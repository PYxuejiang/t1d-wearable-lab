import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.brist1d import read_subject
from t1d_lab.forecasting import CONTEXT_FEATURES,FUSION_FEATURES
from t1d_lab.risk import incident_labels,select_threshold,timeline_metrics,aggregate_metrics


def main():
    output=ROOT/'outputs/module1_incident'
    output.mkdir(exist_ok=True,parents=True)
    f=pd.read_parquet(ROOT/'data/processed/brist1d_features.parquet')
    frames=[]; event_map={}; nominal_map={}
    for subject,g in f.groupby('subject'):
        channels,report=read_subject(ROOT/'data/raw/brist1d'/f'{subject}.csv')
        labels,events=incident_labels(channels['bg'],report['nominal_cgm_minutes'])
        frames.append(g.merge(labels,left_on='decision_time',right_index=True,how='left'))
        event_map[subject]=events
        nominal_map[subject]=report['nominal_cgm_minutes']
    data=pd.concat(frames,ignore_index=True)
    all_predictions=[]; all_rows=[]; thresholds=[]
    with threadpool_limits(limits=2):
      for protocol in ['temporal','loso']:
       for subject in sorted(data.subject.unique()):
        population=data.subject.eq(subject) if protocol=='temporal' else data.subject.ne(subject)
        train=data[population&data.split.eq('train')&data.incident_y.notna()]
        validation=data[population&data.split.eq('validation')].copy()
        test=data[data.subject.eq(subject)&(data.split.eq('test') if protocol=='temporal' else data.split.ne('purged'))].copy()
        for name,columns in [('context',CONTEXT_FEATURES),('fusion',FUSION_FEATURES)]:
          if train.incident_y.nunique()<2:
            print('Insufficient training classes',protocol,subject,name,flush=True)
            continue
          model=HistGradientBoostingClassifier(max_iter=80,max_leaf_nodes=15,learning_rate=.08,l2_regularization=1,class_weight='balanced',early_stopping=False,random_state=20261016)
          model.fit(train[columns],train.incident_y)
          vmask=validation.incident_y.notna()
          tmask=test.incident_y.notna()
          val_raw=model.predict_proba(validation.loc[vmask,columns])[:,1]
          test_raw=model.predict_proba(test.loc[tmask,columns])[:,1]
          calibrated=validation.loc[vmask,'incident_y'].nunique()==2
          if calibrated:
            calibrator=LogisticRegression(C=1,random_state=20261016)
            calibrator.fit(logit(np.clip(val_raw,1e-6,1-1e-6)).reshape(-1,1),validation.loc[vmask,'incident_y'])
            val_score=calibrator.predict_proba(logit(np.clip(val_raw,1e-6,1-1e-6)).reshape(-1,1))[:,1]
            test_score=calibrator.predict_proba(logit(np.clip(test_raw,1e-6,1-1e-6)).reshape(-1,1))[:,1]
          else:
            val_score,test_score=val_raw,test_raw
          validation['score']=np.nan
          validation.loc[vmask,'score']=val_score
          threshold=select_threshold(validation,event_map,'forecast',nominal_map)
          test['score']=np.nan
          test.loc[tmask,'score']=test_score
          test['protocol'],test['model'],test['threshold']=protocol,name,threshold
          row=timeline_metrics(test,event_map[subject],'forecast',threshold,nominal_map[subject])
          row.update(protocol=protocol,subject=subject,model=name,calibrated=calibrated,threshold=threshold)
          row['matches']=[{k:str(v) if isinstance(v,pd.Timestamp) else v for k,v in x.items()} for x in row['matches']]
          all_rows.append(row)
          all_predictions.append(test[['subject','decision_time','incident_y','future_known','incident_eligible','score','protocol','model','threshold']])
          thresholds.append({'protocol':protocol,'subject':subject,'model':name,'validation_selected_threshold':threshold,'calibrated':calibrated})
          print(protocol,subject,name,'recall',row['event_recall'],'FA/day',row['false_alerts_per_person_day'],flush=True)
       pd.concat(all_predictions,ignore_index=True).to_parquet(output/'predictions.parquet',index=False)
    summaries={}
    for protocol in ['temporal','loso']:
        summaries[protocol]={name:aggregate_metrics([r for r in all_rows if r['protocol']==protocol and r['model']==name]) for name in ['context','fusion']}
    (output/'metrics_by_subject.json').write_text(json.dumps(all_rows,indent=2),encoding='utf-8')
    (output/'threshold_selection.json').write_text(json.dumps(thresholds,indent=2),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
