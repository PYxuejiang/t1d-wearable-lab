"""Unseen-subject point classification on a separately sourced public cohort."""
import hashlib
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_improvement import learner
from t1d_lab.risk import point_metrics


def main(config_name='smartwatch_replication_v1.json'):
    config=json.loads((ROOT/'configs'/config_name).read_text());frames=[];audits=[]
    personal=config['protocol']=='personalized_row_holdout'
    dest=ROOT/'outputs'/config.get('output_directory','smartwatch_replication_v1');dest.mkdir(parents=True,exist_ok=True)
    for p in sorted((ROOT/'data/raw/smartwatch_hypo').glob('*.csv')):
        f=pd.read_csv(p);f['source_row']=np.arange(len(f));f['subject']=p.stem
        if not f.hypoglycemia.dropna().isin([0.,1.]).all():raise ValueError('Unrecognized source labels')
        excluded=config['excluded']+['source_row','subject']
        wearable=[c for c in f.select_dtypes(include='number') if c not in excluded+['sin_hour','cos_hour']]
        # Physiologically impossible zero measurements are missing, not normal physiology.
        for c in wearable:
            if c.startswith(('hr_','last_measured_hrv','last_measured_ox','last_measured_rr')):f.loc[f[c].eq(0),c]=np.nan
        f['split']='purged';n=len(f)
        f.loc[f.source_row.lt(int(n*.6)-120),'split']='train'
        f.loc[f.source_row.ge(int(n*.6)+120)&f.source_row.lt(int(n*.8)-120),'split']='validation'
        # Test subject is unseen and kept whole; no fabricated row-to-time conversion.
        f['available']=f[wearable].notna().any(axis=1)
        hour=f.hour.to_numpy();agreement=max(float(np.mean((((np.arange(n)+phase)//60+int(hour[0]))%24)==hour)) for phase in range(60))
        audits.append({'subject':p.stem,'source_rows':n,'unknown_reference_rows':int(f.hypoglycemia.isna().sum()),'known_positive_fraction':float(f.hypoglycemia.mean()),'no_wearable_rows':int((~f.available).sum()),'minute_row_hour_agreement':agreement})
        frames.append(f)
    data=pd.concat(frames,ignore_index=True);sets={'clock':['sin_hour','cos_hour'],'wearable':wearable,'wearable_time':wearable+['sin_hour','cos_hour']}
    all_predictions=[];selections=[];candidates=[];metrics=[]
    for subject in sorted(data.subject.unique()):
      available=data.hypoglycemia.notna()&data.available
      population=data.subject.eq(subject) if personal else data.subject.ne(subject)
      train=data[population&data.split.eq('train')&available]
      val=data[population&data.split.eq('validation')&available]
      test_mask=data.subject.eq(subject)&data.hypoglycemia.notna()
      if personal:
          n=int(data.subject.eq(subject).sum());test_mask &= data.source_row.ge(int(n*.8)+120)
      test=data[test_mask]
      for name,columns in sets.items():
        models={};scores={};choice=[]
        with threadpool_limits(2):
          for method in config['learners']:
            m=learner(method,config['seed']) if train.hypoglycemia.nunique()==2 else None
            if m is not None:m.fit(train[columns],train.hypoglycemia)
            probability=m.predict_proba(val[columns])[:,1] if m is not None else np.repeat(float(train.hypoglycemia.mean()),len(val))
            v=val[['subject','hypoglycemia']].copy();v['score']=probability
            rows=[point_metrics(g.hypoglycemia,g.score) for _,g in v.groupby('subject')]
            aps=[r['ap'] for r in rows if r['ap'] is not None];ap=float(np.mean(aps)) if aps else -1.
            candidates.append({'test_subject':subject,'feature_set':name,'learner':method,'validation_macro_ap':ap})
            choice.append((ap,method));models[method]=m;scores[method]=probability
        method=max(choice,key=lambda x:x[0])[1];vscore=scores[method]
        if val.hypoglycemia.nunique()==2:
            fpr,tpr,thresholds=roc_curve(val.hypoglycemia,vscore)
            feasible=np.flatnonzero((fpr<=.2)&np.isfinite(thresholds))
            idx=max(feasible,key=lambda i:tpr[i]-fpr[i]) if len(feasible) else None
        else:idx=None
        threshold=float(thresholds[idx]) if idx is not None else 1.001
        with threadpool_limits(2):probability=models[method].predict_proba(test.loc[test.available,columns])[:,1] if models[method] is not None else np.repeat(float(train.hypoglycemia.mean()),int(test.available.sum()))
        result=test[['subject','source_row','hypoglycemia','available']].copy();result['score']=np.nan;result.loc[test.available,'score']=probability
        result['threshold']=threshold;result['feature_set']=name
        r=point_metrics(result.hypoglycemia,result.score);mask=result.score.notna();truth=result.loc[mask,'hypoglycemia'].eq(1).to_numpy();alarm=result.loc[mask,'score'].ge(threshold).to_numpy()
        tp=int((truth&alarm).sum());fn=int((truth&~alarm).sum());fp=int((~truth&alarm).sum());tn=int((~truth&~alarm).sum())
        r.update(subject=subject,feature_set=name,threshold=threshold,selected_learner=method,reference_n=len(result),coverage=float(mask.mean()),tp=tp,fn=fn,fp=fp,tn=tn,
                 sensitivity=tp/(tp+fn) if tp+fn else None,specificity=tn/(tn+fp) if tn+fp else None,precision=tp/(tp+fp) if tp+fp else None)
        metrics.append(r);all_predictions.append(result)
        selections.append({'subject':subject,'feature_set':name,'learner':method,'threshold':threshold,'validation_macro_ap':max(choice,key=lambda x:x[0])[0],
                           'training_subjects':sorted(train.subject.unique().tolist()),'validation_subjects':sorted(val.subject.unique().tolist()),'columns':columns,
                           'training_n':len(train),'validation_n':len(val),'training_last_source_row':int(train.source_row.max()),'validation_first_source_row':int(val.source_row.min()),'validation_last_source_row':int(val.source_row.max()),'test_first_source_row':int(test.source_row.min()),'validation_sensitivity':float(tpr[idx]) if idx is not None else 0.,'validation_specificity':float(1-fpr[idx]) if idx is not None else 1.})
        print('Personalized row holdout' if personal else 'Independent subject',subject,name,'AUC',r['roc_auc'],'AP',r['ap'],flush=True)
      pd.concat(all_predictions,ignore_index=True).to_parquet(dest/'predictions.parquet',index=False)
      for filename,value in [('selections.json',selections),('candidates.json',candidates),('metrics_by_subject.json',metrics),('audit.json',audits)]:
        (dest/filename).write_text(json.dumps(value,indent=2),encoding='utf-8')
    (dest/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    print('Personalized source-row experiment completed' if personal else 'Independent-cohort point experiment completed','; alarm efficacy not evaluated')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default='smartwatch_replication_v1.json')
    main(parser.parse_args().config)
