"""Causal temporal summaries and validation-only alarm search for v2."""
import numpy as np
import pandas as pd
from .brist1d import backward_values
from .evaluation import split_masks

KINDS=['ppg','acc','eda','temp']


def features(frame,include_device=False):
    g=frame.sort_values('decision_time').copy().set_index('decision_time',drop=False)
    prefixes=KINDS+(['chest','wrist'] if include_device else [])
    base=sorted(c for c in g.select_dtypes(include='number') if any(c.startswith(k+'_') for k in prefixes) and not c.endswith('_available'))
    g['hour_sin']=np.sin(2*np.pi*(g.index.hour+g.index.minute/60)/24)
    g['hour_cos']=np.cos(2*np.pi*(g.index.hour+g.index.minute/60)/24)
    dynamic=[]
    for c in base:
        if c.endswith(('valid','completeness')):continue
        # Earlier windows themselves reach back five minutes, so lag capped at 55.
        for minutes in ([10,25,50] if include_device else [15,30,55]):
            name=f'{c}_lag{minutes}'
            g[name]=backward_values(g[c].dropna(),g.index-pd.Timedelta(minutes=minutes),5 if include_device else 0)
            dynamic.append(name)
        for minutes in [15,60]:
            name=f'{c}_pastmean{minutes}'
            g[name]=g[c].rolling(f'{minutes-5}min',closed='both',min_periods=2).mean()
            dynamic.append(name)
        name=f'{c}_deviation';g[name]=g[c]-g[f'{c}_pastmean60'];dynamic.append(name)
    g['available']=True
    for kind in KINDS:g['available'] &= g[kind+'_completeness'].fillna(0).ge(.9)
    g['available'] &= g.ppg_valid.eq(1)
    g['split']='purged'
    for key,mask in split_masks(g.index,g.index[0],g.index[-1],history_minutes=65 if include_device else 60,horizon_minutes=0,confirmation_minutes=15).items():g.loc[mask,'split']=key
    sets={'clock':['hour_sin','hour_cos'],'static':base,'dynamic':base+dynamic,'dynamic_time':base+dynamic+['hour_sin','hour_cos']}
    return g.reset_index(drop=True),sets


def past_smooth(times,scores,span):
    output=[];state=None;last=None
    alpha=2/(span+1)
    for t,score in zip(times,scores):
        if last is not None and (t-last).total_seconds()>450:state=None
        if not np.isfinite(score):output.append(np.nan);state=None
        else:
            state=score if state is None else alpha*score+(1-alpha)*state
            output.append(state)
        last=t
    return np.asarray(output)
