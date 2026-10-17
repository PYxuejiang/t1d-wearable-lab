"""Fixed non-CGM feature schema and honest validation-only score calibration."""
import numpy as np
import pandas as pd
from scipy.special import expit,logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve

WEARABLE=[f'hr_{n}min_rolling' for n in [5,10,30,60]]+[
    'last_measured_hrv_15min','hrv_change_15min','last_measured_ox','last_measured_rr']+[
    f'{kind}_rollingsum_{n}min' for kind in ['step_count','active_energy'] for n in [5,10,30,60]]
CONTEXT=['IOB','time_since_lastmeal_ord']
CLOCK=['sin_hour','cos_hour']
SETS={'clock':CLOCK,'context_time':CONTEXT+CLOCK,'wearable_time':WEARABLE+CLOCK,'combined':WEARABLE+CONTEXT+CLOCK}


def validate_protocol(config):
    # Nominal source-row audit only; full source timestamps remain unavailable.
    if 2*config['purge_rows']+1<=240+15:
        raise ValueError('Insufficient row separation for 240-minute context plus15-minute label support')
    if not set(config['feature_sets']).issubset(SETS):raise ValueError('Unregistered contextual feature set')


def prepare(frame):
    f=frame.copy()
    required=set(WEARABLE+CLOCK+['hypoglycemia','hour'])
    if not required.issubset(f):raise ValueError('Unexpected source sensor/label schema')
    missing=[c for c in CONTEXT if c not in f]
    for c in missing:f[c]=np.nan
    for c in WEARABLE:
        if c.startswith(('hr_','last_measured_hrv','last_measured_ox','last_measured_rr')):
            f.loc[f[c].eq(0),c]=np.nan
    f['available']=f[WEARABLE].notna().any(axis=1)
    if not f.hypoglycemia.dropna().isin([0,1]).all():raise ValueError('Unknown source reference encoding')
    return f,missing


def fit_calibration(scores,labels):
    scores=np.asarray(scores,dtype=float);labels=np.asarray(labels,dtype=float)
    valid=np.isfinite(scores)&np.isfinite(labels);p=scores[valid];y=labels[valid]
    prior=float(y.mean()) if len(y) else 0.
    record={'fit_rows':len(y),'positive_rows':int(y.sum()),'validation_prevalence':prior,'type':'constant','reason':'single_class_or_empty_validation','slope':0.,'intercept':None}
    if len(np.unique(y))==2:
        model=LogisticRegression(C=1,random_state=20261016).fit(logit(np.clip(p,1e-6,1-1e-6)).reshape(-1,1),y)
        slope=float(model.coef_[0,0]);intercept=float(model.intercept_[0])
        record.update(slope=slope,intercept=intercept)
        if slope>0:record.update(type='sigmoid',reason=None)
        else:record['reason']='nonpositive_validation_slope_no_ranking_flip'
    return record


def calibrated_scores(scores,record):
    p=np.asarray(scores,dtype=float);out=np.full(len(p),np.nan);valid=np.isfinite(p)
    if record['type']=='sigmoid':out[valid]=expit(record['slope']*logit(np.clip(p[valid],1e-6,1-1e-6))+record['intercept'])
    else:out[valid]=record['validation_prevalence']
    return out


def threshold_on_validation(labels,scores):
    y=np.asarray(labels,dtype=float);p=np.asarray(scores,dtype=float);valid=np.isfinite(y)&np.isfinite(p);y=y[valid];p=p[valid]
    if len(np.unique(y))<2:return 1.001
    fpr,tpr,threshold=roc_curve(y,p)
    feasible=np.flatnonzero((fpr<=.2)&np.isfinite(threshold))
    return float(threshold[max(feasible,key=lambda i:tpr[i]-fpr[i])]) if len(feasible) else 1.001
