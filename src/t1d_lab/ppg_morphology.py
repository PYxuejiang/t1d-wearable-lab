"""Original lightweight short-window morphology; descriptors, not validated HRV."""
import numpy as np
from scipy import signal,stats

QUALITY=['pulse_support','valid_interval_fraction','valid_pair_fraction','periodicity','band_fraction','template_correlation','flat_fraction']
MORPH=['pulse_rate','ppi_sd','ppi_rmssd','width_fraction','rise_fraction','area_fraction','pulse_amplitude_cv','skew']


def interval_stats(peaks,rate):
    intervals=np.diff(peaks)/rate
    valid=(intervals>=.3)&(intervals<=2)
    adjacent=valid[:-1]&valid[1:]
    selected=intervals[valid]
    return {'pulse_rate':float(60/np.median(selected)) if len(selected)>=5 else np.nan,
            'ppi_sd':float(np.std(selected)) if len(selected)>=5 else np.nan,
            'ppi_rmssd':float(np.sqrt(np.mean(np.diff(intervals)[adjacent]**2))) if adjacent.sum()>=4 else np.nan,
            'valid_interval_fraction':float(valid.mean()) if len(valid) else 0.,
            'valid_pair_fraction':float(adjacent.mean()) if len(adjacent) else 0.}


def short_features(x,rate):
    r={k:np.nan for k in QUALITY+MORPH};r.update(pulse_support=0.,flat_fraction=1.)
    x=np.asarray(x,float)
    if len(x)<rate*20 or not np.isfinite(x).all() or np.std(x)<1e-6:return r
    r['flat_fraction']=float(np.mean(np.abs(np.diff(x))<1e-8))
    x=x[int(rate*2):];sd=np.std(x)
    if sd<1e-6:return r
    peaks,_=signal.find_peaks(x,distance=int(.3*rate),prominence=.5*sd)
    r.update(interval_stats(peaks,rate));r['pulse_support']=float(np.isfinite(r['pulse_rate']))
    z=(x-x.mean())/sd;r['skew']=float(stats.skew(z))
    corr=signal.correlate(z,z,mode='full',method='fft')[len(z)-1:]/len(z)
    r['periodicity']=float(np.max(corr[int(.3*rate):int(2*rate)+1]))
    f,p=signal.welch(x,fs=rate,nperseg=min(len(x),int(10*rate)))
    total=p[(f>=.5)&(f<=5)].sum();r['band_fraction']=float(p[(f>=.5)&(f<=3.5)].sum()/total) if total>0 else np.nan
    beats=[];rises=[];areas=[];widths=[];amplitudes=[]
    for i in range(1,len(peaks)-1):
        a,b,c=peaks[i-1:i+2]
        if not (.3<=((b-a)/rate)<=2 and .3<=((c-b)/rate)<=2):continue
        left=a+int(np.argmin(x[a:b]));right=b+int(np.argmin(x[b:c]))
        if right<=left+3:continue
        pulse=x[left:right+1];baseline=np.linspace(pulse[0],pulse[-1],len(pulse));pulse=pulse-baseline
        amp=float(pulse.max())
        if amp<=1e-8:continue
        shape=pulse/amp;peak=int(np.argmax(shape))
        beats.append(np.interp(np.linspace(0,1,64),np.linspace(0,1,len(shape)),shape))
        rises.append(peak/(len(shape)-1));areas.append(float(np.mean(shape)))
        widths.append(float(np.mean(shape>=.5)));amplitudes.append(amp)
    if len(beats)>=5:
        beats=np.asarray(beats);template=np.median(beats,axis=0)
        correlations=[np.corrcoef(b,template)[0,1] for b in beats if np.std(b)>1e-8 and np.std(template)>1e-8]
        r.update(template_correlation=float(np.median(correlations)) if correlations else np.nan,
                 width_fraction=float(np.median(widths)),rise_fraction=float(np.median(rises)),area_fraction=float(np.median(areas)),
                 pulse_amplitude_cv=float(np.std(amplitudes)/np.mean(amplitudes)))
    return r


def window_features(values,rate=64):
    values=np.asarray(values,float);empty={f'pm_{k}_{s}':np.nan for k in QUALITY+MORPH for s in ['median','iqr']}
    empty['pm_short_valid_fraction']=0.
    if len(values)!=int(rate*300) or not np.isfinite(values).all():return empty
    filt=signal.sosfilt(signal.butter(3,[.5,5],btype='bandpass',fs=rate,output='sos'),values)
    rows=[short_features(filt[i*int(30*rate):(i+1)*int(30*rate)],rate) for i in range(10)]
    for key in QUALITY+MORPH:
        a=np.array([r[key] for r in rows]);a=a[np.isfinite(a)]
        if len(a):empty[f'pm_{key}_median']=float(np.median(a));empty[f'pm_{key}_iqr']=float(np.quantile(a,.75)-np.quantile(a,.25))
    empty['pm_short_valid_fraction']=float(np.mean([r['pulse_support'] for r in rows]));return empty


def sample_bounds(start_epoch,anchor_epoch,rate):
    """(anchor-300s, anchor], robust to integer epoch seconds supplied by E4."""
    right=int(np.floor((anchor_epoch-start_epoch)*rate))+1
    return right-int(300*rate),right
