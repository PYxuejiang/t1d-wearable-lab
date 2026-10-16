"""Independent metric recomputation and validation-only simple-baseline selection."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.forecasting import metric_rows, paired_bootstrap


def main():
    output=ROOT/'outputs/module1_forecasting'
    p=pd.read_parquet(output/'predictions.parquet')
    f=pd.read_parquet(ROOT/'data/processed/brist1d_features.parquet')
    if (p.input_max_time > p.decision_time).any(): raise AssertionError('Future input')
    distance=((p.target_time-p.decision_time).dt.total_seconds()/60-30).abs()
    if not (distance <= 2.5).all(): raise AssertionError('Invalid forecast horizon')
    if p.duplicated(['protocol','model','anchor_id']).any(): raise AssertionError('Duplicate test prediction')
    selections=[]
    selected=[]
    for (protocol,subject),g in p.groupby(['protocol','subject']):
        val=f[f.split.eq('validation') & f.target.notna() & (f.subject.eq(subject) if protocol=='temporal' else f.subject.ne(subject))].copy()
        val['persistence']=val.bg_lag_0
        val['trend']=np.clip(val.bg_lag_0+(val.bg_lag_0-val.bg_lag_15.fillna(val.bg_lag_0))*2,0,40)
        errors={name:float(val.assign(error=abs(val[name]-val.target)).groupby('subject').error.mean().mean()) for name in ['persistence','trend']}
        choice=min(errors,key=errors.get)
        chosen=g[g.model.eq(choice)].copy()
        chosen['model']='selected_simple'
        selected.append(chosen)
        selections.append({'protocol':protocol,'subject':subject,'selected':choice,'validation_mae':errors})
        sets=g.groupby('model').anchor_id.apply(set)
        if not all(s==sets.iloc[0] for s in sets): raise AssertionError('Nonpaired model comparison')
        if protocol=='temporal' and not chosen.decision_time.isin(f[f.subject.eq(subject)&f.split.eq('test')].decision_time).all():
            raise AssertionError('Wrong chronological test boundary')
    original=metric_rows(p)
    # Independent arithmetic from saved predictions, not model internals.
    max_delta=0.
    for row in original.itertuples():
        a=p[(p.protocol==row.protocol)&(p.subject==row.subject)&(p.model==row.model)]
        error=a.prediction.to_numpy()-a.target.to_numpy()
        mae=sum(abs(float(e)) for e in error)/len(error)
        max_delta=max(max_delta,abs(mae-row.mae))
    if max_delta>1e-8: raise AssertionError('Metric mismatch')
    augmented=pd.concat([p,*selected],ignore_index=True)
    augmented.to_parquet(output/'verified_predictions.parquet',index=False)
    metrics=metric_rows(augmented)
    metrics.to_csv(output/'verified_metrics_by_subject.csv',index=False)
    report={'task':'30-minute glucose forecasting','unit':'mmol/L','baseline_selection':'validation-only subject-equal MAE','results':{}}
    for protocol,g in metrics.groupby('protocol'):
        report['results'][protocol]={
            'subject_equal_metrics':g.groupby('model')[['mae','rmse','bias']].mean().to_dict(orient='index'),
            'comparisons':[paired_bootstrap(g,'selected_simple','cgm'),paired_bootstrap(g,'context','fusion')],
            'n_subjects':int(g.subject.nunique()),
        }
    (output/'verified_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'baseline_selection.json').write_text(json.dumps(selections,indent=2),encoding='utf-8')
    gate={'stage':'S2a','engineering_status':'passed','evaluation_status':'passed_regression_only','effect_status':{k:v['comparisons'][1]['effect_status'] for k,v in report['results'].items()},'verified_test_predictions':len(p),'subject_count':int(p.subject.nunique()),'future_input_violations':0,'target_tolerance_violations':0,'paired_anchor_sets':'identical','independent_mae_max_difference':max_delta,'limitations':['Regression acceptance only; incident-event risk requires separate evaluation.','Missing wearable values are allowed in the model; availability subgroups must be reported.','Processed-record arrival times are unavailable.'],'results':report['results']}
    (ROOT/'docs/acceptance/S2a.json').write_text(json.dumps(gate,indent=2),encoding='utf-8')
    print(json.dumps(gate,indent=2))


if __name__=='__main__': main()
