"""Freeze candidate selection before touching each chronological test partition."""
import hashlib
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier,RandomForestClassifier,ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.improvement import features,past_smooth
from t1d_lab.evaluation import reference_events
from t1d_lab.risk import timeline_metrics,point_metrics,aggregate_metrics


def learner(name,seed):
    if name=='logistic':model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=1000,random_state=seed))
    elif name in ['random_forest','extra_trees']:
        constructor=RandomForestClassifier if name=='random_forest' else ExtraTreesClassifier
        model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),constructor(n_estimators=160,max_depth=5,min_samples_leaf=10,max_features=.7,class_weight='balanced',n_jobs=2,random_state=seed))
    else:model=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=7,min_samples_leaf=30,learning_rate=.05,l2_regularization=10,class_weight='balanced',early_stopping=False,random_state=seed)
    return model


def operating_points(validation,events,budgets,spans):
    options={budget:[] for budget in budgets}
    for span in spans:
        g=validation.copy();g['score']=past_smooth(g.decision_time,g.score,span)
        finite=g.score[np.isfinite(g.score)]
        thresholds=np.unique(np.r_[np.quantile(finite,np.linspace(0,1,101)) if len(finite) else [],1.001])
        for threshold in thresholds:
            r=timeline_metrics(g,events,'detection',float(threshold),5)
            for budget in budgets:
                if r['false_alerts_per_person_day'] is not None and r['false_alerts_per_person_day']<=budget:
                    options[budget].append(((r['event_recall'] or 0,-r['false_alerts_per_person_day'],-span,float(threshold)),span,float(threshold),r))
    return {budget:max(options[budget],key=lambda v:v[0])[1:] for budget in budgets}


def main(config_name='improvement_v2.json'):
    config_path=ROOT/'configs'/config_name;config=json.loads(config_path.read_text())
    include_device=config.get('include_device_summaries',False)
    history=config['history_minutes']
    warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
    output=ROOT/'outputs'/config.get('output_directory','improvement_v2');output.mkdir(exist_ok=True,parents=True)
    candidates=[];selections=[];predictions=[];rows=[];audits=[]
    features_all=[]
    for path in sorted((ROOT/'data/processed').glob('*signal_features.parquet')):
        raw=pd.read_parquet(path);subject=raw.subject.iloc[0]
        if include_device:
            added=pd.read_parquet(ROOT/'data/processed'/f'{subject}_device_summaries.parquet')
            raw=raw.merge(added,on=['subject','decision_time'],how='left',validate='one_to_one')
        g,sets=features(raw,include_device=include_device)
        ref=pd.Series(g.label_proxy_mg_dl.to_numpy(),index=pd.DatetimeIndex(g.decision_time))
        events=reference_events(ref,5,threshold=70)
        bounds=[g.decision_time.min()+(g.decision_time.max()-g.decision_time.min())*r for r in [.6,.8]]
        crossed=[e for e in events if any(e.start<b<e.end for b in bounds)]
        for e in crossed:
            g.loc[(g.decision_time+pd.Timedelta(minutes=15)>=e.start)&(g.decision_time-pd.Timedelta(minutes=history)<=e.end),'split']='purged'
        events=[e for e in events if e not in crossed]
        features_all.append(g)
        train=g[g.split.eq('train')&g.available];val=g[g.split.eq('validation')].copy();test=g[g.split.eq('test')].copy()
        audit={'subject':subject,'train':len(train),'training_positives':int(train.label_low.sum()),'validation':len(val),'validation_available':int(val.available.sum()),'validation_positive_available':int(val.loc[val.available,'label_low'].sum()),'test_reference_anchors':len(test),'test_positive_anchors':int(test.label_low.sum())}
        audits.append(audit)
        models={};cache={}
        with threadpool_limits(2):
          for feature_set,columns in sets.items():
            for method in config['learners']:
                key=feature_set+'/'+method
                if len(train)<100 or int(train.label_low.sum())<5 or train.label_low.nunique()<2:
                    model=None;vscore=np.repeat(float(train.label_low.mean()) if len(train) else 0.,int(val.available.sum()))
                else:
                    model=learner(method,config['seed'])
                    model.fit(train[columns],train.label_low)
                    vscore=model.predict_proba(val.loc[val.available,columns])[:,1]
                metrics=point_metrics(val.loc[val.available,'label_low'],vscore)
                candidates.append({'subject':subject,'candidate':key,'validation':metrics,'fallback_constant':model is None})
                models[key]=(model,columns);cache[key]=vscore
                print('Validation',subject,key,'AP',metrics['ap'],flush=True)
        # Select once on validation AP; do not retain the best test candidate.
        for experiment,allowed in [('clock_baseline',['clock/']),('static_selected',['static/']),('temporal_selected',['dynamic/','dynamic_time/'])]:
            choices=[r for r in candidates if r['subject']==subject and any(r['candidate'].startswith(a) for a in allowed)]
            winner=max(choices,key=lambda r:r['validation']['ap'] if r['validation']['ap'] is not None else -1)
            key=winner['candidate'];model,columns=models[key]
            val['score']=np.nan;val.loc[val.available,'score']=cache[key]
            points=operating_points(val,events,config['alarm_budgets_per_person_day'],config['smoothing_spans'])
            test['raw_score']=np.nan
            if test.available.any():
                with threadpool_limits(2):score=model.predict_proba(test.loc[test.available,columns])[:,1] if model is not None else np.repeat(float(train.label_low.mean()) if len(train) else 0.,int(test.available.sum()))
                test.loc[test.available,'raw_score']=score
            for budget,(span,threshold,validation_result) in points.items():
                selected={'subject':subject,'experiment':experiment,'candidate':key,'columns':columns,'budget':budget,'span':span,'threshold':threshold,'validation_ap':winner['validation']['ap'],
                    'validation_event_recall':validation_result['event_recall'],'validation_false_alerts_per_person_day':validation_result['false_alerts_per_person_day'],
                    'train_last':str(train.decision_time.max()),'validation_first':str(val.decision_time.min()),'validation_last':str(val.decision_time.max()),'test_first':str(test.decision_time.min())}
                selections.append(selected)
                f=test.copy();f['score']=past_smooth(f.decision_time,f.raw_score,span)
                f['threshold']=threshold;f['budget']=budget;f['experiment']=experiment
                r=timeline_metrics(f,events,'detection',threshold,5)
                r.update(subject=subject,experiment=experiment,budget=budget,candidate=key,threshold=threshold,span=span)
                r['matches']=[{k:str(v) if isinstance(v,pd.Timestamp) else v for k,v in x.items()} for x in r['matches']]
                rows.append(r)
                predictions.append(f[['subject','decision_time','label_low','score','threshold','available','budget','experiment']])
            print('Selected',subject,experiment,key,flush=True)
        # Checkpoint after every participant, not a best-run overwrite.
        pd.concat(predictions,ignore_index=True).to_parquet(output/'predictions.parquet',index=False)
        (output/'selections.json').write_text(json.dumps(selections,indent=2),encoding='utf-8')
        (output/'candidates.json').write_text(json.dumps(candidates,indent=2),encoding='utf-8')
        (output/'metrics_by_subject.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    pd.concat(features_all,ignore_index=True).to_parquet(output/'features.parquet',index=False)
    (output/'cohort_audit.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
    summary={e:{str(b):aggregate_metrics([r for r in rows if r['experiment']==e and r['budget']==b]) for b in config['alarm_budgets_per_person_day']} for e in ['clock_baseline','static_selected','temporal_selected']}
    (output/'summary.json').write_text(json.dumps({'protocol':config,'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),'results':summary},indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default='improvement_v2.json')
    main(parser.parse_args().config)
