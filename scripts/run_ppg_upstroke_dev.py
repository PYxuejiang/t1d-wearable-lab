"""PPG-only candidate upstroke localization; ECG is used solely for scoring alignment."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from audit_ppg_stability_dev import select,score,SEGMENTS

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def upstrokes(x,peaks,fs=64):
    indices=np.rint(np.asarray(peaks)*fs).astype(int);gradient=np.gradient(x,1/fs);ups=[];troughs=[];bad=0
    for j,p in enumerate(indices):
        left=max(2*fs,p-int(np.ceil(.4*fs)),int(np.ceil((indices[j-1]+p)/2)) if j else 0)
        trough=left+int(np.argmin(x[left:p+1]))
        up=trough+int(np.argmax(gradient[trough:p+1]))
        bad+=int(not trough<up<p);ups.append(up/fs);troughs.append(trough/fs)
    assert len(ups)==len(peaks) and np.all(np.diff(ups)>0)
    return ups,troughs,bad

def aggregate(local):
    public={}
    metrics=['f1','ppv','sensitivity','ppi_mae_ms','ppi_pair_coverage']
    for activity in ['sitting','walking']:
        rr=[r for r in local if r['activity']==activity];result={'records':len(rr),'core_time_coverage':float(np.mean([r['coverage'] for r in rr])),'landmarks':{}}
        for landmark in ['peak','upstroke']:
            values={}
            for segment in SEGMENTS:
                arms=[r['landmarks'][landmark][segment] for r in rr]
                choices=[a['choice'] for a in arms];amb=[c for c in choices if c['rival_fraction'] is not None and c['rival_fraction']>=.95]
                values[segment]={m:float(np.mean([a['tail'][m] for a in arms])) for m in metrics}
                values[segment].update(ambiguous_records=len(amb),cycle_like_ambiguous_records=sum(c['near_integer_cycle'] for c in amb),boundary_records=sum(c['boundary'] for c in choices))
            changes=[abs(r['landmarks'][landmark]['first60']['choice']['lag']-r['landmarks'][landmark]['second60']['choice']['lag']) for r in rr]
            values['stability']={'within_100ms_records':sum(d<=.1+1e-12 for d in changes),'median_lag_change_seconds':float(np.median(changes)),
                                 'mean_absolute_tail_f1_change':float(np.mean([abs(r['landmarks'][landmark]['first60']['tail']['f1']-r['landmarks'][landmark]['second60']['tail']['f1']) for r in rr]))}
            result['landmarks'][landmark]=values
        public[activity]=result
    return public

def main():
    out=ROOT/'outputs/ppg_upstroke_dev_v1';out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise RuntimeError('Preserve previous attempts')
    cache=ROOT/'outputs/ppg_capture_v1';done=json.loads((cache/'complete.json').read_text())
    assert sha(cache/'windows.json')==done['windows_sha256']
    assert sha(cache/'records.json')==done['records_sha256']
    rows=[r for r in json.loads((cache/'windows.json').read_text()) if r['phase']=='development']
    meta={r['key']:r for r in json.loads((cache/'records.json').read_text()) if r['phase']=='development'}
    assert len(rows)==211 and {r['subject'] for r in rows}=={'S1','S2','S3','S4','S5'}
    audit=json.loads((ROOT/'docs/acceptance/PPG_DALIA_AUDIT1.json').read_text());signals={}
    for entry in audit['files']:
        path=ROOT/'data/ppg_dalia_mat'/entry['file'];assert sha(path)==entry['sha256']
        for raw in loadmat(path,simplify_cells=True)['data']:
            key=str(raw['fix']['subj_name'])+'/'+entry['activity']
            if key in meta:
                assert raw['ppg']['fs']==64
                signals[key]=signal.sosfilt(signal.butter(3,[.5,5],btype='bandpass',fs=64,output='sos'),np.asarray(raw['ppg']['v'],float))
    for r in rows:
        x=signals[r['key']][r['start']*64:(r['start']+30)*64]
        r['upstroke'],r['trough'],r['non_strict_order']=upstrokes(x,r['detected']['v5_peaks'])
    local=[]
    for key in sorted(meta):
        rr=[r for r in rows if r['key']==key];item={'key':key,'subject':rr[0]['subject'],'activity':rr[0]['activity'],'landmarks':{},'coverage':22*sum(r['start']>=120 for r in rr)/(meta[key]['duration']-120)}
        for landmark in ['peak','upstroke']:
            adapted=[dict(r,detected={'v5_peaks':r['detected']['v5_peaks'] if landmark=='peak' else r['upstroke']}) for r in rr];item['landmarks'][landmark]={}
            for name,(start,end) in SEGMENTS.items():
                choice=select([r for r in adapted if start<=r['start']<end])
                item['landmarks'][landmark][name]={'choice':choice,'tail':score([r for r in adapted if r['start']>=120],choice['lag'])}
        assert len({a['tail']['tp']+a['tail']['fn'] for land in item['landmarks'].values() for a in land.values()})==1
        local.append(item)
    public={'stage':'PPG_UPSTROKE_DEV1','scope':'Seen development cohort, PPG-only candidates with ECG-assisted evaluation alignment; not external or disease validation',
            'subjects':5,'records':10,'windows':211,'candidate_count':sum(len(r['upstroke']) for r in rows),'non_strict_order_count':sum(r['non_strict_order'] for r in rows),
            'by_activity':aggregate(local),'paired':{},'source_sha256':{p:sha(ROOT/p) for p in ['scripts/run_ppg_upstroke_dev.py','docs/METHOD_PPG_UPSTROKE_DEV1.zh-CN.md','scripts/audit_ppg_stability_dev.py','src/t1d_lab/ppg_capture.py']},
            'cache_sha256':sha(cache/'windows.json'),'source_files_sha256':done['data_sha256']}
    for metric in ['f1','ppi_pair_coverage']:
        diff=np.array([np.mean([r['landmarks']['upstroke']['first120']['tail'][metric]-r['landmarks']['peak']['first120']['tail'][metric] for r in local if r['subject']==s]) for s in sorted({r['subject'] for r in local})])
        boot=np.random.default_rng(20261019).choice(diff,(10000,5),replace=True).mean(axis=1)
        public['paired'][metric]={'upstroke_minus_peak':float(diff.mean()),'95_interval':np.quantile(boot,[.025,.975]).tolist(),'subjects':5}
    (out/'windows_local.json').write_text(json.dumps(rows,allow_nan=False));(out/'records_local.json').write_text(json.dumps(local,indent=2,allow_nan=False))
    (ROOT/'docs/acceptance/PPG_UPSTROKE_DEV1.json').write_text(json.dumps(public,indent=2,allow_nan=False))
    print(json.dumps({'paired':public['paired'],'non_strict_order':public['non_strict_order_count'],'candidates':public['candidate_count']}))
    for activity,a in public['by_activity'].items():print(activity,{k:v['first120'] for k,v in a['landmarks'].items()})

if __name__=='__main__':main()
