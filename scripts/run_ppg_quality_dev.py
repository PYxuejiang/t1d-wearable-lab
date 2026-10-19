"""Frozen quality ranking audit; no rejection, training or threshold selection."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.stats import rankdata
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.ppg_capture import match_seconds
FEATURES=('non_strict_order','displacement_deviation','one_minus_sqi')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def auc(y,x):
    y=np.asarray(y,bool);x=np.asarray(x,float);n=int(y.sum());m=len(y)-n
    return float((rankdata(x)[y].sum()-n*(n+1)/2)/(n*m)) if n and m else None
def mean_available(values):
    v=[x for x in values if x is not None]
    return float(np.mean(v)) if v else None
def main():
    out=ROOT/'outputs/ppg_quality_dev_v1';out.mkdir(exist_ok=True,parents=True)
    if any(out.iterdir()):raise RuntimeError('Preserve previous attempts')
    source=ROOT/'outputs/ppg_upstroke_dev_v1'
    rows=json.loads((source/'windows_local.json').read_text());prev=json.loads((source/'records_local.json').read_text())
    acceptance=json.loads((ROOT/'docs/acceptance/PPG_UPSTROKE_DEV1.json').read_text())
    assert acceptance['verification']['status']=='passed' and len(rows)==211
    assert sum(len(r['upstroke']) for r in rows)==7954
    assert {r['subject'] for r in rows}=={'S1','S2','S3','S4','S5'}
    local=[]
    for old in prev:
        rr=[r for r in rows if r['key']==old['key']]
        cal=np.concatenate([np.asarray(r['detected']['v5_peaks'])-np.asarray(r['upstroke']) for r in rr if r['start']<120])
        median=float(np.median(cal));scale=float(max(np.median(abs(cal-median)),1/64))
        lag=old['landmarks']['upstroke']['first120']['choice']['lag']
        item={'key':old['key'],'subject':old['subject'],'activity':old['activity'],'median':median,'scale':scale,'windows':[],
              'candidate_count':0,'bad_count':0,'all_displacements':[]}
        for r in rr:
            p=np.asarray(r['detected']['v5_peaks']);u=np.asarray(r['upstroke']);t=np.asarray(r['trough']);delta=p-u
            bad=~((t<u)&(u<p));assert int(bad.sum())==r['non_strict_order']
            item['candidate_count']+=len(p);item['bad_count']+=int(bad.sum());item['all_displacements'].extend(delta.tolist())
            if r['start']<120:continue
            indices=np.flatnonzero((u-lag>=4)&(u-lag<26));b=(u-lag)[indices];a=np.asarray(r['reference']);a=a[(a>=4)&(a<26)]
            pairs=match_seconds(a,b);matched={j for _,j in pairs};labels=[j not in matched for j in range(len(b))]
            scores={'non_strict_order':bad[indices].astype(int).tolist(),'displacement_deviation':(abs(delta[indices]-median)/scale).tolist(),'one_minus_sqi':[1-r['sqi']]*len(indices)}
            item['windows'].append({'start':r['start'],'indices':indices.tolist(),'unmatched':labels,'scores':scores,'tp':len(pairs),'fp':len(b)-len(pairs),'fn':len(a)-len(pairs)})
        ws=item['windows'];labels=sum([w['unmatched'] for w in ws],[]);scores={k:sum([w['scores'][k] for w in ws],[]) for k in FEATURES}
        item['auc']={k:auc(labels,scores[k]) for k in FEATURES};y=np.array(labels,bool);bad=np.array(scores['non_strict_order'],bool)
        counts={'tp':sum(w['tp'] for w in ws),'fp':sum(w['fp'] for w in ws),'fn':sum(w['fn'] for w in ws),'tail_candidates':len(y),'tail_bad':int(bad.sum()),'bad_unmatched':int((bad&y).sum())}
        for k in ('tp','fp','fn'):assert counts[k]==old['landmarks']['upstroke']['first120']['tail'][k]
        item['counts']=counts
        ratio=lambda a,b:float(a/b) if b else None
        item['rates']={'bad_fraction':ratio(bad.sum(),len(y)),'bad_unmatched_rate':ratio((bad&y).sum(),bad.sum()),'unmatched_covered_by_bad':ratio((bad&y).sum(),y.sum()),'strict_unmatched_rate':ratio((~bad&y).sum(),(~bad).sum()),'reference_miss_rate':ratio(counts['fn'],counts['tp']+counts['fn'])}
        item['displacement_ms']={'median':float(np.median(item['all_displacements'])*1000),'iqr':float(np.diff(np.percentile(item['all_displacements'],[25,75]))[0]*1000)}
        del item['all_displacements'];local.append(item)
    public={'stage':'PPG_QUALITY_DEV1','scope':'Seen development, ECG-reference unmatched ranking; not artifact truth or disease validation','subjects':5,'windows':211,'by_activity':{},'paired_subject_auc':{},
        'input_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [source/'windows_local.json',source/'records_local.json',ROOT/'docs/acceptance/PPG_UPSTROKE_DEV1.json']},
        'source_sha256':{p:sha(ROOT/p) for p in ['scripts/run_ppg_quality_dev.py','docs/METHOD_PPG_QUALITY_DEV1.zh-CN.md','src/t1d_lab/ppg_capture.py']}}
    for activity in ('sitting','walking'):
        rr=[r for r in local if r['activity']==activity]
        public['by_activity'][activity]={'records':len(rr),'candidate_count':sum(r['candidate_count'] for r in rr),'bad_count':sum(r['bad_count'] for r in rr),
            'counts':{k:sum(r['counts'][k] for r in rr) for k in rr[0]['counts']},
            'rates_macro':{k:{'mean':mean_available([r['rates'][k] for r in rr]),'valid_records':sum(r['rates'][k] is not None for r in rr)} for k in rr[0]['rates']},
            'auc_macro':{k:{'mean':mean_available([r['auc'][k] for r in rr]),'valid_records':sum(r['auc'][k] is not None for r in rr)} for k in FEATURES},
            'displacement_ms_macro':{k:float(np.mean([r['displacement_ms'][k] for r in rr])) for k in ('median','iqr')},
            'unchanged_first120':acceptance['by_activity'][activity]}
    for k in FEATURES:
        values=[]
        for subject in sorted({r['subject'] for r in local}):
            v=[r['auc'][k] for r in local if r['subject']==subject]
            if len(v)==2 and all(x is not None for x in v):values.append(np.mean(v))
        boot=np.random.default_rng(20261019).choice(values,(10000,len(values)),replace=True).mean(axis=1) if values else None
        public['paired_subject_auc'][k]={'mean':float(np.mean(values)) if values else None,'95_interval':np.quantile(boot,[.025,.975]).tolist() if values else None,'subjects':len(values)}
    (out/'records_local.json').write_text(json.dumps(local,indent=2,allow_nan=False))
    (ROOT/'docs/acceptance/PPG_QUALITY_DEV1.json').write_text(json.dumps(public,indent=2,allow_nan=False))
    print(json.dumps({'auc':public['paired_subject_auc'],'counts':{k:v['counts'] for k,v in public['by_activity'].items()}},indent=2))
if __name__=='__main__':main()
