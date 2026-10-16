"""Independent event/alarm reconstruction and paired sensor acceptance."""
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.physiocgm import read_cgm
from t1d_lab.risk import aggregate_metrics


def event_runs(reference):
    """Direct sequential scanner, independent of evaluation.reference_events."""
    runs=[];start=None;last=None;known=False;previous_value=None
    for t,value in reference.items():
        gap=last is not None and (t-last).total_seconds()>450
        if start is not None and (gap or value>=70):
            if known and (last-start).total_seconds()>=900:runs.append((start,last))
            start=None
        if value<70 and start is None:
            start=t;known=last is not None and not gap and previous_value>=70
        last=t;previous_value=value
    if start is not None and known and (last-start).total_seconds()>=900:runs.append((start,last))
    return runs


def evaluate(frame,events):
    f=frame.sort_values('decision_time');t=pd.DatetimeIndex(f.decision_time)
    scores=f.score.to_numpy(dtype=float);threshold=float(f.threshold.iloc[0])
    alarms=[];active=False;ready=None;last=None
    for time,score in zip(t,scores):
        if last is not None and (time-last).total_seconds()>450:active=False;ready=None
        if not np.isfinite(score) or score<threshold:
            if active:ready=time+pd.Timedelta(minutes=30)
            active=False
        elif not active:
            if ready is None or time>=ready:alarms.append(time)
            active=True
        last=time
    events=[e for e in events if t[0]<=e[0]<=t[-1]]
    taken=set();offsets=[];opportunities=0
    for start,end in events:
        opportunities+=int(np.isfinite(scores[(t>=start)&(t<=end)]).any())
        for i,alarm in enumerate(alarms):
            if i not in taken and start<=alarm<=end:
                taken.add(i);offsets.append((alarm-start).total_seconds()/60);break
    intervals=np.diff(t.as_unit('ns').asi8)/60e9
    observed=(intervals>0)&(intervals<=7.5)
    weights=intervals[observed]
    supported=(np.isfinite(scores[:-1])&np.isfinite(scores[1:]))[observed]
    hours=float(weights.sum()/60)
    coverage=float(weights[supported].sum()/weights.sum()) if weights.sum() else None
    return {'reference_events':len(events),'matched_events':len(taken),'alarms':len(alarms),
            'unmatched_alarms':len(alarms)-len(taken),'observation_hours':hours,
            'coverage':coverage,'anchor_coverage':float(np.isfinite(scores).mean()),
            'events_with_input_opportunity':opportunities,
            'conditional_event_recall':len(taken)/opportunities if opportunities else None,
            'independent_delay_median':float(np.median(offsets)) if offsets else None}


def paired_interval(rows,a,b,protocol):
    x={r['subject']:r for r in rows if r['protocol']==protocol and r['view']=='paired_common' and r['model']==a}
    y={r['subject']:r for r in rows if r['protocol']==protocol and r['view']=='paired_common' and r['model']==b}
    subjects=[s for s in x if s in y and x[s]['event_recall'] is not None and y[s]['event_recall'] is not None]
    d=np.array([y[s]['event_recall']-x[s]['event_recall'] for s in subjects])
    if not len(d):return {'status':'inconclusive','subjects':0}
    rng=np.random.default_rng(20261016)
    ci=np.quantile(d[rng.integers(0,len(d),(2000,len(d)))].mean(axis=1),[.025,.975])
    deploy={m:[r for r in rows if r['protocol']==protocol and r['view']=='end_to_end' and r['model']==m] for m in [a,b]}
    coverage_loss=float(np.mean([r['coverage'] for r in deploy[a]])-np.mean([r['coverage'] for r in deploy[b]]))
    b_hours=sum(r['observation_hours'] for r in deploy[b])
    b_false=sum(r['unmatched_alarms'] for r in deploy[b])/(b_hours/24) if b_hours else None
    enough=len(d)>=5 and sum(x[s]['reference_events'] for s in subjects)>=20
    return {'subjects':len(d),'recall_difference_percentage_points':float(d.mean()*100),
            '95_interval_percentage_points':(ci*100).tolist(),
            'end_to_end_coverage_loss_percentage_points':coverage_loss*100,'comparison_false_alerts_per_person_day':b_false,
            'status':'inconclusive' if not enough else 'passed' if d.mean()>=.05 and ci[0]>0 and coverage_loss<=.05 and b_false is not None and b_false<=1 else 'failed'}


def main():
    output=ROOT/'outputs/module2_detection'
    predictions=pd.read_parquet(output/'predictions.parquet')
    saved=json.loads((output/'metrics_by_subject.json').read_text())
    sources={};event_map={};future_violations=0;alignment=[]
    for subject in predictions.subject.unique():
        path=ROOT/'data/raw/physiocgm'/f'{subject}_raw.zip'
        reference=read_cgm(path).label_proxy_mg_dl
        sources[subject]=reference
        features=pd.read_parquet(ROOT/'data/processed'/f'{subject}_signal_features.parquet')
        boundaries=[features.decision_time.min()+(features.decision_time.max()-features.decision_time.min())*r for r in [.6,.8]]
        event_map[subject]=[e for e in event_runs(reference.reindex(pd.DatetimeIndex(features.decision_time))) if not any(e[0]<b<e[1] for b in boundaries)]
        for c in features.columns:
            if c.endswith('_input_end'):future_violations+=int((pd.to_datetime(features[c])>features.decision_time).sum())
    assert future_violations==0
    lookup={(r['protocol'],r['subject'],r['model'],r['view']):r for r in saved}
    verified=[];max_difference=0
    for key,frame in predictions.groupby(['protocol','subject','model']):
        reference=sources[key[1]]
        # Original source timestamps/labels must agree with the exported test anchors.
        expected=reference.reindex(pd.DatetimeIndex(frame.decision_time))
        assert expected.notna().all()
        assert np.array_equal(expected.lt(70).to_numpy(),frame.label_low.to_numpy())
        for view in ['end_to_end','paired_common']:
            f=frame.copy()
            if view=='paired_common':f.loc[~f.common_available,'score']=np.nan
            computed=evaluate(f,event_map[key[1]])
            row=dict(lookup[(*key,view)])
            for k in ['reference_events','matched_events','alarms','unmatched_alarms']:assert computed[k]==row[k],(key,view,k,computed[k],row[k])
            max_difference=max(max_difference,abs(computed['observation_hours']-row['observation_hours']))
            row.update(coverage=computed['coverage'],anchor_coverage=computed['anchor_coverage'],
                       events_with_input_opportunity=computed['events_with_input_opportunity'],
                       conditional_event_recall=computed['conditional_event_recall'])
            valid=np.isfinite(f.score);truth=f.loc[valid,'label_low'].to_numpy(dtype=bool);alarm=f.loc[valid,'score'].ge(f.threshold.iloc[0]).to_numpy()
            tp=int((truth&alarm).sum());fp=int((~truth&alarm).sum());tn=int((~truth&~alarm).sum());fn=int((truth&~alarm).sum())
            row['point_confusion']={'tp':tp,'fp':fp,'tn':tn,'fn':fn}
            row['point_recall']=tp/(tp+fn) if tp+fn else None
            row['point_specificity']=tn/(tn+fp) if tn+fp else None
            row['point_precision']=tp/(tp+fp) if tp+fp else None
            row['point_f1']=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
            verified.append(row)
        # Label clock perturbation is a sensitivity analysis, never a selected shift.
        for shift in [-5,0,5]:
            original=event_map[key[1]]
            r=evaluate(frame,[(s+pd.Timedelta(minutes=shift),e+pd.Timedelta(minutes=shift)) for s,e in original])
            r.update(protocol=key[0],subject=key[1],model=key[2],label_shift_minutes=shift,
                     event_recall=r['matched_events']/r['reference_events'] if r['reference_events'] else None)
            alignment.append(r)
    assert max_difference<1e-8
    folds=json.loads((output/'folds.json').read_text())
    for fold in folds:
        assert not any(c.startswith('label') or c in ['score','threshold'] for c in fold['columns'])
        if fold['protocol']=='loso':assert fold['subject'] not in fold['training_subjects']+fold['validation_subjects']
        else:assert pd.Timestamp(fold['training_last_decision'])+pd.Timedelta(minutes=15)<pd.Timestamp(fold['validation_first_decision'])-pd.Timedelta(minutes=5)
    summary={p:{view:{m:aggregate_metrics([r for r in verified if r['protocol']==p and r['view']==view and r['model']==m]) for m in ['ppg','wrist','wrist_eda_temp','ecg','all']} for view in ['end_to_end','paired_common']} for p in ['temporal','loso']}
    paired={p:{a+'__to__'+b:paired_interval(verified,a,b,p) for a,b in [('ppg','wrist'),('wrist','wrist_eda_temp'),('wrist','all')]} for p in ['temporal','loso']}
    excluded=json.loads((output/'exclusions.json').read_text())
    record={'stage':'S3','engineering_status':'passed','evaluation_status':'independent_counts_source_labels_and_fold_checks_passed',
            'effect_status':{p:{m:r['effect_status'] for m,r in summary[p]['end_to_end'].items()} for p in summary},
            'verified_groups':len(verified),'future_input_violations':future_violations,'count_mismatches':0,
            'observation_hours_max_difference':max_difference,'results':summary,'paired_gain':paired,'skipped_folds':excluded,
            'coverage_definition':'Supported elapsed intervals with finite scores at BOTH endpoints / observed elapsed reference intervals (gaps <=7.5 minutes); macro over subjects.',
            'limitations':['CGM versus chest clock remains a source assumption; +/-5 minute sensitivity is separate.','Low/High censored values are classification labels only.','Quality screening is an engineering heuristic, not a clinically validated SQI.','Common-channel validation conditions threshold selection; missing test data count against end-to-end event recall and coverage.']}
    (output/'verified_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (output/'verified_metrics.json').write_text(json.dumps(verified,indent=2),encoding='utf-8')
    (output/'clock_sensitivity.json').write_text(json.dumps(alignment,indent=2),encoding='utf-8')
    (ROOT/'docs/acceptance/S3.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('S3 independently verified',len(verified),'groups; count mismatches=0')


if __name__=='__main__':main()
