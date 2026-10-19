"""Expert-boundary conditional fiducial pilot; not continuous beat detection."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np
from scipy import signal
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parents[1]
ARMS=['raw','causal5','offline12']


def locate(x,fs,bounds,arm):
    x=np.asarray(x,float)
    if arm!='raw':
        sos=signal.butter(3,[.5,5 if arm=='causal5' else 12],btype='bandpass',fs=fs,output='sos')
        x=signal.sosfilt(sos,x) if arm=='causal5' else signal.sosfiltfilt(sos,x)
    start,end=np.rint(np.asarray(bounds)*fs).astype(int)
    if not (0<=start<end<len(x)):return None
    peak=start+int(np.argmax(x[start:end]))
    slope=start+int(np.argmax(np.gradient(x,1/fs)[start:peak+1]))
    return {'pk':peak/fs,'u':slope/fs,'strict_order':bool(start<slope<peak<end)}


def reference(a,n,fs):
    os=np.asarray(a['os']['t'],float).reshape(-1)
    if len(os)!=2 or not np.isfinite(os).all() or not 0<=os[0]<os[1]<=(n-1)/fs:return None
    pk=np.asarray(a['pk']['t'],float).reshape(-1);pk=pk[(pk>os[0])&(pk<os[1])]
    u=np.asarray(a['u']['t'],float).reshape(-1)
    if len(pk)!=1 or len(u)!=1 or not np.isfinite(u).all() or not os[0]<u[0]<pk[0]<os[1]:return None
    return {'pk':float(pk[0]),'u':float(u[0])}


def metrics(errors,total):
    x=np.asarray(errors,float)*1000
    return {'n':len(x),'reference_coverage':len(x)/total,'mae_ms':float(abs(x).mean()),'median_abs_ms':float(np.median(abs(x))),
            'p95_abs_ms':float(np.quantile(abs(x),.95)),'bias_ms':float(x.mean()),
            'within_ms':{str(t):float(np.mean(abs(x)<=t+1e-9)) for t in [10,20,50]}}


def main():
    out=ROOT/'outputs/ppg_fiducial_v1';out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise RuntimeError('Preserve previous results')
    raw=(ROOT/'data/ppg_bp_annot/PPG-BP_annot.zip').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='ea35c29a6afcf494c4f233e0aec94b6d9cb16f39406891e1e910b70fa1779932'
    z=zipfile.ZipFile(io.BytesIO(raw))
    def read(p):return loadmat(io.BytesIO(z.read(p)),simplify_cells=True)
    signals=read('PPG-BP_ref1.mat')['ppg_data']
    annotations={w:{r['name']:r['annot'] for r in read(f'{w}final_PPG-BP_annot/{w}final_PPG-BP_annot.mat')['fiducial_annot']} for w in ['MG','PC']}
    names=sorted([r['name'] for r in signals],key=lambda name:hashlib.sha256(('PPG_FIDUCIAL1/'+name).encode()).hexdigest())
    assert len(names)==len(set(names))==219
    dev=set(names[:70]);local=[]
    for s in signals:
        name=s['name'];fs=s['fs'];n=len(s['sig']);bounds=annotations['MG'][name]['os']['t']
        refs={w:reference(annotations[w][name],n,fs) for w in annotations}
        assert refs['MG'] is not None
        # Only waveform, sampling rate and explicit expert boundary enter locate.
        predictions={a:locate(s['sig'],fs,bounds,a) for a in ARMS}
        assert all(p is not None for p in predictions.values())
        local.append({'name':name,'phase':'development' if name in dev else 'evaluation','reference':refs,'predictions':predictions})
    public={'stage':'PPG_FIDUCIAL1','scope':'Exploratory finger-PPG expert-boundary localization; not wrist, continuous or disease validation',
            'counts':{'development':70,'evaluation':149,'total':219},'results':{},'paired':{},
            'archive_sha256':hashlib.sha256(raw).hexdigest(),
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/run_ppg_fiducial.py','docs/METHOD_PPG_FIDUCIAL1.zh-CN.md']}}
    for phase,total in [('development',70),('evaluation',149)]:
        rows=[r for r in local if r['phase']==phase];assert len(rows)==total
        public['results'][phase]={}
        for arm in ARMS:
            result={'output_fraction':1.,'strict_order_fraction':float(np.mean([r['predictions'][arm]['strict_order'] for r in rows]))}
            for who in ['MG','PC']:
                result[who]={f:metrics([r['predictions'][arm][f]-r['reference'][who][f] for r in rows if r['reference'][who] is not None],total) for f in ['pk','u']}
            public['results'][phase][arm]=result
    objective={a:float(np.mean([public['results']['development'][a]['MG'][f]['mae_ms'] for f in ['pk','u']])) for a in ARMS}
    selected=min(ARMS,key=lambda a:(objective[a],ARMS.index(a)))
    public['selection']={'selected':selected,'development_mg_joint_mae_ms':objective,'evaluation_used':False}
    for who in ['MG','PC']:
        rows=[r for r in local if r['phase']=='evaluation' and r['reference'][who] is not None]
        public['paired'][who]={}
        for f in ['pk','u','joint']:
            fields=['pk','u'] if f=='joint' else [f]
            diff=np.array([np.mean([(abs(r['predictions'][selected][k]-r['reference'][who][k])-abs(r['predictions']['causal5'][k]-r['reference'][who][k]))*1000 for k in fields]) for r in rows])
            boot=np.random.default_rng(20261019).choice(diff,(10000,len(diff)),replace=True).mean(axis=1)
            public['paired'][who][f]={'n':len(diff),'selected_minus_causal5_mae_ms':float(diff.mean()),'95_interval':np.quantile(boot,[.025,.975]).tolist()}
    (out/'records_local.json').write_text(json.dumps(local,indent=2,allow_nan=False))
    (ROOT/'docs/acceptance/PPG_FIDUCIAL1.json').write_text(json.dumps(public,indent=2,allow_nan=False))
    print(json.dumps(public['selection']));print(json.dumps(public['paired'],indent=2))


if __name__=='__main__':main()
