"""Reconstruct reference runs, alarm state and matching independently of risk.py."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.brist1d import read_subject
from t1d_lab.risk import aggregate_metrics


def independent_events(g,nominal):
    low=g.lt(3.9)
    gaps=g.index.to_series().diff().dt.total_seconds().gt(nominal*90)
    group=(low.ne(low.shift(fill_value=False))|gaps).cumsum()
    events=[]
    for _,run in g[low].groupby(group[low]):
        start,end=run.index[0],run.index[-1]
        position=g.index.get_loc(start)
        known=position>0 and g.iloc[position-1]>=3.9 and (start-g.index[position-1]).total_seconds()<=nominal*90
        if known and (end-start).total_seconds()>=900: events.append((start,end))
    return events


def independent_score(frame,events,nominal):
    frame=frame.sort_values('decision_time')
    times=pd.DatetimeIndex(frame.decision_time)
    threshold=float(frame.threshold.iloc[0])
    active=False; ready=None;previous=None;alerts=[]
    for timestamp,score in zip(times,frame.score):
        if previous is not None and (timestamp-previous).total_seconds()>nominal*90:
            active=False;ready=None
        if not np.isfinite(score) or score<threshold:
            if active:ready=timestamp+pd.Timedelta(minutes=30)
            active=False
        elif not active:
            if ready is None or timestamp>=ready: alerts.append(timestamp)
            active=True
        previous=timestamp
    eligible_events=[e for e in events if times[0]<=e[0]<=times[-1]]
    taken=set(); hits=0
    for start,end in eligible_events:
        for i,alarm in enumerate(alerts):
            if i not in taken and 0<(start-alarm).total_seconds()<=1800:
                hits+=1;taken.add(i);break
    known_times=times[frame.future_known.to_numpy()]
    gaps=np.diff(known_times.asi8)/60e9
    hours=float(gaps[(gaps>0)&(gaps<=1.5*nominal)].sum()/60)
    return len(eligible_events),hits,len(alerts)-hits,hours


def main():
    output=ROOT/'outputs/module1_incident'
    saved=json.loads((output/'metrics_by_subject.json').read_text())
    predictions=pd.read_parquet(output/'predictions.parquet')
    source={}
    for subject in predictions.subject.unique():
        channels,audit=read_subject(ROOT/'data/raw/brist1d'/f'{subject}.csv')
        nominal=audit['nominal_cgm_minutes']
        source[subject]=(independent_events(channels['bg'],nominal),nominal)
    lookup={(r['protocol'],r['subject'],r['model']):r for r in saved}
    maximum=0
    for key,frame in predictions.groupby(['protocol','subject','model']):
        events,nominal=source[key[1]]
        counts=independent_score(frame,events,nominal)
        row=lookup[key]
        assert counts[:3]==(row['reference_events'],row['matched_events'],row['unmatched_alarms']),(key,counts,row)
        maximum=max(maximum,abs(counts[3]-row['observation_hours']))
    assert maximum<1e-8
    summary={p:{m:aggregate_metrics([r for r in saved if r['protocol']==p and r['model']==m]) for m in ['context','fusion']} for p in ['temporal','loso']}
    paired={}
    for protocol in ['temporal','loso']:
        a={r['subject']:r['event_recall'] for r in saved if r['protocol']==protocol and r['model']=='context'}
        b={r['subject']:r['event_recall'] for r in saved if r['protocol']==protocol and r['model']=='fusion'}
        d=np.array([b[s]-a[s] for s in a if a[s] is not None and b.get(s) is not None])
        rng=np.random.default_rng(20261016)
        samples=d[rng.integers(0,len(d),(2000,len(d)))].mean(axis=1)
        paired[protocol]={'recall_difference_percentage_points':float(d.mean()*100),'95_interval_percentage_points':[float(np.quantile(samples,q)*100) for q in [.025,.975]],'subjects':len(d)}
    record={'stage':'S2b','engineering_status':'passed','evaluation_status':'independently_reconstructed_events_and_alarms_passed',
            'effect_status':{p:{m:summary[p][m]['effect_status'] for m in summary[p]} for p in summary},
            'groups_verified':len(lookup),'count_mismatches':0,'observation_hours_max_difference':maximum,
            'results':summary,'paired_sensor_gain':paired,
            'limitations':['Retrospective event definition with 5/15-minute reference sampling.','Coverage is conditional on a reference-observable eligible decision opportunity.','Not a clinical alarm or an intervention benefit study.']}
    (output/'verified_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (ROOT/'docs/acceptance/S2b.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('S2b verified',len(lookup),'groups; mismatches=0; effects',record['effect_status'])


if __name__=='__main__':main()
