"""Rebuild all filter predictions from MATLAB objects without importing the runner."""
import hashlib,io,json,zipfile
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat
from verify_ppg_fiducial import equal, reference, summary

ROOT=Path(__file__).resolve().parents[1]
BASE=('raw','causal5','offline5','causal12','offline12')
ARMS=BASE+('causal5_centered','causal12_centered')
PAIRS=(('offline12','offline5'),('causal12_centered','causal5_centered'),('causal5_centered','causal5'),('causal12_centered','causal12'),('offline12','causal12_centered'))

def localize(x,fs,bounds,arm):
    y=np.asarray(x,float)
    if arm!='raw':
        high=5 if arm.endswith('5') else 12
        sos=signal.butter(N=3,Wn=[.5,high],fs=fs,btype='bandpass',output='sos')
        y=signal.sosfilt(sos,y) if arm.startswith('causal') else signal.sosfiltfilt(sos,y)
    start,end=map(lambda t:round(float(t)*fs),bounds)
    peak=max(range(start,end),key=lambda i:(y[i],-i))
    def gradient(i):
        lo=max(0,i-1);hi=min(len(y)-1,i+1)
        return (y[hi]-y[lo])*fs/(hi-lo)
    up=max(range(start,peak+1),key=lambda i:(gradient(i),-i))
    return {'pk':peak/fs,'u':up/fs,'strict_order':bool(start<up<peak<end)}

def main():
    target=ROOT/'docs/acceptance/PPG_FILTER1.json';public=json.loads(target.read_text())
    for name,h in public['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
    previous=ROOT/'outputs/ppg_fiducial_v1/records_local.json'
    assert hashlib.sha256(previous.read_bytes()).hexdigest()==public['previous_local_sha256']
    old=json.loads(previous.read_text())
    raw=(ROOT/'data/ppg_bp_annot/PPG-BP_annot.zip').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==public['archive_sha256']
    archive=zipfile.ZipFile(io.BytesIO(raw))
    def read(name):return loadmat(io.BytesIO(archive.read(name)),squeeze_me=True,struct_as_record=False)
    signals=read('PPG-BP_ref1.mat')['ppg_data']
    labels={w:{a.name:a.annot for a in read(f'{w}final_PPG-BP_annot/{w}final_PPG-BP_annot.mat')['fiducial_annot']} for w in ('MG','PC')}
    names=[s.name for s in signals];assert len(set(names))==219
    dev=set(sorted(names,key=lambda n:hashlib.sha256(('PPG_FIDUCIAL1/'+n).encode()).hexdigest())[:70])
    rows=[]
    for s in signals:
        bounds=np.atleast_1d(labels['MG'][s.name].os.t)
        rows.append({'name':s.name,'phase':'development' if s.name in dev else 'evaluation',
                     'bounds':[round(float(t)*s.fs)/s.fs for t in bounds],
                     'reference':{w:reference(labels[w][s.name],len(s.sig),s.fs) for w in labels},
                     'predictions':{a:localize(s.sig,s.fs,bounds,a) for a in BASE}})
    for r,o in zip(rows,old):
        equal({k:r[k] for k in ('name','phase','reference')},{k:o[k] for k in ('name','phase','reference')})
        equal({a:r['predictions'][a] for a in ('raw','causal5','offline12')},o['predictions'])
    shifts={a:{} for a in ('causal5','causal12')}
    for a in shifts:
        for f in ('pk','u'):
            errors=sorted(r['predictions'][a][f]-r['reference']['MG'][f] for r in rows if r['name'] in dev)
            assert len(errors)==70
            shifts[a][f]=(errors[34]+errors[35])/2
    equal(public['development_shifts_ms'],{a:{f:v*1000 for f,v in d.items()} for a,d in shifts.items()})
    for r in rows:
        for a in shifts:
            p={f:r['predictions'][a][f]-shifts[a][f] for f in ('pk','u')}
            p['strict_order']=bool(r['bounds'][0]<p['u']<p['pk']<r['bounds'][1])
            r['predictions'][a+'_centered']=p
    equal(json.loads((ROOT/'outputs/ppg_filter_v1/records_local.json').read_text()),rows)
    results={}
    equal(public['counts'],{'development':70,'evaluation':149,'total':219})
    for phase,count in [('development',70),('evaluation',149)]:
        subset=[r for r in rows if r['phase']==phase];assert len(subset)==count
        results[phase]={}
        for a in ARMS:
            stats={'output_fraction':sum(r['predictions'][a] is not None for r in subset)/count,
                   'strict_order_fraction':sum(r['predictions'][a]['strict_order'] for r in subset)/count,
                   'outside_boundary_fraction':sum(any(not r['bounds'][0]<r['predictions'][a][f]<r['bounds'][1] for f in ('pk','u')) for r in subset)/count}
            for w in labels:stats[w]={f:summary([r['predictions'][a][f]-r['reference'][w][f] for r in subset if r['reference'][w] is not None],count) for f in ('pk','u')}
            results[phase][a]=stats
    equal(public['results'],results)
    pairs={}
    for a,b in PAIRS:
        key=a+'__minus__'+b;pairs[key]={}
        for w in labels:
            subset=[r for r in rows if r['phase']=='evaluation' and r['reference'][w] is not None];pairs[key][w]={}
            for f in ('pk','u','joint'):
                fields=('pk','u') if f=='joint' else (f,)
                diff=np.asarray([sum((abs(r['predictions'][a][k]-r['reference'][w][k])-abs(r['predictions'][b][k]-r['reference'][w][k]))*1000 for k in fields)/len(fields) for r in subset])
                idx=np.random.default_rng(20261019).integers(len(diff),size=(10000,len(diff)))
                pairs[key][w][f]={'n':len(diff),'mae_difference_ms':float(diff.mean()),'95_interval':np.percentile(diff[idx].mean(axis=1),[2.5,97.5]).tolist()}
    equal(public['paired'],pairs)
    # Synthetic mathematical controls: constant centering removes known offset,
    # but cannot change adjacent intervals of the same fiducial sequence.
    truth=np.array([.2,1.1,2.3,3.1]);pred=truth+.064
    corrected=pred-np.median(pred-truth)
    assert np.allclose(corrected,truth,atol=1e-12)
    assert np.allclose(np.diff(corrected),np.diff(pred),atol=1e-12)
    public['verification']={'status':'passed','entries':219,'predictions_recomputed':1533,'metric_groups_checked':56,
                            'paired_intervals_checked':30,'development_constants_checked':4,'synthetic_controls':2,
                            'old_arms_reproduced':3,'shared_numerical_dependency':'SciPy filter kernels; reused independent reference/metric helpers',
                            'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            'helper_sha256':hashlib.sha256((ROOT/'scripts/verify_ppg_fiducial.py').read_bytes()).hexdigest()}
    target.write_text(json.dumps(public,indent=2,allow_nan=False));print(json.dumps(public['verification'],indent=2))

if __name__=='__main__':main()
