"""Predeclared contextual ablation and calibration, with no CGM model input."""
import hashlib
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from t1d_lab.contextual import SETS,CONTEXT,prepare,fit_calibration,calibrated_scores,threshold_on_validation,validate_protocol
from t1d_lab.risk import point_metrics
from run_improvement import learner


def score_row(frame,score,threshold):
    mask=np.isfinite(score);y=frame.hypoglycemia.to_numpy(dtype=bool)[mask];alarm=score[mask]>=threshold
    tp=int((y&alarm).sum());tn=int((~y&~alarm).sum());fp=int((~y&alarm).sum());fn=int((y&~alarm).sum())
    r=point_metrics(frame.hypoglycemia,score)
    r.update(reference_n=len(frame),coverage=float(mask.mean()),threshold=threshold,tp=tp,tn=tn,fp=fp,fn=fn,
        sensitivity=tp/(tp+fn) if tp+fn else None,specificity=tn/(tn+fp) if tn+fp else None,
        precision=tp/(tp+fp) if tp+fp else None)
    return r


def main(config_name='smartwatch_context_v1_1.json'):
    config_path=ROOT/'configs'/config_name;config=json.loads(config_path.read_text());dest=ROOT/'outputs'/config.get('output_directory','smartwatch_context_v1');dest.mkdir(parents=True,exist_ok=True)
    validate_protocol(config)
    if (dest/'config.json').exists():raise RuntimeError('Completed/checkpointed experiment exists; preserve it and use a new ID for changes')
    (dest/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    predictions=[];validation_predictions=[];metrics=[];selections=[];candidates=[];audits=[]
    for path in sorted((ROOT/'data/raw/smartwatch_hypo').glob('*.csv')):
        frame,missing=prepare(pd.read_csv(path));subject=path.stem;n=len(frame);frame['source_row']=np.arange(n)
        known=frame.hypoglycemia.notna();mask=known&frame.available
        first,second=[int(n*f) for f in config['fractions']];purge=config['purge_rows']
        train=frame[mask&frame.source_row.lt(first-purge)]
        val=frame[mask&frame.source_row.ge(first+purge)&frame.source_row.lt(second-purge)]
        test=frame[known&frame.source_row.ge(second+purge)]
        prior=float(train.hypoglycemia.mean()) if len(train) else 0.
        audits.append({'subject':subject,'source_rows':n,'absent_context_columns':missing,
            'unknown_reference_rows':int((~known).sum()),'train_rows':len(train),'validation_rows':len(val),'test_rows':len(test),
            'training_positives':int(train.hypoglycemia.sum()),'validation_positives':int(val.hypoglycemia.sum()),'test_positives':int(test.hypoglycemia.sum()),
            'context_missing_fractions':{c:float(frame[c].isna().mean()) for c in CONTEXT},'IOB_constant_zero':bool(frame.IOB.eq(0).all())})
        for name in config['feature_sets']:
            columns=SETS[name];models={};scores={};choice=[]
            with threadpool_limits(2):
                for method in config['learners']:
                    model=learner(method,config['seed']) if train.hypoglycemia.nunique()==2 else None
                    if model is not None:model.fit(train[columns],train.hypoglycemia)
                    p=model.predict_proba(val[columns])[:,1] if model is not None else np.repeat(prior,len(val))
                    v=point_metrics(val.hypoglycemia,p);rank=v['ap'] if v['ap'] is not None else -1.
                    candidates.append({'subject':subject,'feature_set':name,'method':method,'validation_ap':v['ap'],'validation_brier':v['brier'],'constant_fallback':model is None})
                    models[method]=model;scores[method]=p;choice.append((rank,method))
            method=max(choice,key=lambda x:x[0])[1];model=models[method];vp=scores[method]
            # Calibration sees validation only; its mapping never flips ranking.
            calibration=fit_calibration(vp,val.hypoglycemia)
            tscore=np.full(len(test),np.nan);valid=test.available.to_numpy()
            with threadpool_limits(2):tscore[valid]=model.predict_proba(test.loc[valid,columns])[:,1] if model is not None else prior
            thresholds={view:threshold_on_validation(val.hypoglycemia,p) for view,p in [('raw',vp),('calibrated',calibrated_scores(vp,calibration))]}
            thresholds['training_prior']=1.001
            for view,ps in [('raw',tscore),('calibrated',calibrated_scores(tscore,calibration)),('training_prior',np.where(np.isfinite(tscore),prior,np.nan))]:
                threshold=thresholds[view];r=score_row(test,ps,threshold);r.update(subject=subject,feature_set=name,view=view,selected_learner=method)
                metrics.append(r)
                result=test[['source_row','hypoglycemia','available']].copy();result['subject']=subject;result['feature_set']=name;result['view']=view;result['score']=ps;result['threshold']=threshold
                predictions.append(result)
            # Save validation predictions locally for independently checking calibration/threshold provenance.
            vframe=val[['source_row','hypoglycemia']].copy();vframe['subject']=subject;vframe['feature_set']=name;vframe['raw_score']=vp;vframe['calibrated_score']=calibrated_scores(vp,calibration)
            validation_predictions.append(vframe)
            selections.append({'subject':subject,'feature_set':name,'method':method,'columns':columns,'thresholds':thresholds,'calibration':calibration,
                'training_prior':prior,'train_last_source_row':int(train.source_row.max()),'validation_first_source_row':int(val.source_row.min()),
                'validation_last_source_row':int(val.source_row.max()),'test_first_source_row':int(test.source_row.min())})
            print(subject,name,method,'raw AP',metrics[-3]['ap'],'cal Brier',metrics[-2]['brier'],flush=True)
        pd.concat(predictions,ignore_index=True).to_parquet(dest/'predictions.parquet',index=False)
        pd.concat(validation_predictions,ignore_index=True).to_parquet(dest/'validation_predictions.parquet',index=False)
        for filename,value in [('candidates.json',candidates),('selections.json',selections),('metrics_by_subject.json',metrics),('audit.json',audits)]:
            (dest/filename).write_text(json.dumps(value,indent=2),encoding='utf-8')
    (dest/'completed.json').write_text(json.dumps({'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),'subjects':len(audits),'test_groups':len(metrics)},indent=2),encoding='utf-8')
    print('Context and calibration experiment complete; point task only')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default='smartwatch_context_v1_1.json')
    main(parser.parse_args().config)
