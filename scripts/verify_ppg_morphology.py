"""Independent event/point reconstruction and same-mask regression verification."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from verify_module2 import event_runs
from verify_mechanism import reconstruct,summary,rank_metrics,failure_diagnostics
from verify_smartwatch_replication import bootstrap

def equal(a,b):
    assert a is None and b is None or a is not None and b is not None and abs(a-b)<1e-9,(a,b)

def main():
    dest=ROOT/'outputs/ppg_morphology_v5';cfg=json.loads((dest/'config.json').read_text());done=json.loads((dest/'completed.json').read_text())
    for path,sha in done['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
    for path,key in [('predictions.parquet','prediction_sha256'),('selections_frozen_before_test.json','selection_sha256')]:assert hashlib.sha256((dest/path).read_bytes()).hexdigest()==done[key]
    raw=pd.read_parquet(ROOT/cfg['source_features']);source={};events={};audits=json.loads((dest/'audit.json').read_text());states=json.loads((dest/'normalizers.json').read_text())
    for s,g in raw.groupby('subject'):
        g=g.sort_values('decision_time');t=pd.DatetimeIndex(g.decision_time);bounds=[t[0]+(t[-1]-t[0])*v for v in [.6,.8]]
        events[s]=[(a,b) for a,b in event_runs(pd.Series(g.label_proxy_mg_dl.to_numpy(),index=t)) if not any(a<cut<b for cut in bounds)]
        source[s]=g.set_index('decision_time',drop=False);a=next(a for a in audits if a['subject']==s)
        assert pd.Timestamp(a['inner_train_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(a['inner_cut'])
        assert pd.Timestamp(a['inner_holdout_first'])-pd.Timedelta(minutes=60)>=pd.Timestamp(a['inner_cut'])
        assert pd.Timestamp(a['outer_train_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(a['validation_first'])-pd.Timedelta(minutes=60)
        assert pd.Timestamp(a['validation_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(a['test_first'])-pd.Timedelta(minutes=60)
        pm=pd.read_parquet(ROOT/cfg['extraction_directory']/f'{s}.parquet');assert not pm.decision_time.duplicated().any()
        assert (pm.pm_input_end<=pm.decision_time).all();native=source[s].loc[pm.decision_time];assert native.available.all()
        # Independent train-only morphology center/scale audit. Missing rows contribute no values.
        for key,mask in [('pm_outer',native.split.eq('train').to_numpy()),('pm_inner',(native.split.eq('train')&(native.decision_time+pd.Timedelta(minutes=15)<pd.Timestamp(a['inner_cut']))).to_numpy())]:
            for col,p in states[s][key].items():
                v=pm.loc[mask,col].replace([np.inf,-np.inf],np.nan).dropna();equal(p['center'],float(v.median()) if len(v) else 0.)
                equal(p['scale'],max(float(v.quantile(.75)-v.quantile(.25)),.01) if len(v) else 1.);assert p['rows']==len(v)
    inner=pd.read_parquet(dest/'inner_predictions.parquet');tuning=json.loads((dest/'tuning.json').read_text());selected=json.loads((dest/'selected_parameters.json').read_text())
    for row in tuning:
        aps=[]
        for s,g in inner[inner.arm.eq(row['arm'])&inner.candidate.eq(row['candidate'])].groupby('subject'):
            native=source[s].loc[g.decision_time];assert native.split.eq('train').all();assert np.array_equal(native.label_low,g.label_low)
            a=next(a for a in audits if a['subject']==s);assert (g.decision_time-pd.Timedelta(minutes=60)>=pd.Timestamp(a['inner_cut'])).all()
            assert np.array_equal(native.available,np.isfinite(g.score));ap=rank_metrics(g.label_low,g.score)['ap']
            if ap is not None:aps.append(ap)
        equal(row['inner_macro_ap'],float(np.mean(aps)) if aps else None)
    for row in selected:assert row==max([r for r in tuning if r['arm']==row['arm']],key=lambda r:r['inner_macro_ap'] if r['inner_macro_ap'] is not None else -1)
    val=pd.read_parquet(dest/'validation_predictions.parquet');pred=pd.read_parquet(dest/'predictions.parquet')
    for phase,split in [(val,'validation'),(pred,'test')]:
        for s,g in phase.groupby('subject'):
            native=source[s].loc[g.decision_time];assert native.split.eq(split).all();assert np.array_equal(native.label_low,g.label_low)
            assert np.array_equal(native.available,np.isfinite(g.score))
    choices=json.loads((dest/'selections_frozen_before_test.json').read_text());candidates=json.loads((dest/'decision_candidates.json').read_text())
    for c in choices:
        trials=[r for r in candidates if r['arm']==c['arm'] and r['validation']['false_alerts_per_person_day']<=c['budget']]
        best=max(trials,key=lambda r:(r['validation']['event_recall'] or 0,-r['validation']['false_alerts_per_person_day'],-r['policy_index'],r['threshold']))
        assert (best['threshold'],best['policy'])==(c['threshold'],c['policy']);rows=[]
        for s,g in val[val.arm.eq(c['arm'])].groupby('subject'):
            g=g.copy();g['threshold']=c['threshold'];g['policy']=c['policy'];rows.append(reconstruct(g,events[s]))
        actual=summary(rows)
        for k,v in c['validation'].items():
            if k in actual:equal(v,actual[k])
    saved=json.loads((dest/'metrics_by_subject.json').read_text());keys=['subject','arm','budget'];lookup={tuple(r[k] for k in keys):r for r in saved};verified=[];diagnostics=[]
    for key,g in pred.groupby(keys):
        s,arm,budget=key;c=next(c for c in choices if c['arm']==arm and c['budget']==budget)
        assert g.threshold.eq(c['threshold']).all() and g.policy.eq(c['policy']).all()
        actual,alarms=reconstruct(g,events[s],return_alarms=True);original=lookup[key]
        for k,v in actual.items():
            if k in original:equal(v,original[k])
        selected_events=[(a,b) for a,b in events[s] if g.decision_time.min()<=a<=g.decision_time.max()]
        timely=sum(any(a<=t<=min(b,a+pd.Timedelta(minutes=15)) for t in alarms) for a,b in selected_events)
        verified.append({**actual,**dict(zip(keys,key)),'budget':int(budget),'events_hit_within15min':int(timely)})
        if arm=='morphology' and budget==1:
            v=val[val.subject.eq(s)&val.arm.eq(arm)].copy();v['policy']=c['policy'];v['threshold']=c['threshold']
            diagnostics.append({'subject':s,**failure_diagnostics(g,v,events[s])})
    assert len(verified)==done['metric_groups']==42 and len(tuning)==9 and len(choices)==6
    results={}
    for arm in cfg['arms']:
        for budget in cfg['budgets']:
            rows=[r for r in verified if r['arm']==arm and r['budget']==budget];assert len(rows)==7 and sum(r['reference_events'] for r in rows)==30
            result=summary(rows);result['events_hit_within15min']=sum(r['events_hit_within15min'] for r in rows)
            result['micro_event_recall']=result['matched_events']/result['reference_events']
            result['micro_event_precision']=result['matched_events']/result['alarms'] if result['alarms'] else None
            results[f'{arm}/b{budget}']=result
    contrasts={}
    for arm in ['coarse','quality_time']:
        a={r['subject']:r for r in verified if r['arm']==arm and r['budget']==1};b={r['subject']:r for r in verified if r['arm']=='morphology' and r['budget']==1}
        contrasts[arm]={k:bootstrap([b[s][k]-a[s][k] for s in a if a[s][k] is not None and b[s][k] is not None]) for k in ['ap','roc_auc','event_recall','coverage']}
    # Coarse route must reproduce frozen v4 PPG point scores and operating points.
    old=pd.read_parquet(ROOT/'outputs/late_fusion_v4/predictions.parquet');old=old[old.arm.eq('ppg')&old.weighting.eq('point')&old.view.eq('end_to_end')]
    current=pred[pred.arm.eq('coarse')];joined=current.merge(old,on=['subject','decision_time','budget'],validate='one_to_one',suffixes=('_new','_old'))
    assert len(joined)==len(current)==len(old);assert np.allclose(joined.score_new,joined.score_old,atol=1e-10,equal_nan=True)
    assert np.allclose(joined.threshold_new,joined.threshold_old,atol=1e-10) and joined.policy_new.eq(joined.policy_old).all()
    maxdiff=float(np.nanmax(np.abs(joined.score_new-joined.score_old)))
    record={'stage':cfg['id'],'engineering_status':'passed','effect_status':results[cfg['primary']]['effect_status'],
        'primary_key':cfg['primary'],'primary':results[cfg['primary']],'results':results,'paired_differences':contrasts,
        'groups_verified':len(verified),'inner_candidates_verified':len(tuning),'selected_validation_operating_points_verified':len(choices),
        'coarse_v4_maximum_score_difference':maxdiff,'metrics_by_subject':verified,'selected_parameters':selected,'selections':choices,
        'failure_diagnostics':diagnostics,'audit':audits,'source_sha256':done['source_sha256'],
        'limitations':[cfg['scope'],'Seen7-person cohort, exploratory unadjusted subject bootstrap; no external confirmation.',
        'Soft waveform descriptors have synthetic tests, not expert beat annotation accuracy. PPI is not ECG RR.',
        'Same old full-wrist mask; cannot pass80%coverage. All30events retained; low-quality points not deleted.',
        'First complete lexical source session used in overlaps; physical reference clock remains unresolved.',
        'Checks independently reconstruct selected validation and all test metrics, not every candidate model refit.']}
    (ROOT/'docs/acceptance/V5_PPG_MORPH1.json').write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'primary':record['primary'],'results':results,'contrasts':contrasts,'coarse_score_difference':maxdiff},indent=2))

if __name__=='__main__':main()
