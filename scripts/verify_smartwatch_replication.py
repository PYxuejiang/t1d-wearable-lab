"""Independent rank-AUC/AP, confusion counts and paired-subject uncertainty."""
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT=Path(__file__).resolve().parents[1]


def independent_metrics(y,p,threshold):
    y=np.asarray(y,dtype=bool);p=np.asarray(p,dtype=float);valid=np.isfinite(p);y=y[valid];p=p[valid]
    positive=int(y.sum());negative=len(y)-positive
    auc=(rankdata(p)[y].sum()-positive*(positive+1)/2)/(positive*negative) if positive and negative else None
    # AP at unique thresholds; tied probabilities enter as one whole group.
    order=np.argsort(-p,kind='stable');ys=y[order];ps=p[order]
    ends=np.r_[np.flatnonzero(np.diff(ps)!=0),len(p)-1] if len(p) else np.array([],dtype=int)
    tp=np.cumsum(ys)[ends] if len(p) else np.array([]);precision=tp/(ends+1) if len(p) else np.array([])
    ap=float(np.sum(np.diff(np.r_[0,tp])*precision)/positive) if positive and negative else None
    alarm=p>=threshold
    return {'roc_auc':float(auc) if auc is not None else None,'ap':ap,'tp':int((y&alarm).sum()),'fn':int((y&~alarm).sum()),'fp':int((~y&alarm).sum()),'tn':int((~y&~alarm).sum())}


def bootstrap(values):
    x=np.asarray([v for v in values if v is not None],dtype=float)
    if not len(x):return {'n':0,'mean':None,'95_interval':None}
    rng=np.random.default_rng(20261016);samples=x[rng.integers(0,len(x),(2000,len(x)))].mean(axis=1)
    return {'n':len(x),'mean':float(x.mean()),'95_interval':np.quantile(samples,[.025,.975]).tolist()}


def main(folder_name='smartwatch_replication_v1'):
    folder=ROOT/'outputs'/folder_name
    config=json.loads((folder/'config.json').read_text());personal=config['protocol']=='personalized_row_holdout'
    p=pd.read_parquet(folder/'predictions.parquet');rows=json.loads((folder/'metrics_by_subject.json').read_text());lookup={(r['subject'],r['feature_set']):r for r in rows}
    difference=0.
    for key,g in p.groupby(['subject','feature_set']):
        r=independent_metrics(g.hypoglycemia,g.score,float(g.threshold.iloc[0]));saved=lookup[key]
        for k in ['tp','fn','fp','tn']:assert r[k]==saved[k]
        for k in ['ap','roc_auc']:
            if r[k] is not None:difference=max(difference,abs(r[k]-saved[k]))
        raw=pd.read_csv(ROOT/'data/raw/smartwatch_hypo'/f'{key[0]}.csv')
        assert np.array_equal(raw.loc[g.source_row,'hypoglycemia'].to_numpy(),g.hypoglycemia.to_numpy())
    assert difference<1e-8
    selections=json.loads((folder/'selections.json').read_text())
    for r in selections:
        if personal:
            assert r['training_subjects']==[r['subject']] and r['validation_subjects']==[r['subject']]
            assert r['training_last_source_row']+120<r['validation_first_source_row']
            assert r['validation_last_source_row']+120<r['test_first_source_row']
        else:assert r['subject'] not in r['training_subjects']+r['validation_subjects']
        assert not {'cgm','hypoglycemia','IOB','time_since_lastmeal','time_since_lastmeal_ord'}.intersection(r['columns'])
    sets=['clock','wearable','wearable_time']
    # All feature configurations must evaluate identical reference anchors per subject.
    for subject,g in p.groupby('subject'):
        anchors=[set(g[g.feature_set.eq(s)].source_row) for s in sets];assert all(x==anchors[0] for x in anchors)
    summary={s:{k:bootstrap([r[k] for r in rows if r['feature_set']==s]) for k in ['roc_auc','ap','sensitivity','specificity','coverage','positive_fraction']} for s in sets}
    paired={}
    for a,b in [('clock','wearable'),('clock','wearable_time'),('wearable','wearable_time')]:
        shared=sorted(p.subject.unique());paired[a+'__to__'+b]={k:bootstrap([lookup[(s,b)][k]-lookup[(s,a)][k] for s in shared if lookup[(s,b)][k] is not None and lookup[(s,a)][k] is not None]) for k in ['roc_auc','ap','sensitivity','specificity']}
    main_gain=paired['clock__to__wearable']
    effect='passed_point_discrimination_exploration' if main_gain['roc_auc']['95_interval'][0]>0 and main_gain['ap']['95_interval'][0]>0 else 'inconclusive'
    stage='COHORT_SW_PERSONAL1' if personal else 'COHORT_SW1'
    record={'stage':stage,'engineering_status':'passed','evaluation_status':'independent_rank_metrics_confusions_and_split_checks_passed',
        'effect_status':effect,'scope':'Exploratory personalized source-row holdout, temporal order conditional on source' if personal else 'Independent cohort methodology exploration; source-defined point classification, not the v1 sensor configuration or event endpoint.',
        'groups_verified':len(lookup),'subject_count':len(p.subject.unique()),'maximum_metric_difference':difference,
        'summary':summary,'paired_gain':paired,'metrics_by_subject':rows,'audit':json.loads((folder/'audit.json').read_text()),
        'limitations':['Processed source CSVs lack timestamp and day identifiers; no verified chronological order, event matching, alarm/day or true time coverage claims.','Labels follow source <4 mmol/L plus duration rules and backfilled reference, unlike PhysioCGM native <70mg/dL.','Precomputed wearable feature causality is based on source code review, not full raw-data reconstruction.','No clinical or prospective efficacy conclusion; input sensors differ from PhysioCGM.','Patient-specific calibration not used; training/validation row partition is descriptive within other subjects and test subject is entirely unseen.']}
    audit=json.loads((folder/'audit.json').read_text());aligned=[r['subject'] for r in audit if r.get('minute_row_hour_agreement',0)>=.99]
    if personal:record['hour_agreement_subgroup']={s:{k:bootstrap([r[k] for r in rows if r['feature_set']==s and r['subject'] in aligned]) for k in ['roc_auc','ap','sensitivity','specificity']} for s in sets}
    (ROOT/'docs/acceptance'/f'{stage}.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    (folder/'verified_summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('Verified',len(lookup),'personalized source-row groups' if personal else 'independent-subject groups','; max metric difference',difference,'effect',effect)
    print(json.dumps(summary,indent=2));print(json.dumps(paired,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default='smartwatch_replication_v1')
    main(parser.parse_args().folder)
