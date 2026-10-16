"""Incident labels, calibrated risks, and event operating-point evaluation."""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from .evaluation import alarm_triggers, match_events, nearest_future_reference, reference_events, reference_hours


def incident_labels(glucose, nominal_minutes):
    times=glucose.index
    events=reference_events(glucose,nominal_minutes)
    _, confirmation=nearest_future_reference(glucose,times,45,2.5)
    bad=np.r_[False,np.diff(times.asi8)/60e9>1.5*nominal_minutes]
    cumulative=np.cumsum(bad)
    current=np.arange(len(times))
    ending=np.searchsorted(times.asi8,confirmation.astype('int64').to_numpy()).clip(0,len(times)-1)
    future_known=confirmation.notna().to_numpy() & (cumulative[ending]==cumulative[current])
    beginning=np.searchsorted(times.asi8,times.asi8-pd.Timedelta(minutes=15).value,side='right')-1
    safe=np.maximum(beginning,0)
    past_known=(beginning>=0)&((times.asi8-times.asi8[safe])/60e9<=15+1.5*nominal_minutes)&(cumulative[current]==cumulative[safe])
    normal=glucose.rolling('15min',closed='both').min().ge(3.9).to_numpy()
    eligible=future_known&past_known&normal
    starts=np.array([e.start.value for e in events if not e.left_censored],dtype=np.int64)
    target=np.zeros(len(times),dtype=float)
    if len(starts):
        positions=np.searchsorted(starts,times.asi8,side='right')
        safe_positions=np.minimum(positions,len(starts)-1)
        target=((positions<len(starts))&(starts[safe_positions]-times.asi8<=pd.Timedelta(minutes=30).value)).astype(float)
    target[~eligible]=np.nan
    return pd.DataFrame({'incident_y':target,'future_known':future_known,'incident_eligible':eligible},index=times),events


def point_metrics(labels,scores):
    labels=np.asarray(labels,dtype=float)
    scores=np.asarray(scores,dtype=float)
    valid=np.isfinite(labels)&np.isfinite(scores)
    y,p=labels[valid],scores[valid]
    both=len(np.unique(y))==2
    return {'point_n':len(y),'positive_fraction':float(np.mean(y)) if len(y) else None,
            'ap':float(average_precision_score(y,p)) if both else None,
            'roc_auc':float(roc_auc_score(y,p)) if both else None,
            'brier':float(brier_score_loss(y,p)) if len(y) else None,
            'single_class':not both}


def timeline_metrics(frame,events,task,threshold,nominal_minutes):
    frame=frame.sort_values('decision_time')
    if frame.empty:
        return None
    t=pd.DatetimeIndex(frame.decision_time)
    scores=frame.score.to_numpy(dtype=float)
    gaps=np.r_[True,np.diff(t.asi8)/60e9>1.5*nominal_minutes]
    groups=np.cumsum(gaps)
    alarms=[]
    for group in np.unique(groups):
        mask=groups==group
        alarms.extend(alarm_triggers(t[mask],scores[mask],threshold))
    selected=[e for e in events if not e.left_censored and t[0]<=e.start<=t[-1]]
    matches,unmatched=match_events(selected,alarms,task)
    # Unknown labels/followup do not become false negatives or normal observation time.
    observation_mask=frame.future_known.to_numpy() if task=='forecast' else np.ones(len(frame),dtype=bool)
    hours=reference_hours(t[observation_mask],nominal_minutes)
    eligible=frame.incident_eligible.to_numpy() if task=='forecast' else np.ones(len(frame),dtype=bool)
    coverage=float(np.isfinite(scores[eligible]).mean()) if eligible.any() else None
    offsets=[x['offset_minutes'] if task=='forecast' else -x['offset_minutes'] for x in matches]
    y=frame.incident_y.to_numpy() if task=='forecast' else frame.label_low.to_numpy(dtype=float)
    result=point_metrics(y,scores)
    result.update(reference_events=len(selected),matched_events=len(matches),alarms=len(alarms),
                  unmatched_alarms=len(unmatched),observation_hours=hours,
                  event_recall=len(matches)/len(selected) if selected else None,
                  false_alerts_per_person_day=len(unmatched)/(hours/24) if hours>0 else None,
                  event_precision=len(matches)/len(alarms) if alarms else None,
                  coverage=coverage,offset_median_minutes=float(np.median(offsets)) if offsets else None,
                  matches=matches)
    return result


def aggregate_metrics(rows):
    valid=[r for r in rows if r is not None]
    def mean(key):
        v=[r[key] for r in valid if r.get(key) is not None and np.isfinite(r[key])]
        return float(np.mean(v)) if v else None
    hours=sum(r['observation_hours'] for r in valid)
    result={key:mean(key) for key in ['event_recall','event_precision','coverage','ap','roc_auc','brier','offset_median_minutes']}
    result.update(subjects=len(valid),event_subjects=sum(r['reference_events']>0 for r in valid),
                  reference_events=sum(r['reference_events'] for r in valid),matched_events=sum(r['matched_events'] for r in valid),
                  observation_hours=hours,unmatched_alarms=sum(r['unmatched_alarms'] for r in valid))
    offsets=[abs(m['offset_minutes']) for r in valid for m in r.get('matches',[])]
    result['offset_median_minutes']=float(np.median(offsets)) if offsets else None
    result['offset_iqr_minutes']=[float(np.quantile(offsets,q)) for q in [.25,.75]] if offsets else None
    result['false_alerts_per_person_day']=result['unmatched_alarms']/(hours/24) if hours else None
    enough=result['event_subjects']>=5 and result['reference_events']>=20
    achieved=(result['event_recall'] is not None and result['event_recall']>=.8 and result['false_alerts_per_person_day'] is not None and result['false_alerts_per_person_day']<=1 and result['coverage'] is not None and result['coverage']>=.8)
    result['effect_status']='inconclusive' if not enough else 'passed' if achieved else 'failed'
    return result


def select_threshold(frames,event_map,task,nominal_map):
    candidates=[]
    for threshold in [.01,.05,.1,.2,.3,.5,.7,.9,.99,.999,1.001]:
        rows=[timeline_metrics(g,event_map[s],task,threshold,nominal_map[s]) for s,g in frames.groupby('subject')]
        aggregate=aggregate_metrics(rows)
        if aggregate['false_alerts_per_person_day'] is not None and aggregate['false_alerts_per_person_day']<=1:
            candidates.append((aggregate['event_recall'] or 0,-aggregate['false_alerts_per_person_day'],threshold))
    if not candidates:
        return 1.001
    return max(candidates)[2]

