"""Recompute development alignment counts and public summaries from local audit."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def count(row,lag):
    a=np.asarray(row['reference']);b=np.asarray(row['detected']['v5_peaks'])-lag
    a=a[(a>=4)&(a<26)];b=b[(b>=4)&(b<26)]
    available=0;tp=0
    for x in a:
        j=max(available,int(np.searchsorted(b,x-.1-1e-12)))
        if j<len(b) and b[j]<=x+.1+1e-12:
            tp+=1;available=j+1
    return tp,len(a)-tp,len(b)-tp


def main():
    public_path=ROOT/'docs/acceptance/PPG_TIMING_DEV1.json'
    public=json.loads(public_path.read_text())
    for name,digest in public['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    local=json.loads((ROOT/'outputs/ppg_timing_dev_v1/records_local.json').read_text())
    rows=[r for r in json.loads((ROOT/'outputs/ppg_capture_v1/windows.json').read_text()) if r['phase']=='development']
    assert len(rows)==211 and len(local)==10
    deltas={}
    for record in local:
        rr=[r for r in rows if r['key']==record['key']]
        cal=[r for r in rr if r['start']<120];tail=[r for r in rr if r['start']>=120]
        for name,grid in [('old',np.round(np.arange(0,.601,.01),2)),('new',np.round(np.arange(-1.5,1.501,.01),2))]:
            lag=max(grid,key=lambda x:(sum(count(r,x)[0] for r in cal),-abs(x-.2),-x))
            assert abs(lag-record[name+'_lag'])<1e-12
            totals=np.sum([count(r,lag) for r in tail],axis=0)
            for key,value in zip(['tp','fn','fp'],totals):assert record[name+'_tail'][key]==value
        assert record['old_tail']['tp']+record['old_tail']['fn']==record['new_tail']['tp']+record['new_tail']['fn']
        deltas.setdefault(record['key'].split('/')[0],[]).append(record['new_tail']['f1']-record['old_tail']['f1'])
    person=np.array([np.mean(v) for v in deltas.values()]);assert len(person)==5
    rng=np.random.default_rng(20261019)
    boot=np.mean(rng.choice(person,(10000,len(person)),replace=True),axis=1)
    public['development_paired_f1_difference']={'subjects':5,'mean':float(person.mean()),'95_interval':np.quantile(boot,[.025,.975]).tolist(),'interpretation':'Exploratory alignment sensitivity, not detector improvement; five development subjects only'}
    for activity in ['sitting','walking']:
        records=[r for r in local if r['activity']==activity]
        meta=[r for r in json.loads((ROOT/'outputs/ppg_capture_v1/records.json').read_text()) if r['phase']=='development' and r['activity']==activity]
        public['by_activity'][activity]['core_time_coverage_after_calibration']=float(np.mean([22*r['score_windows']/(r['duration']-120) for r in meta]))
        for name,label in [('old','old_tail_f1'),('new','expanded_tail_f1')]:
            assert abs(np.mean([r[name+'_tail']['f1'] for r in records])-public['by_activity'][activity][label])<1e-12
    # Public schema contains no subject-linked metric, waveform or peak arrays.
    assert all(key not in json.dumps(public) for key in ['S1/','S2/','S3/','S4/','S5/','block_lags','detected'])
    public['verification']={'status':'passed','calibration_choices':20,'tail_count_groups':20,'equal_reference_denominators':True,'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    public_path.write_text(json.dumps(public,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(public['development_paired_f1_difference']))


if __name__=='__main__':main()
