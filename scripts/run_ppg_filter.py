"""Fixed frequency/filter-family contrasts and development-only timestamp centering."""
import hashlib,io,json,zipfile
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat
from run_ppg_fiducial import metrics

ROOT=Path(__file__).resolve().parents[1]
ARMS=['raw','causal5','offline5','causal12','offline12','causal5_centered','causal12_centered']
CONTRASTS=[('offline12','offline5'),('causal12_centered','causal5_centered'),('causal5_centered','causal5'),('causal12_centered','causal12'),('offline12','causal12_centered')]

def locate(x,fs,bounds,arm):
    cutoff=int(arm.replace('causal','').replace('offline',''))
    sos=signal.butter(3,[.5,cutoff],btype='bandpass',fs=fs,output='sos')
    y=signal.sosfilt(sos,x) if arm.startswith('causal') else signal.sosfiltfilt(sos,x)
    start,end=np.rint(np.array(bounds)*fs).astype(int)
    peak=start+int(np.argmax(y[start:end]))
    up=start+int(np.argmax(np.gradient(y,1/fs)[start:peak+1]))
    return {'pk':peak/fs,'u':up/fs,'strict_order':bool(start<up<peak<end)}

def main():
    out=ROOT/'outputs/ppg_filter_v1';out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise RuntimeError('Preserve completed results')
    previous=ROOT/'outputs/ppg_fiducial_v1/records_local.json'
    local=json.loads(previous.read_text())
    prior=json.loads((ROOT/'docs/acceptance/PPG_FIDUCIAL1.json').read_text())
    assert prior['verification']['status']=='passed'
    raw=(ROOT/'data/ppg_bp_annot/PPG-BP_annot.zip').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==prior['archive_sha256']
    archive=zipfile.ZipFile(io.BytesIO(raw))
    def read(p):return loadmat(io.BytesIO(archive.read(p)),simplify_cells=True)
    signals={s['name']:s for s in read('PPG-BP_ref1.mat')['ppg_data']}
    annot={r['name']:r['annot'] for r in read('MGfinal_PPG-BP_annot/MGfinal_PPG-BP_annot.mat')['fiducial_annot']}
    for r in local:
        s=signals[r['name']];bounds=annot[r['name']]['os']['t']
        r['bounds']=(np.rint(np.asarray(bounds)*s['fs'])/s['fs']).tolist()
        for arm in ['offline5','causal12']:r['predictions'][arm]=locate(s['sig'],s['fs'],bounds,arm)
    dev=[r for r in local if r['phase']=='development'];assert len(dev)==70
    shifts={a:{f:float(np.median([r['predictions'][a][f]-r['reference']['MG'][f] for r in dev])) for f in ['pk','u']} for a in ['causal5','causal12']}
    for r in local:
        for a in shifts:
            pred={f:r['predictions'][a][f]-shifts[a][f] for f in ['pk','u']}
            pred['strict_order']=bool(r['bounds'][0]<pred['u']<pred['pk']<r['bounds'][1])
            r['predictions'][a+'_centered']=pred
    public={'stage':'PPG_FILTER1','scope':'Exploratory expert-boundary finger PPG; global timestamp centering is not continuous detection or PPI improvement',
            'counts':prior['counts'],'development_shifts_ms':{a:{f:v*1000 for f,v in d.items()} for a,d in shifts.items()},
            'selection':'No winner selection; all fixed contrasts reported','results':{},'paired':{},'archive_sha256':prior['archive_sha256'],
            'previous_local_sha256':hashlib.sha256(previous.read_bytes()).hexdigest(),
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/run_ppg_filter.py','scripts/run_ppg_fiducial.py','docs/METHOD_PPG_FILTER1.zh-CN.md']}}
    for phase in ['development','evaluation']:
        rows=[r for r in local if r['phase']==phase];public['results'][phase]={}
        for arm in ARMS:
            result={'output_fraction':1.,'strict_order_fraction':float(np.mean([r['predictions'][arm]['strict_order'] for r in rows])),
                    'outside_boundary_fraction':float(np.mean([any(not r['bounds'][0]<r['predictions'][arm][f]<r['bounds'][1] for f in ['pk','u']) for r in rows]))}
            for who in ['MG','PC']:
                result[who]={f:metrics([r['predictions'][arm][f]-r['reference'][who][f] for r in rows if r['reference'][who] is not None],len(rows)) for f in ['pk','u']}
            public['results'][phase][arm]=result
    for a,b in CONTRASTS:
        key=a+'__minus__'+b;public['paired'][key]={}
        for who in ['MG','PC']:
            rows=[r for r in local if r['phase']=='evaluation' and r['reference'][who] is not None]
            public['paired'][key][who]={}
            for f in ['pk','u','joint']:
                fields=['pk','u'] if f=='joint' else [f]
                diff=np.array([np.mean([(abs(r['predictions'][a][k]-r['reference'][who][k])-abs(r['predictions'][b][k]-r['reference'][who][k]))*1000 for k in fields]) for r in rows])
                boot=np.random.default_rng(20261019).choice(diff,(10000,len(diff)),replace=True).mean(axis=1)
                public['paired'][key][who][f]={'n':len(diff),'mae_difference_ms':float(diff.mean()),'95_interval':np.quantile(boot,[.025,.975]).tolist()}
    (out/'records_local.json').write_text(json.dumps(local,indent=2,allow_nan=False))
    (ROOT/'docs/acceptance/PPG_FILTER1.json').write_text(json.dumps(public,indent=2,allow_nan=False))
    print('Development shifts (ms):',public['development_shifts_ms'])
    for arm,result in public['results']['evaluation'].items():print(arm,{f:round(result['MG'][f]['mae_ms'],4) for f in ['pk','u']},'outside',result['outside_boundary_fraction'])

if __name__=='__main__':main()
