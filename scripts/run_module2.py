"""Paired signal ablations with common training data and end-to-end reporting."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.evaluation import reference_events,split_masks
from t1d_lab.risk import timeline_metrics,aggregate_metrics,select_threshold,point_metrics

GROUPS={'ppg':['ppg'],'wrist':['ppg','acc'],'wrist_eda_temp':['ppg','acc','eda','temp'],
        'ecg':['ecg'],'all':['ppg','acc','eda','temp','ecg']}


def completed_sources():
    archives=list((ROOT/'data/raw/physiocgm').glob('*_raw.zip'))
    complete=[]
    for p in archives:
        s=p.name.removesuffix('_raw.zip')
        feature=ROOT/'data/processed'/f'{s}_signal_features.parquet'
        provenance=feature.with_suffix('.provenance.json')
        audit=ROOT/'outputs/audit'/f'physiocgm_{s}.json'
        if feature.exists() and provenance.exists(): complete.append((s,'extracted'))
        elif audit.exists() and not json.loads(audit.read_text())['clock_resolved_by_sensor_check']:
            complete.append((s,'clock_quarantined'))
    return archives,complete


def prepare_data():
    frames=[]; event_map={}; nominals={}; audits=[]
    archives,done=completed_sources()
    if len(archives)!=10 or len(done)!=10:
        raise RuntimeError('S1b not ready: all source records must be accounted for before training')
    for subject,status in done:
        report=json.loads((ROOT/'outputs/audit'/f'physiocgm_{subject}.json').read_text())
        if status!='extracted':
            audits.append({'subject':subject,'status':status})
            continue
        g=pd.read_parquet(ROOT/'data/processed'/f'{subject}_signal_features.parquet').sort_values('decision_time')
        t=pd.DatetimeIndex(g.decision_time)
        reference=pd.Series(g.label_proxy_mg_dl.to_numpy(dtype=float),index=t)
        nominal=5.
        events=reference_events(reference,nominal,threshold=70)
        masks=split_masks(t,t[0],t[-1],history_minutes=5,horizon_minutes=0,confirmation_minutes=15)
        # Do not put one long event on both sides of a chronological boundary.
        crossed=set()
        for ratio in [.6,.8]:
            boundary=t[0]+(t[-1]-t[0])*ratio
            for event in events:
                if event.start<boundary<event.end:
                    crossed.add(event.start)
                    intersects=(t+pd.Timedelta(minutes=15)>=event.start)&(t-pd.Timedelta(minutes=5)<=event.end)
                    masks={k:v&~intersects for k,v in masks.items()}
        g['split']='purged'
        for key,mask in masks.items():g.loc[mask,'split']=key
        for name,kinds in GROUPS.items():
            valid=np.ones(len(g),dtype=bool)
            for kind in kinds:
                valid &= g.get(kind+'_completeness',pd.Series(0,index=g.index)).fillna(0).to_numpy()>=.9
                if kind in ['ppg','ecg']:
                    valid &= g.get(kind+'_valid',pd.Series(0,index=g.index)).fillna(0).to_numpy()==1
            g[name+'_available']=valid
        g['common_available']=g.all_available
        g['nominal_minutes']=nominal
        event_map[subject]=[e for e in events if e.start not in crossed];nominals[subject]=nominal
        frames.append(g)
        audits.append({'subject':subject,'status':status,'reference_anchors':len(g),
                       'low_anchors':int(g.label_low.sum()),'common_anchors':int(g.common_available.sum()),
                       'clock_shift_hours':report['best_clock_candidate']['shift_hours'],
                       'boundary_crossing_events_excluded':[str(t) for t in sorted(crossed)]})
    if len(frames)<5:raise RuntimeError('Fewer than 5 clock-audited participants; no full-cohort sensor claim')
    (ROOT/'docs/acceptance/S1b.json').write_text(json.dumps({'stage':'S1b','engineering_status':'passed',
        'evaluation_status':'source_clock_and_feature_audit_passed','effect_status':'not_tested',
        'source_archives_accounted':len(archives),'included_subjects':len(frames),'audit':audits,
        'limitations':['CGM/chest wall-clock alignment is a declared source assumption.','No archives were expanded; features read directly from CSV members.','Quarantined clocks are not assigned labels by optimizing disease prediction.']},indent=2),encoding='utf-8')
    return pd.concat(frames,ignore_index=True),event_map,nominals


def main(wait=False):
    while wait:
        files,done=completed_sources()
        if len(files)==10 and len(done)==10:break
        print('S1b waiting for extraction',len(done),'/10',flush=True)
        time.sleep(30)
    data,event_map,nominal_map=prepare_data()
    output=ROOT/'outputs/module2_detection';output.mkdir(exist_ok=True,parents=True)
    rows=[];predictions=[];skipped=[];folds=[]
    numeric=set(data.select_dtypes(include='number').columns)
    with threadpool_limits(limits=2):
     for protocol in ['temporal','loso']:
      for subject in sorted(data.subject.unique()):
       population=data.subject.eq(subject) if protocol=='temporal' else data.subject.ne(subject)
       train=data[population&data.split.eq('train')&data.common_available]
       validation=data[population&data.split.eq('validation')].copy()
       test=data[data.subject.eq(subject)&(data.split.eq('test') if protocol=='temporal' else data.split.ne('purged'))].copy()
       if len(train)<100 or train.label_low.nunique()<2:
           skipped.append({'protocol':protocol,'subject':subject,'reason':'insufficient common training labels'})
           continue
       for name,kinds in GROUPS.items():
        columns=sorted(c for c in numeric if any(c.startswith(k+'_') for k in kinds) and not c.endswith('_available'))
        # The identical common training set isolates the information contribution.
        model=HistGradientBoostingClassifier(max_iter=80,max_leaf_nodes=15,learning_rate=.08,l2_regularization=1,class_weight='balanced',early_stopping=False,random_state=20261016)
        model.fit(train[columns],train.label_low)
        vm=validation.common_available
        tm=test[name+'_available']
        if vm.sum()<20 or tm.sum()==0:
            skipped.append({'protocol':protocol,'subject':subject,'model':name,'reason':'insufficient valid validation/test signals'})
            continue
        vraw=model.predict_proba(validation.loc[vm,columns])[:,1]
        traw=model.predict_proba(test.loc[tm,columns])[:,1]
        calibrated=validation.loc[vm,'label_low'].nunique()==2
        if calibrated:
            calibration=LogisticRegression(C=1,random_state=20261016).fit(logit(np.clip(vraw,1e-6,1-1e-6)).reshape(-1,1),validation.loc[vm,'label_low'])
            vscore=calibration.predict_proba(logit(np.clip(vraw,1e-6,1-1e-6)).reshape(-1,1))[:,1]
            tscore=calibration.predict_proba(logit(np.clip(traw,1e-6,1-1e-6)).reshape(-1,1))[:,1]
        else:vscore,tscore=vraw,traw
        validation['score']=np.nan;validation.loc[vm,'score']=vscore
        threshold=select_threshold(validation,event_map,'detection',nominal_map)
        folds.append({'protocol':protocol,'subject':subject,'model':name,'columns':columns,
                      'training_subjects':sorted(train.subject.unique().tolist()),
                      'validation_subjects':sorted(validation.subject.unique().tolist()),
                      'training_rows':len(train),'validation_scored_rows':int(vm.sum()),
                      'training_last_decision':str(train.decision_time.max()),
                      'validation_first_decision':str(validation.decision_time.min()),
                      'test_first_decision':str(test.decision_time.min()),'threshold':threshold,
                      'calibrated':calibrated})
        test['score']=np.nan;test.loc[tm,'score']=tscore
        test['model'],test['protocol'],test['threshold']=name,protocol,threshold
        for view in ['end_to_end','paired_common']:
            evaluated=test.copy()
            if view=='paired_common':evaluated.loc[~evaluated.common_available,'score']=np.nan
            row=timeline_metrics(evaluated,event_map[subject],'detection',threshold,5)
            row.update(protocol=protocol,subject=subject,model=name,view=view,threshold=threshold,calibrated=calibrated)
            row['matches']=[{k:str(v) if isinstance(v,pd.Timestamp) else v for k,v in x.items()} for x in row['matches']]
            rows.append(row)
        predictions.append(test[['subject','decision_time','label_low','label_very_low','score','common_available',name+'_available','protocol','model','threshold']].rename(columns={name+'_available':'channel_available'}))
        print(protocol,subject,name,'threshold',threshold,'available',int(tm.sum()),flush=True)
      pd.concat(predictions,ignore_index=True).to_parquet(output/'predictions.parquet',index=False)
    summary={protocol:{view:{name:aggregate_metrics([r for r in rows if r['protocol']==protocol and r['view']==view and r['model']==name]) for name in GROUPS} for view in ['end_to_end','paired_common']} for protocol in ['temporal','loso']}
    (output/'metrics_by_subject.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (output/'exclusions.json').write_text(json.dumps(skipped,indent=2),encoding='utf-8')
    (output/'folds.json').write_text(json.dumps(folds,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--wait-for-extraction',action='store_true')
    main(parser.parse_args().wait_for_extraction)
