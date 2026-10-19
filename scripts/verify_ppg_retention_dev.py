"""Independent fixed-quantile, matching and denominator conservation audit."""
import hashlib,json
from pathlib import Path
import numpy as np
from verify_ppg_stability_dev import recount
from verify_ppg_quality_dev import equal
ROOT=Path(__file__).resolve().parents[1]
def ratio(a,b):return a/b if b else None
def macro(values):
    v=[x for x in values if x is not None]
    return {'mean':float(np.mean(v)) if v else None,'valid_records':len(v)}
def main():
    path=ROOT/'docs/acceptance/PPG_RETENTION_DEV1.json';pub=json.loads(path.read_text())
    for group in ('input_sha256','source_sha256'):
        for p,digest in pub[group].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest
    rows=json.loads((ROOT/'outputs/ppg_upstroke_dev_v1/windows_local.json').read_text())
    prev={r['key']:r for r in json.loads((ROOT/'outputs/ppg_upstroke_dev_v1/records_local.json').read_text())}
    local=json.loads((ROOT/'outputs/ppg_retention_dev_v1/records_local.json').read_text())
    nwin=0
    for rec in local:
        old=prev[rec['key']];rr=[r for r in rows if r['key']==rec['key']];cal=sorted(r['sqi'] for r in rr if r['start']<120);assert len(cal)==4
        expected={'baseline':None}
        for k,q in [('q25',.25),('q50',.5),('q75',.75)]:
            index=3*q;lo=int(index);expected[k]=cal[lo]+(index-lo)*(cal[lo+1]-cal[lo])
        equal(rec['thresholds'],expected)
        tail=[r for r in rr if r['start']>=120];assert len(tail)==len(rec['windows'])
        lag=old['landmarks']['upstroke']['first120']['choice']['lag'];computed=[]
        for row,w in zip(tail,rec['windows']):
            counts=recount({'reference':row['reference'],'detected':{'v5_peaks':row['upstroke']}},lag)
            x=dict(zip(('tp','fn','fp','ppi_pairs','reference_pairs','ppi_abs_sum_ms'),counts.tolist()))
            x.update(start=row['start'],sqi=row['sqi']);equal(w,x);computed.append(x);nwin+=1
        keys=('tp','fn','fp','ppi_pairs','reference_pairs','ppi_abs_sum_ms')
        all_counts={k:sum(w[k] for w in computed) for k in keys}
        for k,v in all_counts.items():assert abs(v-old['landmarks']['upstroke']['first120']['tail'][k])<1e-8
        lengths=[]
        for name,threshold in expected.items():
            accepted=[w for w in computed if threshold is None or w['sqi']>=threshold];rejected=[w for w in computed if threshold is not None and w['sqi']<threshold]
            kept={k:sum(w[k] for w in accepted) for k in keys};rej={k:sum(w[k] for w in rejected) for k in keys}
            for k in keys:assert abs(kept[k]+rej[k]-all_counts[k])<1e-8
            tp=kept['tp'];fp=kept['fp'];fn=kept['fn']+rej['fn']+rej['tp'];lengths.append(len(accepted))
            m={'ppv':ratio(tp,tp+fp),'sensitivity':ratio(tp,tp+fn),'f1':ratio(2*tp,2*tp+fp+fn),
               'baseline_tp_retention':ratio(tp,all_counts['tp']),'baseline_fp_removed':ratio(rej['fp'],all_counts['fp']),
               'relative_time_retention':len(accepted)/len(tail),'core_time_coverage':old['coverage']*len(accepted)/len(tail),
               'ppi_pair_coverage':ratio(kept['ppi_pairs'],all_counts['reference_pairs']),'ppi_mae_ms':ratio(kept['ppi_abs_sum_ms'],kept['ppi_pairs'])}
            equal(rec['arms'][name],{'kept_windows':len(accepted),'counts':{'tp':tp,'fp':fp,'fn':fn,'ppi_pairs':kept['ppi_pairs'],'reference_pairs':all_counts['reference_pairs']},'metrics':m,
                  'rejected_original_counts':{k:rej[k] for k in ('tp','fp','fn','ppi_pairs','reference_pairs')},'rejected_original_ppv':ratio(rej['tp'],rej['tp']+rej['fp'])})
            assert tp+fn==all_counts['tp']+all_counts['fn']
        assert lengths==sorted(lengths,reverse=True)
    assert nwin==pub['tail_windows']==171 and len(local)==10
    for activity,group in pub['by_activity'].items():
        rr=[r for r in local if r['activity']==activity];assert group['records']==len(rr)==5
        assert group['tail_windows']==sum(len(r['windows']) for r in rr)
        for arm,a in group['arms'].items():
            aa=[r['arms'][arm] for r in rr]
            equal(a,{'kept_windows':sum(x['kept_windows'] for x in aa),'zero_output_records':sum(x['counts']['tp']+x['counts']['fp']==0 for x in aa),
              'counts':{k:sum(x['counts'][k] for x in aa) for k in aa[0]['counts']},
              'metrics_macro':{k:macro([x['metrics'][k] for x in aa]) for k in aa[0]['metrics']},
              'rejected_original_counts':{k:sum(x['rejected_original_counts'][k] for x in aa) for k in aa[0]['rejected_original_counts']},
              'rejected_original_ppv_macro':macro([x['rejected_original_ppv'] for x in aa])})
    for metric,result in pub['q50_minus_baseline'].items():
        differences=[]
        for sub in sorted({r['subject'] for r in local}):
            aa=[r['arms'] for r in local if r['subject']==sub]
            if all(a[k]['metrics'][metric] is not None for a in aa for k in ('baseline','q50')):
                differences.append(np.mean([a['q50']['metrics'][metric]-a['baseline']['metrics'][metric] for a in aa]))
        if differences:
            idx=np.random.default_rng(20261020).integers(len(differences),size=(10000,len(differences)))
            ci=np.percentile(np.array(differences)[idx].mean(axis=1),[2.5,97.5]).tolist()
        else:ci=None
        equal(result,{'mean_difference':float(np.mean(differences)) if differences else None,'95_interval':ci,'subjects':len(differences)})
    # Complete rejection never makes recall/coverage disappear from the denominator.
    reference=17;tp=0;fp=0;fn=reference
    assert ratio(tp,tp+fp) is None and ratio(tp,tp+fn)==0 and ratio(2*tp,2*tp+fp+fn)==0
    assert all(x not in json.dumps(pub) for x in ['S1/','"thresholds":','"subject":','"reference":'])
    pub['verification']={'status':'passed','calibration_thresholds':30,'tail_windows_recounted':171,'record_arms':40,'paired_intervals':4,'all_reference_denominators_preserved':True,'baseline_reproduced':True,'nested_retention':True,'zero_output_control':True,
      'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'helper_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/verify_ppg_stability_dev.py','scripts/verify_ppg_quality_dev.py']}}
    path.write_text(json.dumps(pub,indent=2,allow_nan=False));print(json.dumps(pub['verification'],indent=2))
if __name__=='__main__':main()
