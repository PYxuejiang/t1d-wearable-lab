"""Independent source waveform extrema and reference-matching verification."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat
from verify_ppg_stability_dev import recount
from verify_ppg_fiducial import equal
ROOT=Path(__file__).resolve().parents[1]

def main():
    path=ROOT/'docs/acceptance/PPG_UPSTROKE_DEV1.json';public=json.loads(path.read_text())
    for p,h in public['source_sha256'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    cache=ROOT/'outputs/ppg_capture_v1'
    assert hashlib.sha256((cache/'windows.json').read_bytes()).hexdigest()==public['cache_sha256']
    original=[r for r in json.loads((cache/'windows.json').read_text()) if r['phase']=='development']
    rows=json.loads((ROOT/'outputs/ppg_upstroke_dev_v1/windows_local.json').read_text())
    local=json.loads((ROOT/'outputs/ppg_upstroke_dev_v1/records_local.json').read_text())
    assert len(rows)==len(original)==211 and len(local)==10
    assert {r['subject'] for r in rows}=={'S1','S2','S3','S4','S5'}
    data={}
    audit=json.loads((ROOT/'docs/acceptance/PPG_DALIA_AUDIT1.json').read_text())
    for entry in audit['files']:
        file=ROOT/'data/ppg_dalia_mat'/entry['file']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==public['source_files_sha256'][entry['file']]
        for s in loadmat(file,squeeze_me=True,struct_as_record=False)['data']:
            if str(s.fix.subj_name) in {'S1','S2','S3','S4','S5'}:
                data[str(s.fix.subj_name)+'/'+entry['activity']]=signal.sosfilt(signal.butter(3,[.5,5],btype='bandpass',fs=64,output='sos'),np.asarray(s.ppg.v,float))
    bad=total=0
    for r,old in zip(rows,original):
        equal({k:r[k] for k in old},old)
        x=data[r['key']][r['start']*64:(r['start']+30)*64]
        peaks=[round(t*64) for t in old['detected']['v5_peaks']];up=[];valleys=[];invalid=0
        for j,p in enumerate(peaks):
            left=max(128,p-26,(peaks[j-1]+p+1)//2 if j else 0)
            v=min(range(left,p+1),key=lambda i:(x[i],i))
            def derivative(i):
                a=max(0,i-1);b=min(len(x)-1,i+1)
                return (x[b]-x[a])*64/(b-a)
            u=max(range(v,p+1),key=lambda i:(derivative(i),-i))
            up.append(u/64);valleys.append(v/64);invalid+=int(not v<u<p)
        equal(r['upstroke'],up);equal(r['trough'],valleys);assert r['non_strict_order']==invalid
        assert len(up)==len(peaks) and all(b>a for a,b in zip(up,up[1:]));bad+=invalid;total+=len(up)
    assert public['candidate_count']==total and public['non_strict_order_count']==bad
    grid=np.round(np.arange(-1.5,1.501,.01),2);segments={'first60':(0,60),'second60':(60,120),'first120':(0,120)}
    old_records={r['key']:r for r in json.loads((ROOT/'outputs/ppg_stability_dev_v1/records_local.json').read_text())}
    metadata={r['key']:r for r in json.loads((cache/'records.json').read_text()) if r['phase']=='development'}
    for rec in local:
        rr=[r for r in rows if r['key']==rec['key']];denominators=[]
        equal(rec['landmarks']['peak'],old_records[rec['key']]['arms'])
        for mark in ('peak','upstroke'):
            adapted=[dict(r,detected={'v5_peaks':r['detected']['v5_peaks'] if mark=='peak' else r['upstroke']}) for r in rr]
            for name,(start,end) in segments.items():
                cal=[r for r in adapted if start<=r['start']<end]
                counts={float(lag):int(sum(recount(r,lag)[0] for r in cal)) for lag in grid}
                key=lambda lag:(counts[lag],-abs(lag-.2),-lag)
                lag=max(counts,key=key);rival=max((g for g in counts if abs(g-lag)>=.3-1e-9),key=key)
                cycles=abs(rival-lag)/np.median(np.concatenate([np.diff(r['reference']) for r in cal]))
                choice={'lag':lag,'tp':counts[lag],'rival_lag':rival,'rival_fraction':counts[rival]/counts[lag] if counts[lag] else None,
                        'near_integer_cycle':bool(round(cycles)>=1 and abs(cycles-round(cycles))<=.15),'boundary':bool(abs(lag)==1.5)}
                arm=rec['landmarks'][mark][name];equal(arm['choice'],choice)
                tail=[r for r in adapted if r['start']>=120]
                totals=np.sum([recount(r,lag) for r in tail],axis=0)
                tp,fn,fp,pp,rp,error=totals
                assert np.allclose(totals,[arm['tail'][k] for k in ['tp','fn','fp','ppi_pairs','reference_pairs','ppi_abs_sum_ms']],rtol=0,atol=1e-8)
                expect={'f1':2*tp/(2*tp+fn+fp),'ppv':tp/(tp+fp),'sensitivity':tp/(tp+fn),'ppi_mae_ms':error/pp,'ppi_pair_coverage':pp/rp}
                for k,v in expect.items():assert abs(arm['tail'][k]-v)<1e-10
                denominators.append(tp+fn)
        assert len(set(denominators))==1
        assert abs(rec['coverage']-22*sum(r['start']>=120 for r in rr)/(metadata[rec['key']]['duration']-120))<1e-12
    for activity in ('sitting','walking'):
        subset=[r for r in local if r['activity']==activity];agg=public['by_activity'][activity]
        assert agg['records']==len(subset)==5
        assert abs(agg['core_time_coverage']-np.mean([r['coverage'] for r in subset]))<1e-12
        for mark in ('peak','upstroke'):
            for seg in segments:
                arms=[r['landmarks'][mark][seg] for r in subset];a=agg['landmarks'][mark][seg]
                for metric in ('f1','ppv','sensitivity','ppi_mae_ms','ppi_pair_coverage'):
                    assert abs(a[metric]-np.mean([v['tail'][metric] for v in arms]))<1e-12
                amb=[v['choice'] for v in arms if v['choice']['rival_fraction'] is not None and v['choice']['rival_fraction']>=.95]
                assert a['ambiguous_records']==len(amb)
                assert a['cycle_like_ambiguous_records']==sum(c['near_integer_cycle'] for c in amb)
                assert a['boundary_records']==sum(v['choice']['boundary'] for v in arms)
            diffs=[abs(r['landmarks'][mark]['first60']['choice']['lag']-r['landmarks'][mark]['second60']['choice']['lag']) for r in subset]
            expected={'within_100ms_records':sum(v<=.1+1e-12 for v in diffs),'median_lag_change_seconds':float(np.median(diffs)),
                      'mean_absolute_tail_f1_change':float(np.mean([abs(r['landmarks'][mark]['first60']['tail']['f1']-r['landmarks'][mark]['second60']['tail']['f1']) for r in subset]))}
            equal(agg['landmarks'][mark]['stability'],expected)
    for metric in ('f1','ppi_pair_coverage'):
        differences=np.array([np.mean([r['landmarks']['upstroke']['first120']['tail'][metric]-r['landmarks']['peak']['first120']['tail'][metric] for r in local if r['subject']==s]) for s in sorted({r['subject'] for r in local})])
        indices=np.random.default_rng(20261019).integers(5,size=(10000,5));ci=np.percentile(differences[indices].mean(axis=1),[2.5,97.5]).tolist()
        equal(public['paired'][metric],{'subjects':5,'upstroke_minus_peak':float(differences.mean()),'95_interval':ci})
    assert all(k not in json.dumps(public) for k in ['S1/','S2/','S3/','S4/','S5/','"reference":','"rival_lag":'])
    public['verification']={'status':'passed','windows_reparsed':211,'candidate_localizations_recomputed':total,'calibration_choices':60,'tail_count_and_ppi_groups':60,
                            'old_peak_baseline_reproduced':True,'equal_reference_denominators':True,'paired_intervals':2,
                            'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            'helper_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/verify_ppg_stability_dev.py','scripts/verify_ppg_fiducial.py']}}
    path.write_text(json.dumps(public,indent=2,allow_nan=False));print(json.dumps(public['verification'],indent=2))

if __name__=='__main__':main()
