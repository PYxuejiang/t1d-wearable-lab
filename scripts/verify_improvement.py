"""Independent v2 counts and same-opportunity v1 comparison; preserve failures."""
import json
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from verify_module2 import evaluate,event_runs
from t1d_lab.risk import aggregate_metrics,point_metrics


def main(folder='improvement_v2'):
    output=ROOT/'outputs'/folder
    config=json.loads((output/'summary.json').read_text())['protocol'];history=config['history_minutes']
    predictions=pd.read_parquet(output/'predictions.parquet');features=pd.read_parquet(output/'features.parquet')
    rows=json.loads((output/'metrics_by_subject.json').read_text());lookup={(r['subject'],r['experiment'],r['budget']):r for r in rows}
    selections=json.loads((output/'selections.json').read_text())
    for s in selections:
        assert not any(c.startswith('label') or 'glucose' in c for c in s['columns'])
        assert pd.Timestamp(s['train_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(s['validation_first'])-pd.Timedelta(minutes=history)
        assert pd.Timestamp(s['validation_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(s['test_first'])-pd.Timedelta(minutes=history)
    events={}
    for subject,g in features.groupby('subject'):
        ref=pd.Series(g.label_proxy_mg_dl.to_numpy(),index=pd.DatetimeIndex(g.decision_time))
        t=ref.index;bounds=[t[0]+(t[-1]-t[0])*r for r in [.6,.8]]
        events[subject]=[e for e in event_runs(ref) if not any(e[0]<b<e[1] for b in bounds)]
    verified=[];baseline=[]
    original=pd.read_parquet(ROOT/'outputs/module2_detection/predictions.parquet')
    original=original[original.protocol.eq('temporal')&original.model.eq('wrist_eda_temp')]
    for key,g in predictions.groupby(['subject','experiment','budget']):
        r=evaluate(g,events[key[0]]);saved=dict(lookup[key])
        for c in ['reference_events','matched_events','unmatched_alarms','alarms']:assert saved[c]==r[c],(key,c)
        assert abs(saved['observation_hours']-r['observation_hours'])<1e-8
        saved.update(coverage=r['coverage'],anchor_coverage=r['anchor_coverage'],events_with_input_opportunity=r['events_with_input_opportunity'],conditional_event_recall=r['conditional_event_recall'])
        verified.append(saved)
        if key[1:] == ('clock_baseline',1):
            f=g[['subject','decision_time','label_low','available']].merge(original[original.subject.eq(key[0])][['decision_time','score','threshold']],on='decision_time',how='left')
            assert f.threshold.notna().all();f.loc[~f.available,'score']=np.nan
            m=evaluate(f,events[key[0]]);m.update(point_metrics(f.label_low,f.score),subject=key[0],matches=[],event_recall=m['matched_events']/m['reference_events'] if m['reference_events'] else None,event_precision=m['matched_events']/m['alarms'] if m['alarms'] else None)
            baseline.append(m)
    results={e:{str(b):aggregate_metrics([r for r in verified if r['experiment']==e and r['budget']==b]) for b in [1,2,4]} for e in ['clock_baseline','static_selected','temporal_selected']}
    stage='V2_2' if config.get('include_device_summaries') else 'V2_1'
    record={'stage':stage,'engineering_status':'passed','evaluation_status':'independently_reconstructed_events_and_temporal_boundaries_passed','effect_status':results['temporal_selected']['1']['effect_status'],
        'scope':'Exploratory same-cohort temporal tests, not independent confirmation','groups_verified':len(verified),'count_mismatches':0,
        'results':results,'same_opportunity_v1_wrist_multimodal':aggregate_metrics(baseline),
        'limitations':['Longer history changes eligible event count from 31 to 30; v1 is recomputed on the identical opportunities.','Static model sparse hits do not establish improvement over the clock baseline.','Temporal features did not achieve primary event-detection target.']}
    (ROOT/'docs/acceptance'/f'{stage}.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    (output/'verified_metrics.json').write_text(json.dumps(verified,indent=2),encoding='utf-8')
    print(stage,'independently verified',len(verified),'groups; research target status',record['effect_status'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default='improvement_v2')
    main(parser.parse_args().folder)
