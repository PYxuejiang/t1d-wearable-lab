"""Training-fitted physiology residuals and explicit causal alert policies."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

RAW = ['hr','hrv','rrstd','eda','edav','temp','motion','ppgq']
ECG = ['ecghr','ecghrv','ecgrrstd','ecgq']
DEVIATIONS = ['hr_dev','eda_dev','temp_dev']
CLOCK = ['hour_sin','hour_cos']
MASK = ['wrist_present','ecg_present']
RESIDUAL = RAW + DEVIATIONS + ['hr_residual','hr_eda_interaction']
SETS = {'clock':CLOCK, 'personal_raw':RAW+CLOCK,
        'personal_residual':RESIDUAL+CLOCK, 'pooled_residual':RESIDUAL+CLOCK,
        'pooled_fallback':RESIDUAL+ECG+['ecghr_dev']+MASK+CLOCK,
        'pooled_mask_clock':MASK+CLOCK}
POLICIES = ['legacy_edge','confirm2','smooth_confirm2','smooth_remind30']
NS_MINUTE = 60_000_000_000


def prepare(frame):
    g=frame.sort_values('decision_time').copy().set_index('decision_time',drop=False)
    g['wrist_present']=g.available.astype(float)
    g['ecg_present']=(g.ecg_completeness.fillna(0).ge(.9)&g.ecg_valid.eq(1)).astype(float)
    mapping={'hr':'ppg_rate','hrv':'ppg_interval_rmssd','rrstd':'ppg_interval_std',
             'eda':'eda_mean','edav':'eda_diff_std','temp':'temp_mean','motion':'acc_std',
             'ppgq':'ppg_spectral_concentration','ecghr':'ecg_rate','ecghrv':'ecg_interval_rmssd',
             'ecgrrstd':'ecg_interval_std','ecgq':'ecg_spectral_concentration'}
    for name,source in mapping.items():
        g[name]=pd.to_numeric(g[source],errors='coerce').replace([np.inf,-np.inf],np.nan)
        valid=g.ecg_present.eq(1) if name.startswith('ecg') else g.wrist_present.eq(1)
        g.loc[~valid,name]=np.nan
        if name in ['hr','ecghr']:g.loc[~g[name].between(30,200),name]=np.nan
        if name in ['hrv','rrstd','eda','edav','motion','ecghrv','ecgrrstd']:
            g[name]=np.log1p(g[name].where(g[name]>=0))
    #55minutes between feature anchors +5minutes of source signal <=60min.
    for name in ['hr','eda','temp','ecghr']:
        g[name+'_dev']=g[name]-g[name].rolling('55min',closed='both',min_periods=3).median()
    return g.reset_index(drop=True)


def availability(frame,arm):
    return (frame.wrist_present.eq(1)|frame.ecg_present.eq(1)).to_numpy() if arm in ['pooled_fallback','pooled_mask_clock'] else frame.wrist_present.eq(1).to_numpy()


def fit_normalizer(train):
    normal=train[~train.label_low.astype(bool)]
    parameters={}
    for c in RAW+ECG+DEVIATIONS+['ecghr_dev']:
        values=normal[c].dropna()
        if len(values)<20:values=train[c].dropna()
        center=float(values.median()) if len(values) else 0.
        scale=float(values.quantile(.75)-values.quantile(.25)) if len(values) else 1.
        floor=1. if c in ['hr','ecghr','hr_dev','ecghr_dev'] else .1 if c in ['temp','temp_dev'] else .01
        parameters[c]={'center':center,'scale':max(scale,floor),'fit_rows':len(values)}
    eligible=normal[normal[['hr','motion']].notna().all(axis=1)]
    design=['motion']+CLOCK
    if len(eligible)>=30:
        x=eligible[design].to_numpy();center=x.mean(axis=0);scale=x.std(axis=0);scale[scale<1e-6]=1.
        model=Ridge(alpha=10).fit((x-center)/scale,eligible.hr)
        regression={'center':center.tolist(),'scale':scale.tolist(),'coef':model.coef_.tolist(),'intercept':float(model.intercept_),'fit_rows':len(eligible)}
    else:regression={'center':[0.,0.,0.],'scale':[1.,1.,1.],'coef':[0.,0.,0.],'intercept':parameters['hr']['center'],'fit_rows':len(eligible)}
    return {'parameters':parameters,'hr_activity_regression':regression,'training_rows':len(train),'normal_rows':len(normal)}


def transform(frame,state):
    output=frame[CLOCK+MASK].copy()
    for c,p in state['parameters'].items():output[c]=((frame[c]-p['center'])/p['scale']).clip(-8,8)
    r=state['hr_activity_regression']
    x=frame[['motion']+CLOCK].to_numpy()
    expected=((x-np.array(r['center']))/np.array(r['scale']))@np.array(r['coef'])+r['intercept']
    output['hr_residual']=((frame.hr.to_numpy()-expected)/state['parameters']['hr']['scale']).clip(-8,8)
    output['hr_eda_interaction']=output.hr_residual*output.eda
    return output


def smooth_scores(times,scores,policy):
    if policy not in POLICIES:raise ValueError(policy)
    alpha=.5 if policy.startswith('smooth_') else 1.
    result=np.full(len(scores),np.nan);state=None;last=None
    for i,(time,score) in enumerate(zip(times,scores)):
        if last is not None and time-last>7.5*NS_MINUTE:state=None
        if not np.isfinite(score):state=None
        else:
            state=score if state is None else alpha*score+(1-alpha)*state
            result[i]=state
        last=time
    return result


def alert_indices(times,scores,threshold,policy):
    active=False;ready=None;last=None;last_alert=None;high=low=0;alarms=[]
    for i,(time,score) in enumerate(zip(times,scores)):
        if last is not None and time-last>7.5*NS_MINUTE:
            active=False;ready=None;last_alert=None;high=low=0
        if policy=='legacy_edge':
            if not np.isfinite(score) or score<threshold:
                if active:ready=time+30*NS_MINUTE
                active=False
            elif not active:
                if ready is None or time>=ready:alarms.append(i)
                active=True
        elif not np.isfinite(score):
            active=False;high=low=0
        elif score<threshold:
            high=0;low+=1
            if low>=2:active=False
        else:
            high+=1;low=0
            permitted=last_alert is None or time-last_alert>=30*NS_MINUTE
            if permitted and ((not active and high>=2) or (active and policy=='smooth_remind30')):
                alarms.append(i);last_alert=time;active=True
        last=time
    return np.array(alarms,dtype=int)


def event_metrics(times,raw_scores,events,threshold,policy):
    scores=smooth_scores(times,raw_scores,policy)
    alarms=times[alert_indices(times,scores,threshold,policy)]
    events=[(s,e) for s,e in events if times[0]<=s<=times[-1]]
    used=set();delays=[];opportunities=0
    for start,end in events:
        opportunities+=int(np.isfinite(scores[(times>=start)&(times<=end)]).any())
        for i,time in enumerate(alarms):
            if i not in used and start<=time<=end:
                used.add(i);delays.append(float((time-start)/NS_MINUTE));break
    delta=np.diff(times)/NS_MINUTE;observed=(delta>0)&(delta<=7.5)
    minutes=float(delta[observed].sum());supported=np.isfinite(scores[:-1])&np.isfinite(scores[1:])
    return {'reference_events':len(events),'matched_events':len(used),'alarms':len(alarms),
            'unmatched_alarms':len(alarms)-len(used),'observation_hours':minutes/60,
            'event_recall':len(used)/len(events) if events else None,
            'event_precision':len(used)/len(alarms) if len(alarms) else None,
            'false_alerts_per_person_day':(len(alarms)-len(used))/(minutes/1440) if minutes else None,
            'coverage':float(delta[observed&supported].sum()/minutes) if minutes else None,
            'anchor_coverage':float(np.isfinite(scores).mean()),'events_with_input_opportunity':opportunities,
            'observable_event_ceiling':opportunities/len(events) if events else None,
            'conditional_event_recall':len(used)/opportunities if opportunities else None,
            'delay_median_minutes':float(np.median(delays)) if delays else None}


def aggregate(rows):
    keys=['event_recall','event_precision','coverage','anchor_coverage','observable_event_ceiling','conditional_event_recall']
    result={k:float(np.mean([r[k] for r in rows if r[k] is not None])) if any(r[k] is not None for r in rows) else None for k in keys}
    for k in ['reference_events','matched_events','alarms','unmatched_alarms','observation_hours','events_with_input_opportunity']:result[k]=sum(r[k] for r in rows)
    result['false_alerts_per_person_day']=result['unmatched_alarms']/(result['observation_hours']/24) if result['observation_hours'] else None
    return result
