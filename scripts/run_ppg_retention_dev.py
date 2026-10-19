"""Fixed calibration quantiles: quantify false output removal and lost coverage."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.ppg_capture import metrics
ARMS={'baseline':None,'q25':.25,'q50':.5,'q75':.75}
KEYS=('tp','fp','fn','ppi_pairs','reference_pairs','ppi_abs_sum_ms')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ratio(a,b):return float(a/b) if b else None
def main():
    out=ROOT/'outputs/ppg_retention_dev_v1';out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise RuntimeError('Preserve previous attempts')
    paths=['outputs/ppg_upstroke_dev_v1/windows_local.json','outputs/ppg_upstroke_dev_v1/records_local.json','docs/acceptance/PPG_QUALITY_DEV1.json']
    rows=json.loads((ROOT/paths[0]).read_text());old=json.loads((ROOT/paths[1]).read_text())
    assert json.loads((ROOT/paths[2]).read_text())['verification']['status']=='passed'
    assert len(rows)==211 and len(old)==10 and {r['subject'] for r in rows}=={'S1','S2','S3','S4','S5'}
    local=[]
    for prev in old:
        rr=[r for r in rows if r['key']==prev['key']];cal=[r['sqi'] for r in rr if r['start']<120];assert len(cal)==4
        thresholds={k:float(np.quantile(cal,q,method='linear')) if q is not None else None for k,q in ARMS.items()}
        lag=prev['landmarks']['upstroke']['first120']['choice']['lag'];windows=[]
        for r in rr:
            if r['start']<120:continue
            a=np.asarray(r['reference']);b=np.asarray(r['upstroke'])-lag
            m=metrics(a[(a>=4)&(a<26)],b[(b>=4)&(b<26)])
            windows.append({'start':r['start'],'sqi':r['sqi'],**{k:m[k] for k in KEYS}})
        totals={k:sum(w[k] for w in windows) for k in KEYS};base=prev['landmarks']['upstroke']['first120']['tail']
        for k,v in totals.items():assert abs(v-base[k])<1e-8
        arms={}
        for name,threshold in thresholds.items():
            selected=[w for w in windows if threshold is None or w['sqi']>=threshold]
            kept={k:sum(w[k] for w in selected) for k in KEYS};rejected={k:totals[k]-kept[k] for k in KEYS}
            tp=kept['tp'];fp=kept['fp'];fn=totals['tp']+totals['fn']-tp
            arms[name]={'kept_windows':len(selected),'counts':{'tp':tp,'fp':fp,'fn':fn,'ppi_pairs':kept['ppi_pairs'],'reference_pairs':totals['reference_pairs']},
                'metrics':{'ppv':ratio(tp,tp+fp),'sensitivity':ratio(tp,tp+fn),'f1':ratio(2*tp,2*tp+fn+fp),
                    'baseline_tp_retention':ratio(tp,totals['tp']),'baseline_fp_removed':ratio(rejected['fp'],totals['fp']),
                    'relative_time_retention':len(selected)/len(windows),'core_time_coverage':prev['coverage']*len(selected)/len(windows),
                    'ppi_pair_coverage':ratio(kept['ppi_pairs'],totals['reference_pairs']),'ppi_mae_ms':ratio(kept['ppi_abs_sum_ms'],kept['ppi_pairs'])},
                'rejected_original_counts':{k:rejected[k] for k in ('tp','fp','fn','ppi_pairs','reference_pairs')},
                'rejected_original_ppv':ratio(rejected['tp'],rejected['tp']+rejected['fp'])}
        local.append({'key':prev['key'],'subject':prev['subject'],'activity':prev['activity'],'thresholds':thresholds,'windows':windows,'arms':arms})
    public={'stage':'PPG_RETENTION_DEV1','scope':'Seen development; fixed calibration SQI quantiles, no operating point selected or deployed','subjects':5,'records':10,'tail_windows':sum(len(r['windows']) for r in local),'by_activity':{},'q50_minus_baseline':{},
      'input_sha256':{p:sha(ROOT/p) for p in paths},'source_sha256':{p:sha(ROOT/p) for p in ['scripts/run_ppg_retention_dev.py','docs/METHOD_PPG_RETENTION_DEV1.zh-CN.md','src/t1d_lab/ppg_capture.py']}}
    for activity in ('sitting','walking'):
        rr=[r for r in local if r['activity']==activity];group={'records':len(rr),'tail_windows':sum(len(r['windows']) for r in rr),'arms':{}}
        for name in ARMS:
            aa=[r['arms'][name] for r in rr];macro={}
            for k in aa[0]['metrics']:
                v=[a['metrics'][k] for a in aa if a['metrics'][k] is not None];macro[k]={'mean':float(np.mean(v)) if v else None,'valid_records':len(v)}
            rejected_ppv=[a['rejected_original_ppv'] for a in aa if a['rejected_original_ppv'] is not None]
            group['arms'][name]={'kept_windows':sum(a['kept_windows'] for a in aa),'zero_output_records':sum(a['counts']['tp']+a['counts']['fp']==0 for a in aa),
                'counts':{k:sum(a['counts'][k] for a in aa) for k in aa[0]['counts']},'metrics_macro':macro,
                'rejected_original_counts':{k:sum(a['rejected_original_counts'][k] for a in aa) for k in aa[0]['rejected_original_counts']},
                'rejected_original_ppv_macro':{'mean':float(np.mean(rejected_ppv)) if rejected_ppv else None,'valid_records':len(rejected_ppv)}}
        public['by_activity'][activity]=group
    for metric in ('ppv','sensitivity','ppi_pair_coverage','core_time_coverage'):
        diffs=[]
        for sub in sorted({r['subject'] for r in local}):
            aa=[r['arms'] for r in local if r['subject']==sub]
            if all(a[k]['metrics'][metric] is not None for a in aa for k in ('baseline','q50')):
                diffs.append(np.mean([a['q50']['metrics'][metric]-a['baseline']['metrics'][metric] for a in aa]))
        boot=np.random.default_rng(20261020).choice(diffs,(10000,len(diffs)),replace=True).mean(axis=1) if diffs else None
        public['q50_minus_baseline'][metric]={'mean_difference':float(np.mean(diffs)) if diffs else None,'95_interval':np.quantile(boot,[.025,.975]).tolist() if diffs else None,'subjects':len(diffs)}
    (out/'records_local.json').write_text(json.dumps(local,indent=2,allow_nan=False))
    (ROOT/'docs/acceptance/PPG_RETENTION_DEV1.json').write_text(json.dumps(public,indent=2,allow_nan=False))
    print(json.dumps(public['q50_minus_baseline'],indent=2))
if __name__=='__main__':main()
