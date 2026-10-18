"""Independent reference-window and matching-count checks; publish aggregate evidence only."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.ppg_capture import score_window,summarize


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def dp_count(a,b,tolerance=.1):
    # LCS-style dynamic programming, independently checking the greedy matcher.
    b=np.asarray(b);previous=np.zeros(len(b)+1,int)
    for t in a:
        valid=np.abs(b-t)<=tolerance+1e-12
        previous=np.r_[0,np.maximum.accumulate(np.maximum(previous[1:],previous[:-1]+valid))]
    return int(previous[-1])


def independent(row,method,lag,zero=False,accepted=True):
    ref=np.asarray(row['reference'])+(1/700 if zero else 0);ref=ref[(ref>=2)&(ref<29)]
    pred=np.asarray(row['detected'][method])-lag;pred=pred[(pred>=2)&(pred<29)] if accepted else np.array([])
    value=score_window(row,method,lag,origin_zero=zero,accepted=accepted)
    tp=dp_count(ref,pred);assert (tp,len(ref)-tp,len(pred)-tp)==(value['tp'],value['fn'],value['fp'])
    # Independently recover the prescribed earliest feasible assignment and adjacent-only intervals.
    pairs=[];next_ref=0
    for j,p in enumerate(pred):
        while next_ref<len(ref) and ref[next_ref]<p-.1-1e-12:next_ref+=1
        if next_ref<len(ref) and abs(ref[next_ref]-p)<=.1+1e-12:pairs.append((next_ref,j));next_ref+=1
    assert len(pairs)==tp
    errors=[abs((pred[d]-pred[b])-(ref[c]-ref[a]))*1000 for (a,b),(c,d) in zip(pairs,pairs[1:]) if c-a==1 and d-b==1]
    assert len(errors)==value['ppi_pairs'] and abs(sum(errors)-value['ppi_abs_sum_ms'])<1e-6
    def hr(v):
        d=np.diff(v);d=d[(d>=.3)&(d<=2)]
        return 60/np.median(d) if len(d)>=5 else None
    rh,ph=hr(ref),hr(pred);expected=abs(rh-ph) if rh is not None and ph is not None else 0
    assert abs(expected-value['hr_error_sum'])<1e-9
    return value


def macro(records,field):
    persons={}
    for r in records:
        if r[field] is not None:persons.setdefault(r['subject'],[]).append(r[field])
    return {s:float(np.mean(v)) for s,v in persons.items()}


def summary(records):
    fields=['f1','sensitivity','ppv','hr_mae_bpm','hr_output_fraction','ppi_mae_ms','ppi_pair_coverage','accepted_core_fraction','covered_reference_time_fraction','conditional_f1']
    result={'records':len(records),'subjects':len(set(r['subject'] for r in records))}
    for field in fields:
        v=macro(records,field);result[field]=float(np.mean(list(v.values()))) if v else None;result[field+'_subjects']=len(v)
    result['reference_beats']=sum(r['tp']+r['fn'] for r in records)
    return result


def bootstrap(values,cfg):
    values=np.asarray(values);rng=np.random.default_rng(cfg['seed']);a=rng.choice(values,(cfg['bootstrap_repetitions'],len(values)),replace=True).mean(axis=1)
    return {'mean':float(values.mean()),'95_interval':np.quantile(a,[.025,.975]).tolist(),'subjects':len(values)}


def main():
    cfg=json.loads((ROOT/'configs/ppg_capture_v1.json').read_text());dest=ROOT/cfg['output'];done=json.loads((dest/'complete.json').read_text())
    for name,digest in done['source_sha256'].items():assert sha(ROOT/name)==digest
    for name in ['selection','windows','records']:assert sha(dest/(name+'.json'))==done[name+'_sha256']
    rows=json.loads((dest/'windows.json').read_text());metas=json.loads((dest/'records.json').read_text());selection=json.loads((dest/'selection.json').read_text());threshold=selection['sqi_threshold']
    raw_refs={};durations={}
    for name,digest in done['data_sha256'].items():
        path=ROOT/'data/ppg_dalia_mat'/name;assert sha(path)==digest
        activity='sitting' if 'sitting' in name else 'walking'
        for r in loadmat(path,simplify_cells=True)['data']:
            key=str(r['fix']['subj_name'])+'/'+activity;raw_refs[key]=(np.asarray(r['ecg']['rpeaks'])-1)/700
            durations[key]=min(len(r['ppg']['v'])/64,len(r['ecg']['v'])/700)
    assert len(metas)==29 and len(set(r['key'] for r in metas))==29 and 'S6/walking' not in raw_refs
    for row in rows:
        assert row['start']%30==0 and row['input_end']==row['start']+30 and row['input_end']<=durations[row['key']]
        assert row['subject'] in cfg[row['phase']+'_subjects']
        ref=raw_refs[row['key']];expected=ref[(ref>=row['start'])&(ref<row['input_end'])]-row['start']
        assert np.array_equal(expected,row['reference'])
        for peaks in row['detected'].values():
            assert np.all(np.diff(peaks)>0) and all(2<=p<30 for p in peaks)
    # Reconstruct every calibration choice independently of the module's lag selector.
    for meta in metas:
        rr=[r for r in rows if r['key']==meta['key']];assert len(rr)==int(meta['duration']//30) and len(rr)-4==meta['score_windows']
        calibration=[r for r in rr if r['start']<120];assert len(calibration)==4
        counts=[]
        for lag in cfg['lag_grid_seconds']:
            tp=sum(independent(r,'v5_peaks',lag)['tp'] for r in calibration)
            counts.append((tp,-abs(lag-.2),-lag,lag))
        assert max(counts)[-1]==meta['lag_seconds']
    # All threshold candidates were chosen only from development records.
    checked=[]
    for old in selection['candidates']:
        scores=[];coverage={a:[] for a in ['sitting','walking']}
        for meta in [m for m in metas if m['phase']=='development']:
            rr=[r for r in rows if r['key']==meta['key'] and r['start']>=120];keep=[r for r in rr if r['sqi']>=old['threshold']]
            a=summarize([independent(r,'dual_average',meta['lag_seconds']) for r in keep]);scores.append(a['f1']);coverage[meta['activity']].append(len(keep)/len(rr))
        cov={a:float(np.mean(v)) for a,v in coverage.items()};feasible=min(cov.values())>=.7 and all(s is not None for s in scores)
        assert feasible==old['feasible'] and cov==old['coverage_by_activity']
        score=float(np.mean(scores)) if feasible else None;assert score==old['macro_f1']
        if feasible:checked.append((score,sum(cov.values()),-old['threshold'],old['threshold']))
    assert max(checked)[-1]==threshold
    records=[]
    for meta in metas:
        rr=[r for r in rows if r['key']==meta['key'] and r['start']>=120]
        for view,fixed in cfg['views'].items():
            lag=meta['lag_seconds'] if fixed is None else fixed
            for method in cfg['algorithms']:
                for gate in ['raw','sqi']:
                    vals=[];accepted=[]
                    for row in rr:
                        keep=gate=='raw' or row['sqi']>=threshold
                        val=independent(row,method,lag,view=='index_origin_zero',keep);vals.append(val)
                        if keep:accepted.append(val)
                    total=summarize(vals);conditional=summarize(accepted)
                    total.update({**meta,'view':view,'method':method,'gate':gate,'accepted_core_fraction':len(accepted)/len(rr),'covered_reference_time_fraction':27*len(accepted)/(meta['duration']-120),'conditional_f1':conditional['f1']})
                    records.append(total)
    results={}
    for phase in ['development','heldout']:
        for view in cfg['views']:
            for method in cfg['algorithms']:
                for gate in ['raw','sqi']:
                    rr=[r for r in records if (r['phase'],r['view'],r['method'],r['gate'])==(phase,view,method,gate)]
                    key='/'.join([phase,view,method,gate]);results[key]=summary(rr)
                    results[key]['by_activity']={a:summary([r for r in rr if r['activity']==a]) for a in ['sitting','walking']}
    contrasts={}
    for view in cfg['views']:
        for field in ['f1','hr_mae_bpm','ppi_mae_ms','ppi_pair_coverage','hr_output_fraction']:
            base=macro([r for r in records if (r['phase'],r['view'],r['method'],r['gate'])==('heldout',view,'v5_peaks','raw')],field)
            new=macro([r for r in records if (r['phase'],r['view'],r['method'],r['gate'])==('heldout',view,'dual_average','raw')],field)
            contrasts[view+'/'+field]=bootstrap([new[s]-base[s] for s in base if s in new],cfg)
    effect='f1_gain_supported' if contrasts['calibrated/f1']['95_interval'][0]>0 else 'f1_gain_not_supported'
    report={'stage':cfg['id'],'engineering_status':'passed','effect_status':effect,'clinical_effect_status':'not_evaluated','records_verified':len(metas),'metric_groups_verified':len(records),'windows_verified':len(rows),'development_candidates_verified':len(selection['candidates']),'feasible_candidates':len(checked),'sqi_threshold':threshold,'selection':selection,'results':results,'paired_differences':contrasts,'metrics_by_record':records,'source_sha256':done['source_sha256'],'data_sha256':done['data_sha256'],'limitations':[cfg['scope'],'Calibrated scores use first120s ECG reference; not reference-free deployment.','Only sitting/walking; S6 walking absent; no manual PPG fiducial labels.','Intervals are adjacent-matched only: always interpret alongside PPI pair coverage.','Two origins and fixed/unadjusted delays reported; no heldout-wide alignment tuning.','Exploratory10-person bootstrap; repeated measurements not independent people.']}
    (ROOT/'docs/acceptance/PPG_CAPTURE1.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'effect':effect,'selected_sqi':threshold,'baseline':results['heldout/calibrated/v5_peaks/raw'],'new':results['heldout/calibrated/dual_average/raw'],'contrasts':contrasts},indent=2))
if __name__=='__main__':main()
