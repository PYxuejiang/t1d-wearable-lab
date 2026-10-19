"""Fixed candidate morphology and interval audit. No reference in feature functions."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat
from run_ppg_quality_dev import auc
ROOT=Path(__file__).resolve().parents[1]
FEATURES=('template','interval','one_minus_sqi')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalized(v):
    v=np.asarray(v,float)-np.mean(v);norm=np.linalg.norm(v)
    return v/norm if norm>1e-12 else np.zeros_like(v)
def shapes(x,peaks):
    peaks=np.rint(np.asarray(peaks)*64).astype(int);out=[]
    for j,p in enumerate(peaks):
        left=int(np.ceil((peaks[j-1]+p)/2)) if j else 0
        right=int(np.floor((p+peaks[j+1])/2)) if j+1<len(peaks) else len(x)-1
        assert 0<=left<=p<=right<len(x)
        out.append(normalized(np.interp(np.linspace(left,right,64),np.arange(left,right+1),x[left:right+1])))
    return np.asarray(out).reshape(-1,64)
def interval_risk(ups,median):
    intervals=np.diff(ups);out=[];missing=one_side=0
    for j in range(len(ups)):
        neighbors=[]
        if j:neighbors.append(intervals[j-1])
        if j<len(intervals):neighbors.append(intervals[j])
        valid=[v for v in neighbors if np.isfinite(v) and v>0]
        missing+=int(not valid);one_side+=int(len(valid)==1)
        out.append(float(max(abs(np.log(np.asarray(valid)/median)))) if valid else 2.)
    return out,missing,one_side
def controls():
    x=np.sin(np.linspace(0,12,1920));p=[3.,4.,5.,6.]
    assert np.allclose(shapes(x,p),shapes(x*3+7,p),atol=1e-12)
    a=interval_risk([1.,2.,3.2],1.1)[0];b=interval_risk([3.,6.,9.6],3.3)[0];assert np.allclose(a,b)
    assert not normalized(np.ones(64)).any() and interval_risk([1.],1.)[0]==[2.]
    return {'shape_offset_scale_invariant':True,'interval_time_scale_invariant':True,'constant_and_no_neighbor_defaults':True}
def main():
    out=ROOT/'outputs/ppg_local_dev_v1';out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise RuntimeError('Preserve previous attempts')
    controls_result=controls()
    inputs=['outputs/ppg_upstroke_dev_v1/windows_local.json','outputs/ppg_quality_dev_v1/records_local.json','docs/acceptance/PPG_QUALITY_DEV1.json','docs/acceptance/PPG_DALIA_AUDIT1.json']
    rows=json.loads((ROOT/inputs[0]).read_text());quality=json.loads((ROOT/inputs[1]).read_text());prior=json.loads((ROOT/inputs[2]).read_text());audit=json.loads((ROOT/inputs[3]).read_text())
    assert prior['verification']['status']=='passed' and len(rows)==211 and len(quality)==10
    assert {r['subject'] for r in rows}=={'S1','S2','S3','S4','S5'}
    signals={};data_hash={}
    for entry in audit['files']:
        path=ROOT/'data/ppg_dalia_mat'/entry['file'];assert sha(path)==entry['sha256'];data_hash[entry['file']]=sha(path)
        for rec in loadmat(path,simplify_cells=True)['data']:
            key=str(rec['fix']['subj_name'])+'/'+entry['activity']
            if key not in {r['key'] for r in quality}:continue
            assert rec['ppg']['fs']==64
            signals[key]=signal.sosfilt(signal.butter(3,[.5,5],btype='bandpass',fs=64,output='sos'),np.asarray(rec['ppg']['v'],float))
    local=[]
    for q in quality:
        rr=[r for r in rows if r['key']==q['key']];sh={}
        for r in rr:
            x=signals[r['key']][r['start']*64:(r['start']+30)*64];sh[r['start']]=shapes(x,r['detected']['v5_peaks'])
        template=normalized(np.median(np.concatenate([sh[r['start']] for r in rr if r['start']<120]),axis=0))
        calibration_intervals=np.concatenate([np.diff(r['upstroke']) for r in rr if r['start']<120]);median=float(np.median(calibration_intervals[calibration_intervals>0]))
        item={'key':q['key'],'subject':q['subject'],'activity':q['activity'],'template':template.tolist(),'median_interval':median,'windows':[],
              'candidate_count':0,'zero_shape':0,'zero_template':int(np.linalg.norm(template)<1e-12),'no_neighbor':0,'one_side':0}
        for r in rr:
            mat=sh[r['start']];norms=np.linalg.norm(mat,axis=1);risks=np.clip(1-mat@template,0,2)
            risks[(norms<1e-12)|(np.linalg.norm(template)<1e-12)]=2
            intervals,missing,one=interval_risk(r['upstroke'],median)
            item['candidate_count']+=len(mat);item['zero_shape']+=int((norms<1e-12).sum());item['no_neighbor']+=missing;item['one_side']+=one
            item['windows'].append({'start':r['start'],'scores':{'template':risks.tolist(),'interval':intervals,'one_minus_sqi':[1-r['sqi']]*len(mat)}})
        scored={w['start']:w for w in item['windows']};labels=[];features={k:[] for k in FEATURES}
        for w in q['windows']:
            labels.extend(w['unmatched'])
            for k in FEATURES:features[k].extend(scored[w['start']]['scores'][k][j] for j in w['indices'])
        item['auc']={k:auc(labels,features[k]) for k in FEATURES};assert abs(item['auc']['one_minus_sqi']-q['auc']['one_minus_sqi'])<1e-12
        item['tail_candidates']=len(labels);local.append(item)
    public={'stage':'PPG_LOCAL_DEV1','scope':'Seen development candidate risk ranking; no rejection or disease validation','subjects':5,'windows':211,'tail_candidates':sum(r['tail_candidates'] for r in local),
        'synthetic':controls_result,'by_activity':{},'subject_auc':{},'difference_vs_sqi':{},'input_sha256':{p:sha(ROOT/p) for p in inputs},'data_sha256':data_hash,
        'source_sha256':{p:sha(ROOT/p) for p in ['scripts/run_ppg_local_dev.py','scripts/run_ppg_quality_dev.py','docs/METHOD_PPG_LOCAL_DEV1.zh-CN.md']}}
    for activity in ('sitting','walking'):
        rr=[r for r in local if r['activity']==activity]
        public['by_activity'][activity]={'records':len(rr),**{k:sum(r[k] for r in rr) for k in ('candidate_count','tail_candidates','zero_shape','zero_template','no_neighbor','one_side')},
            'auc':{k:{'mean':float(np.mean([r['auc'][k] for r in rr if r['auc'][k] is not None])) if any(r['auc'][k] is not None for r in rr) else None,'valid_records':sum(r['auc'][k] is not None for r in rr)} for k in FEATURES}}
    def summarize(values):
        if not values:return {'mean':None,'95_interval':None,'subjects':0}
        boot=np.random.default_rng(20261020).choice(values,(10000,len(values)),replace=True).mean(axis=1)
        return {'mean':float(np.mean(values)),'95_interval':np.quantile(boot,[.025,.975]).tolist(),'subjects':len(values)}
    for k in FEATURES:
        values=[];diff=[]
        for sub in sorted({r['subject'] for r in local}):
            rr=[r for r in local if r['subject']==sub]
            if all(r['auc'][k] is not None for r in rr):values.append(np.mean([r['auc'][k] for r in rr]))
            if all(r['auc'][k] is not None and r['auc']['one_minus_sqi'] is not None for r in rr):diff.append(np.mean([r['auc'][k]-r['auc']['one_minus_sqi'] for r in rr]))
        public['subject_auc'][k]=summarize(values)
        if k!='one_minus_sqi':public['difference_vs_sqi'][k]=summarize(diff)
    (out/'records_local.json').write_text(json.dumps(local,allow_nan=False))
    (ROOT/'docs/acceptance/PPG_LOCAL_DEV1.json').write_text(json.dumps(public,indent=2,allow_nan=False))
    print(json.dumps({'by_activity':public['by_activity'],'differences':public['difference_vs_sqi']},indent=2))
if __name__=='__main__':main()
