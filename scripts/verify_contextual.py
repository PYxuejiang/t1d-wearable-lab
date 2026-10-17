"""Independently reconstruct contextual point scores, splits and calibration."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit,expit
from sklearn.linear_model import LogisticRegression

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from verify_smartwatch_replication import independent_metrics,bootstrap
from t1d_lab.contextual import SETS


def reliability(y,p):
    y=np.asarray(y);p=np.asarray(p);valid=np.isfinite(p);y=y[valid];p=p[valid];bins=[]
    for a,b in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
        mask=(p>=a)&(p<b if b<1 else p<=b)
        bins.append({'lower':float(a),'upper':float(b),'n':int(mask.sum()),'score_mean':float(p[mask].mean()) if mask.any() else None,'positive_fraction':float(y[mask].mean()) if mask.any() else None})
    return bins


def main():
    folder=ROOT/'outputs/smartwatch_context_v1_1'
    if not (folder/'completed.json').exists():raise RuntimeError('Incomplete experiment; no acceptance')
    config=json.loads((folder/'config.json').read_text());done=json.loads((folder/'completed.json').read_text())
    assert done['config_sha256']==hashlib.sha256((ROOT/'configs/smartwatch_context_v1_1.json').read_bytes()).hexdigest()
    p=pd.read_parquet(folder/'predictions.parquet');val=pd.read_parquet(folder/'validation_predictions.parquet')
    rows=json.loads((folder/'metrics_by_subject.json').read_text());selection=json.loads((folder/'selections.json').read_text());candidates=json.loads((folder/'candidates.json').read_text())
    lookup={(r['subject'],r['feature_set'],r['view']):r for r in rows};maxdiff=0.;caldiff=0.;calibration_audit=[]
    for (subject,feature,view),g in p.groupby(['subject','feature_set','view']):
        source=pd.read_csv(ROOT/'data/raw/smartwatch_hypo'/f'{subject}.csv')
        assert np.array_equal(g.hypoglycemia.to_numpy(),source.loc[g.source_row,'hypoglycemia'].to_numpy())
        m=independent_metrics(g.hypoglycemia,g.score,float(g.threshold.iloc[0]));r=lookup[(subject,feature,view)]
        for c in ['tp','fp','tn','fn']:assert m[c]==r[c]
        for c in ['ap','roc_auc']:
            if m[c] is not None:maxdiff=max(maxdiff,abs(m[c]-r[c]))
        valid=g.score.notna();brier=float(((g.loc[valid,'score']-g.loc[valid,'hypoglycemia'])**2).mean())
        maxdiff=max(maxdiff,abs(brier-r['brier']))
        assert (g.score.dropna().between(0,1)).all()
    for s in selection:
        assert s['columns']==SETS[s['feature_set']]
        assert not {'cgm','hypoglycemia','source_row','hour'}.intersection(s['columns'])
        assert s['train_last_source_row']+255<s['validation_first_source_row']
        assert s['validation_last_source_row']+255<s['test_first_source_row']
        choices=[c for c in candidates if c['subject']==s['subject'] and c['feature_set']==s['feature_set']]
        assert s['method']==max(choices,key=lambda r:r['validation_ap'] if r['validation_ap'] is not None else -1.)['method']
        v=val[val.subject.eq(s['subject'])&val.feature_set.eq(s['feature_set'])];fit=s['calibration']
        test=p[p.subject.eq(s['subject'])&p.feature_set.eq(s['feature_set'])]
        raw=test[test.view.eq('raw')].sort_values('source_row');cal=test[test.view.eq('calibrated')].sort_values('source_row')
        assert np.array_equal(raw.source_row,cal.source_row)
        if v.hypoglycemia.nunique()==2:
            fitted=LogisticRegression(C=1,random_state=20261016).fit(logit(np.clip(v.raw_score.to_numpy(),1e-6,1-1e-6)).reshape(-1,1),v.hypoglycemia)
            assert abs(float(fitted.coef_[0,0])-fit['slope'])<1e-10
            assert abs(float(fitted.intercept_[0])-fit['intercept'])<1e-10
        for view,column in [('raw','raw_score'),('calibrated','calibrated_score')]:
            threshold_candidates=[];truth=v.hypoglycemia.to_numpy(dtype=bool);scores=v[column].to_numpy()
            if truth.any() and (~truth).any():
                for threshold in np.unique(scores)[::-1]:
                    positive=scores>=threshold
                    tpr=float(positive[truth].mean());fpr=float(positive[~truth].mean())
                    if fpr<=.2:threshold_candidates.append((tpr-fpr,float(threshold)))
            expected_threshold=max(threshold_candidates,key=lambda x:x[0])[1] if threshold_candidates else 1.001
            assert abs(expected_threshold-s['thresholds'][view])<1e-10
        expected=expit(fit['slope']*logit(np.clip(raw.score.to_numpy(),1e-6,1-1e-6))+fit['intercept']) if fit['type']=='sigmoid' else np.where(raw.score.notna(),fit['validation_prevalence'],np.nan)
        finite=cal.score.notna().to_numpy();caldiff=max(caldiff,float(np.max(np.abs(expected[finite]-cal.score.to_numpy()[finite]))))
        if fit['type']=='sigmoid':
            assert fit['slope']>0
            # Clipping extreme logits can create ties; it cannot reverse ordering.
            order=np.argsort(raw.score.to_numpy()[finite],kind='stable')
            assert np.all(np.diff(cal.score.to_numpy()[finite][order])>=-1e-12)
        calibration_audit.append({'subject':s['subject'],'feature_set':s['feature_set'],'type':fit['type'],'reason':fit['reason'],'validation_rows':fit['fit_rows'],'validation_positives':fit['positive_rows']})
    for subject,g in p.groupby('subject'):
        locations=[set(h.source_row) for _,h in g.groupby(['feature_set','view'])]
        assert all(locations[0]==r for r in locations)
    assert maxdiff<1e-8 and caldiff<1e-8
    features=list(config['feature_sets']);views=['raw','calibrated','training_prior']
    summary={f:{v:{key:bootstrap([r[key] for r in rows if r['feature_set']==f and r['view']==v]) for key in ['ap','roc_auc','brier','sensitivity','specificity','coverage','positive_fraction']} for v in views} for f in features}
    contrasts={}
    for a,b in [('clock','context_time'),('clock','wearable_time'),('wearable_time','combined'),('context_time','combined')]:
        contrasts[a+'__to__'+b]={key:bootstrap([lookup[(s,b,'raw')][key]-lookup[(s,a,'raw')][key] for s in sorted(p.subject.unique()) if lookup[(s,b,'raw')][key] is not None and lookup[(s,a,'raw')][key] is not None]) for key in ['ap','roc_auc','sensitivity','specificity']}
    calibration={}
    for f in features:
        calibration[f]={name:bootstrap([lookup[(s,f,reference)]['brier']-lookup[(s,f,'calibrated')]['brier'] for s in sorted(p.subject.unique())]) for name,reference in [('calibrated_vs_raw','raw'),('calibrated_vs_prior','training_prior')]}
    primary=contrasts['wearable_time__to__combined']['ap']
    record={'stage':'CONTEXT_V1_1','engineering_status':'passed','evaluation_status':'source_rows_feature_whitelist_candidate_selection_calibration_and_independent_metrics_passed',
        'effect_status':'passed' if primary['95_interval'] is not None and primary['95_interval'][0]>0 else 'inconclusive',
        'effect_scope':'Exploratory primary contextual AP contrast only; no event-alarm acceptance',
        'groups_verified':len(lookup),'subject_count':len(p.subject.unique()),'maximum_metric_difference':maxdiff,'maximum_calibration_difference':caldiff,
        'summary':summary,'paired_gain':contrasts,'calibration_brier_reductions':calibration,'calibration_audit':calibration_audit,
        'metrics_by_subject':rows,'source_context_audit':json.loads((ROOT/'outputs/audit/context_audit.json').read_text()),
        'limitations':['Same previously viewed processed cohort; all contrasts exploratory and intervals unadjusted.','Missing complete timestamps: row support is nominal, not proven temporal or prospective validation; no alarm/day or event metrics.','Source IOB is a unitless past-injection activity index, not remaining insulin dose.','Context requires diary entries; missing fields and zeros do not establish true absence of injections or food.','Personal training and validation require earlier source-reference labels. Calibration uses the same validation segment used in model/threshold selection; no separate calibration cohort.','Point-level observed-reference opportunity fraction is not true sensor uptime; no actual device measurement-coverage claim.']}
    (ROOT/'docs/acceptance/CONTEXT_V1_1.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    (folder/'verified_summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    bins={f+'/'+view:reliability(g.hypoglycemia,g.score) for (f,view),g in p.groupby(['feature_set','view'])}
    (folder/'reliability.json').write_text(json.dumps(bins,indent=2),encoding='utf-8')
    print('CONTEXT V1.1 verified',len(lookup),'groups; primary contextual AP effect',record['effect_status'])


if __name__=='__main__':main()
