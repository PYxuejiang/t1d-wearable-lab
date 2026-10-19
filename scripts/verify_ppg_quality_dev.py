"""Recheck candidate matching via searchsorted and AUROC via pair comparisons."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FEATURES=('non_strict_order','displacement_deviation','one_minus_sqi')
def equal(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:equal(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):equal(x,y)
    elif a is None or isinstance(a,(str,bool)):assert a==b
    else:assert np.isclose(a,b,rtol=0,atol=1e-10),(a,b)
def direct_auc(y,x):
    pos=[v for label,v in zip(y,x) if label];neg=[v for label,v in zip(y,x) if not label]
    if not pos or not neg:return None
    # Pair comparisons independent of the producer's rank-sum formula.
    wins=sum(sum(v>w for w in neg)+.5*sum(v==w for w in neg) for v in pos)
    return wins/(len(pos)*len(neg))
def avg(v):
    v=[x for x in v if x is not None];return float(np.mean(v)) if v else None
def main():
    path=ROOT/'docs/acceptance/PPG_QUALITY_DEV1.json';pub=json.loads(path.read_text())
    for group in ('source_sha256','input_sha256'):
        for p,digest in pub[group].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest
    rows=json.loads((ROOT/'outputs/ppg_upstroke_dev_v1/windows_local.json').read_text())
    old={r['key']:r for r in json.loads((ROOT/'outputs/ppg_upstroke_dev_v1/records_local.json').read_text())}
    local=json.loads((ROOT/'outputs/ppg_quality_dev_v1/records_local.json').read_text())
    upstream=json.loads((ROOT/'docs/acceptance/PPG_UPSTROKE_DEV1.json').read_text())
    assert len(rows)==211 and len(local)==10
    nwin=ncandidate=0
    for rec in local:
        rr=[r for r in rows if r['key']==rec['key']]
        calibration=[p-u for r in rr if r['start']<120 for p,u in zip(r['detected']['v5_peaks'],r['upstroke'])]
        med=float(np.median(calibration));scale=float(max(np.median([abs(x-med) for x in calibration]),1/64))
        equal([rec['median'],rec['scale']],[med,scale])
        deltas=[p-u for r in rr for p,u in zip(r['detected']['v5_peaks'],r['upstroke'])]
        equal(rec['displacement_ms'],{'median':float(np.median(deltas)*1000),'iqr':float((np.percentile(deltas,75)-np.percentile(deltas,25))*1000)})
        assert rec['candidate_count']==len(deltas)
        assert rec['bad_count']==sum(not t<u<p for r in rr for t,u,p in zip(r['trough'],r['upstroke'],r['detected']['v5_peaks']))
        lag=old[rec['key']]['landmarks']['upstroke']['first120']['choice']['lag'];labels=[];scores={k:[] for k in FEATURES};totals=dict(tp=0,fp=0,fn=0)
        tail=[r for r in rr if r['start']>=120];assert len(tail)==len(rec['windows'])
        for row,window in zip(tail,rec['windows']):
            indices=[j for j,u in enumerate(row['upstroke']) if 4<=u-lag<26]
            a=[t for t in row['reference'] if 4<=t<26];b=[row['upstroke'][j]-lag for j in indices]
            matches=[];next_index=0
            for t in a:
                j=max(next_index,int(np.searchsorted(b,t-.1-1e-12)))
                if j<len(b) and b[j]<=t+.1+1e-12:matches.append(j);next_index=j+1
            y=[j not in matches for j in range(len(b))]
            s={'non_strict_order':[int(not row['trough'][j]<row['upstroke'][j]<row['detected']['v5_peaks'][j]) for j in indices],
               'displacement_deviation':[abs(row['detected']['v5_peaks'][j]-row['upstroke'][j]-med)/scale for j in indices],
               'one_minus_sqi':[1-row['sqi'] for j in indices]}
            expected={'start':row['start'],'indices':indices,'unmatched':y,'scores':s,'tp':len(matches),'fp':len(b)-len(matches),'fn':len(a)-len(matches)}
            equal(window,expected);labels+=y
            for k in FEATURES:scores[k]+=s[k]
            for k in totals:totals[k]+=expected[k]
            nwin+=1;ncandidate+=len(y)
        bad=scores['non_strict_order'];nb=sum(bad);bu=sum(v and y for v,y in zip(bad,labels));fp=sum(labels)
        equal(rec['counts'],{**totals,'tail_candidates':len(labels),'tail_bad':nb,'bad_unmatched':bu})
        for k in totals:assert totals[k]==old[rec['key']]['landmarks']['upstroke']['first120']['tail'][k]
        ratio=lambda a,b:a/b if b else None
        equal(rec['rates'],{'bad_fraction':ratio(nb,len(labels)),'bad_unmatched_rate':ratio(bu,nb),'unmatched_covered_by_bad':ratio(bu,fp),'strict_unmatched_rate':ratio(fp-bu,len(labels)-nb),'reference_miss_rate':ratio(totals['fn'],totals['tp']+totals['fn'])})
        equal(rec['auc'],{k:direct_auc(labels,scores[k]) for k in FEATURES})
    for activity,group in pub['by_activity'].items():
        rr=[r for r in local if r['activity']==activity]
        assert group['records']==len(rr)==5
        for k in ('candidate_count','bad_count'):assert group[k]==sum(r[k] for r in rr)
        equal(group['counts'],{k:sum(r['counts'][k] for r in rr) for k in rr[0]['counts']})
        for field,source in [('auc_macro','auc'),('rates_macro','rates')]:
            equal(group[field],{k:{'mean':avg([r[source][k] for r in rr]),'valid_records':sum(r[source][k] is not None for r in rr)} for k in rr[0][source]})
        equal(group['displacement_ms_macro'],{k:float(np.mean([r['displacement_ms'][k] for r in rr])) for k in ('median','iqr')})
        equal(group['unchanged_first120'],upstream['by_activity'][activity])
    for k in FEATURES:
        vals=[]
        for sub in sorted({r['subject'] for r in local}):
            v=[r['auc'][k] for r in local if r['subject']==sub]
            if len(v)==2 and all(x is not None for x in v):vals.append(np.mean(v))
        if vals:
            indices=np.random.default_rng(20261019).integers(len(vals),size=(10000,len(vals)))
            ci=np.percentile(np.array(vals)[indices].mean(axis=1),[2.5,97.5]).tolist()
        else:ci=None
        equal(pub['paired_subject_auc'][k],{'mean':avg(vals),'95_interval':ci,'subjects':len(vals)})
    assert direct_auc([True,False],[1,0])==1
    assert direct_auc([True,False],[0,1])==0
    assert direct_auc([True,False],[1,1])==.5
    assert direct_auc([True],[1]) is None
    assert all(x not in json.dumps(pub) for x in ['S1/','"unmatched":','"indices":','"subject":'])
    pub['verification']={'status':'passed','tail_windows':nwin,'tail_candidates':ncandidate,'record_auc_recomputed':30,'subject_intervals':3,'old_counts_reproduced':True,'synthetic_auc_controls':4,'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    path.write_text(json.dumps(pub,indent=2,allow_nan=False));print(json.dumps(pub['verification'],indent=2))
if __name__=='__main__':main()
