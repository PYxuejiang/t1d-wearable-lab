"""Original PPG benchmark methods. Reference-assisted scoring is not a detector input."""
import numpy as np
from scipy import signal
from .ppg_morphology import short_features


def match_seconds(reference, predicted, tolerance=.1):
    a,b=np.asarray(reference,float),np.asarray(predicted,float)
    if not np.isfinite(a).all() or not np.isfinite(b).all() or np.any(np.diff(a)<=0) or np.any(np.diff(b)<=0):
        raise ValueError('Beat times must be finite, unique and increasing')
    i=j=0;pairs=[]
    while i<len(a) and j<len(b):
        d=b[j]-a[i]
        if d < -tolerance-1e-12:j+=1
        elif d > tolerance+1e-12:i+=1
        else:pairs.append((i,j));i+=1;j+=1
    return pairs


def detect_window(filtered, rate, method):
    x=np.asarray(filtered,float);offset=int(2*rate);x=x[offset:]
    if len(x)<rate*20 or not np.isfinite(x).all() or np.std(x)<1e-6:return np.array([],float)
    if method=='v5_peaks':
        peaks=signal.find_peaks(x,distance=int(.3*rate),prominence=.5*np.std(x))[0]
    elif method=='dual_average':
        # Fixed paper-inspired block rule, shared causal filter, no external source code.
        y=np.maximum(x,0)**2
        short=max(1,round(.111*rate));long=max(short,round(.667*rate))
        a=np.convolve(y,np.ones(short)/short,mode='same')
        b=np.convolve(y,np.ones(long)/long,mode='same')+.02*y.mean()
        edges=np.diff(np.r_[False,a>b,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
        candidates=[int(s+np.argmax(x[s:e])) for s,e in zip(starts,ends) if e-s>=short]
        chosen=[]
        for p in sorted(candidates,key=lambda p:(-x[p],p)):
            if all(abs(p-q)>=int(.3*rate) for q in chosen):chosen.append(p)
        peaks=np.array(sorted(chosen),int)
    else:raise ValueError(method)
    return (peaks+offset)/rate


def quality(filtered,rate):
    r=short_features(filtered,rate)
    values=[r['template_correlation'],r['periodicity']]
    a=[float(np.clip(v,0,1)) if np.isfinite(v) else 0. for v in values]
    return .6*a[0]+.4*a[1]


def median_hr(times):
    intervals=np.diff(times);valid=intervals[(intervals>=.3)&(intervals<=2.)]
    return float(60/np.median(valid)) if len(valid)>=5 else None


def metrics(reference,predicted,tolerance=.1):
    a,b=np.asarray(reference,float),np.asarray(predicted,float);pairs=match_seconds(a,b,tolerance)
    ppi=[]
    for (i,j),(k,l) in zip(pairs,pairs[1:]):
        if k==i+1 and l==j+1:ppi.append(abs((b[l]-b[j])-(a[k]-a[i]))*1000)
    rh,ph=median_hr(a),median_hr(b)
    return {'tp':len(pairs),'fn':len(a)-len(pairs),'fp':len(b)-len(pairs),
            'ppi_pairs':len(ppi),'reference_pairs':max(0,len(a)-1),'ppi_abs_sum_ms':float(sum(ppi)),
            'hr_error_sum':abs(ph-rh) if ph is not None and rh is not None else 0.,
            'hr_windows':int(ph is not None and rh is not None),'windows':1}


def summarize(items):
    keys=['tp','fn','fp','ppi_pairs','reference_pairs','ppi_abs_sum_ms','hr_error_sum','hr_windows','windows']
    s={k:sum(x[k] for x in items) for k in keys}
    ratio=lambda a,b:a/b if b else None
    s.update(f1=ratio(2*s['tp'],2*s['tp']+s['fn']+s['fp']),sensitivity=ratio(s['tp'],s['tp']+s['fn']),ppv=ratio(s['tp'],s['tp']+s['fp']),ppi_mae_ms=ratio(s['ppi_abs_sum_ms'],s['ppi_pairs']),ppi_pair_coverage=ratio(s['ppi_pairs'],s['reference_pairs']),hr_mae_bpm=ratio(s['hr_error_sum'],s['hr_windows']),hr_output_fraction=ratio(s['hr_windows'],s['windows']))
    return s


def score_window(row,method,lag,origin_zero=False,accepted=True):
    # A fixed cardiac-time core gives identical reference denominators across methods/lags.
    ref=np.asarray(row['reference'])+(1/700 if origin_zero else 0.)
    pred=np.asarray(row['detected'][method])-lag
    ref=ref[(ref>=2)&(ref<29)];pred=pred[(pred>=2)&(pred<29)] if accepted else np.array([])
    return metrics(ref,pred)


def select_lag(rows,grid):
    counts=[]
    for lag in grid:
        tp=sum(score_window(r,'v5_peaks',lag)['tp'] for r in rows)
        counts.append((tp,-abs(lag-.2),-lag,lag))
    return max(counts)[-1]
