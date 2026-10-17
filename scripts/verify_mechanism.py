"""Independent policy/count/coverage reconstruction and nested selection audit."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from verify_module2 import event_runs,evaluate
from verify_smartwatch_replication import independent_metrics,bootstrap


def rank_metrics(labels,p):
    result=independent_metrics(labels,p,.5)
    p=np.asarray(p,dtype=float);y=np.asarray(labels,dtype=float);valid=np.isfinite(p)&np.isfinite(y)
    result.update(point_n=int(valid.sum()),positive_fraction=float(y[valid].mean()) if valid.any() else None,
                  brier=float(np.mean((p[valid]-y[valid])**2)) if valid.any() else None)
    return result


def smoothed(f,policy):
    p=f.score.to_numpy(dtype=float)
    if not policy.startswith('smooth_'):return p.copy()
    t=pd.DatetimeIndex(f.decision_time)
    breaks=np.r_[True,np.diff(t.as_unit('ns').asi8)>450e9]|~np.isfinite(p)|np.r_[True,~np.isfinite(p[:-1])]
    groups=np.cumsum(breaks);out=np.full(len(f),np.nan)
    for group in np.unique(groups):
        positions=np.flatnonzero((groups==group)&np.isfinite(p))
        out[positions]=pd.Series(p[positions]).ewm(span=3,adjust=False).mean().to_numpy()
    return out


def reconstruct(f,events,return_alarms=False):
    f=f.sort_values('decision_time');t=pd.DatetimeIndex(f.decision_time)
    policy=f.policy.iloc[0];threshold=float(f.threshold.iloc[0]);p=smoothed(f,policy)
    events=[e for e in events if t[0]<=e[0]<=t[-1]]
    if policy=='legacy_edge':
        original=f.copy();original['score']=p
        old=evaluate(original,events)
        # Reconstruct alarm timestamps as well, with original edge semantics.
        alarm_times=[];active=False;ready=None
        for i,(time,value) in enumerate(zip(t,p)):
            if i and time-t[i-1]>pd.Timedelta(seconds=450):active=False;ready=None
            if not np.isfinite(value) or value<threshold:
                if active:ready=time+pd.Timedelta(minutes=30)
                active=False
            elif not active:
                if ready is None or time>=ready:alarm_times.append(time)
                active=True
    else:
        alarm_times=[];active=False;last_alert=None
        for i,(time,value) in enumerate(zip(t,p)):
            continuous=i>0 and time-t[i-1]<=pd.Timedelta(seconds=450)
            if not continuous:active=False;last_alert=None
            if not np.isfinite(value):active=False;continue
            previous_high=continuous and np.isfinite(p[i-1]) and p[i-1]>=threshold
            previous_low=continuous and np.isfinite(p[i-1]) and p[i-1]<threshold
            if value<threshold:
                if previous_low:active=False
                continue
            ready=last_alert is None or time-last_alert>=pd.Timedelta(minutes=30)
            if ready and ((not active and previous_high) or (active and policy=='smooth_remind30')):
                alarm_times.append(time);last_alert=time;active=True
    used=set();delays=[];observable=0
    for start,end in events:
        observable+=int(np.isfinite(p[(t>=start)&(t<=end)]).any())
        choices=[i for i,time in enumerate(alarm_times) if i not in used and start<=time<=end]
        if choices:
            i=choices[0];used.add(i);delays.append((alarm_times[i]-start).total_seconds()/60)
    minutes=np.diff(t.as_unit('ns').asi8)/60e9;observed=(minutes>0)&(minutes<=7.5);total=minutes[observed].sum()
    support=np.isfinite(p[:-1])&np.isfinite(p[1:])
    r={'reference_events':len(events),'matched_events':len(used),'alarms':len(alarm_times),
       'unmatched_alarms':len(alarm_times)-len(used),'observation_hours':float(total/60),
       'event_recall':len(used)/len(events) if events else None,
       'event_precision':len(used)/len(alarm_times) if alarm_times else None,
       'false_alerts_per_person_day':(len(alarm_times)-len(used))/(total/1440) if total else None,
       'coverage':float(minutes[observed&support].sum()/total) if total else None,
       'anchor_coverage':float(np.isfinite(p).mean()),'events_with_input_opportunity':observable,
       'observable_event_ceiling':observable/len(events) if events else None,
       'conditional_event_recall':len(used)/observable if observable else None,
       'delay_median_minutes':float(np.median(delays)) if delays else None}
    if policy=='legacy_edge':
        for c in ['reference_events','matched_events','alarms','unmatched_alarms']:assert r[c]==old[c]
    m=rank_metrics(f.label_low,p);r.update({k:m[k] for k in ['point_n','ap','roc_auc','brier','positive_fraction']})
    valid=np.isfinite(p);y=f.label_low.to_numpy(dtype=bool)[valid];above=p[valid]>=threshold
    tp=int((y&above).sum());fp=int((~y&above).sum());tn=int((~y&~above).sum());fn=int((y&~above).sum())
    r.update(point_tp=tp,point_fp=fp,point_tn=tn,point_fn=fn,
             threshold_point_sensitivity=tp/(tp+fn) if tp+fn else None,
             threshold_point_specificity=tn/(tn+fp) if tn+fp else None)
    return (r,alarm_times) if return_alarms else r


def failure_diagnostics(frame,validation,events):
    """Descriptive diagnostics only; do not turn near misses into detections."""
    f=frame.sort_values('decision_time');r,alarms=reconstruct(f,events,return_alarms=True)
    t=pd.DatetimeIndex(f.decision_time);p=smoothed(f,f.policy.iloc[0]);threshold=float(f.threshold.iloc[0])
    ev=[e for e in events if t[0]<=e[0]<=t[-1]];used=set();misses={'no_input':0,'score_never_above_threshold':0,'above_threshold_without_event_alert':0}
    for start,end in ev:
        choices=[i for i,a in enumerate(alarms) if i not in used and start<=a<=end]
        if choices:used.add(choices[0]);continue
        values=p[(t>=start)&(t<=end)]
        if not np.isfinite(values).any():misses['no_input']+=1
        elif not (values>=threshold).any():misses['score_never_above_threshold']+=1
        else:misses['above_threshold_without_event_alert']+=1
    timing={'duplicate_inside_reference_event':0,'within30min_before_onset':0,'within30min_after_end':0,'other':0}
    for i,a in enumerate(alarms):
        if i in used:continue
        if any(start<=a<=end for start,end in ev):key='duplicate_inside_reference_event'
        elif any(start-pd.Timedelta(minutes=30)<=a<start for start,end in ev):key='within30min_before_onset'
        elif any(end<a<=end+pd.Timedelta(minutes=30) for start,end in ev):key='within30min_after_end'
        else:key='other'
        timing[key]+=1
    distributions={}
    for phase,g in [('validation',validation),('test',f)]:
        values=smoothed(g,f.policy.iloc[0]);y=g.label_low.to_numpy(dtype=bool)
        distributions[phase]={}
        for name,mask in [('reference_normal',~y),('reference_low',y)]:
            a=values[mask&np.isfinite(values)]
            distributions[phase][name]={'n':len(a),'quantiles_10_50_90':np.quantile(a,[.1,.5,.9]).tolist() if len(a) else None}
    oracle=f.copy();oracle['score']=np.where(np.isfinite(f.score),f.label_low.astype(float),np.nan);oracle['threshold']=.5
    ideal=reconstruct(oracle,events)
    assert sum(misses.values())==r['reference_events']-r['matched_events']
    assert sum(timing.values())==r['unmatched_alarms']
    return {'miss_reasons':misses,'unmatched_alert_timing':timing,'score_distributions':distributions,
            'fixed_policy_perfect_point_oracle_matched_events':ideal['matched_events'],
            'oracle_scope':'Counterfactual labels on available anchors with this fixed policy; not an attainable learned-model result.'}


def summary(rows):
    macro=['event_recall','event_precision','coverage','anchor_coverage','observable_event_ceiling',
           'conditional_event_recall','ap','roc_auc','brier','threshold_point_sensitivity','threshold_point_specificity']
    r={k:float(np.mean([x[k] for x in rows if x.get(k) is not None])) if any(x.get(k) is not None for x in rows) else None for k in macro}
    for k in ['reference_events','matched_events','alarms','unmatched_alarms','observation_hours','events_with_input_opportunity']:r[k]=sum(x[k] for x in rows)
    r['false_alerts_per_person_day']=r['unmatched_alarms']/(r['observation_hours']/24) if r['observation_hours'] else None
    r['effect_status']='passed' if r['event_recall'] is not None and r['event_recall']>=.8 and r['coverage'] is not None and r['coverage']>=.8 and r['false_alerts_per_person_day'] is not None and r['false_alerts_per_person_day']<=1 else 'failed'
    return r


def selection_rank(r):return (r['validation']['event_recall'] or 0,-r['validation']['false_alerts_per_person_day'],-r['policy_index'],r['threshold'])


def main():
    dest=ROOT/'outputs/mechanism_v3_1';config=json.loads((dest/'config.json').read_text());done=json.loads((dest/'completed.json').read_text())
    for p,digest in done['source_and_protocol_sha256'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest
    assert hashlib.sha256((dest/'selections_frozen_before_test.json').read_bytes()).hexdigest()==done['selection_sha256']
    assert hashlib.sha256((dest/'predictions.parquet').read_bytes()).hexdigest()==done['test_predictions_sha256']
    frames=pd.read_parquet(ROOT/config['source_features']);events={};source={}
    audit=json.loads((dest/'audit.json').read_text());normalizers=json.loads((dest/'normalizers.json').read_text())
    for subject,g in frames.groupby('subject'):
        original=pd.read_parquet(ROOT/'data/processed'/f'{subject}_signal_features.parquet').set_index('decision_time')
        assert np.array_equal(original.loc[g.decision_time,'label_proxy_mg_dl'].to_numpy(),g.label_proxy_mg_dl.to_numpy())
        t=pd.DatetimeIndex(g.decision_time);boundaries=[t[0]+(t[-1]-t[0])*x for x in [.6,.8]]
        ev=event_runs(pd.Series(g.label_proxy_mg_dl.to_numpy(),index=t));events[subject]=[e for e in ev if not any(e[0]<b<e[1] for b in boundaries)]
        source[subject]=g.set_index('decision_time')
        assert normalizers[subject]['training_rows']==int(g.split.eq('train').sum())
        for col in g.columns:
            if col.endswith('_input_end'):assert not (pd.to_datetime(g[col])>g.decision_time).any()
    for row in audit:
        for a,b in [('inner_train_last','inner_validation_first'),('outer_train_last','outer_validation_first'),('outer_validation_last','test_first')]:
            assert pd.Timestamp(row[a])+pd.Timedelta(minutes=15)<pd.Timestamp(row[b])-pd.Timedelta(minutes=60)
    tuning=json.loads((dest/'tuning.json').read_text());inner=pd.read_parquet(dest/'inner_predictions.parquet')
    for row in tuning:
        group=inner[inner.arm.eq(row['arm'])&inner.parameter_index.eq(row['parameter_index'])&inner.subject.isin(row['subjects'])]
        aps=[]
        for _,f in group.groupby('subject'):
            ap=rank_metrics(f.label_low,f.score)['ap']
            if ap is not None:aps.append(ap)
        expected=float(np.mean(aps)) if aps else None
        assert expected is None and row['inner_macro_ap'] is None or expected is not None and abs(expected-row['inner_macro_ap'])<1e-10
    options=json.loads((dest/'operating_candidates.json').read_text());selection=json.loads((dest/'selections_frozen_before_test.json').read_text())
    val=pd.read_parquet(dest/'validation_predictions.parquet');validation_checked=set()
    for chosen in selection:
        assert not any('label' in c or 'glucose' in c or 'cgm' in c for c in chosen['columns'])
        candidates=[r for r in tuning if r['arm']==chosen['arm'] and chosen['subject'] in r['subjects']]
        parameter=max(candidates,key=lambda r:r['inner_macro_ap'] if r['inner_macro_ap'] is not None else -1.)
        assert parameter['parameter_index']==chosen['parameter_index']
        trials=[r for r in options if r['arm']==chosen['arm'] and r['calibration_mode']==chosen['calibration_mode'] and r['subjects']==chosen['subjects'] and r['validation']['false_alerts_per_person_day']<=chosen['budget']]
        winner=max(trials,key=selection_rank)
        assert (winner['policy'],winner['threshold'])==(chosen['policy'],chosen['threshold'])
        key=(chosen['arm'],tuple(chosen['subjects']),chosen['policy'],chosen['threshold'])
        if key not in validation_checked:
            rows=[]
            for subject in chosen['subjects']:
                f=val[val.subject.eq(subject)&val.arm.eq(chosen['arm'])].copy();f['policy']=chosen['policy'];f['threshold']=chosen['threshold']
                rows.append(reconstruct(f,events[subject]))
            value=summary(rows)
            for k in ['event_recall','false_alerts_per_person_day','coverage','reference_events','matched_events']:
                assert value[k] is None and chosen['validation'][k] is None or value[k] is not None and abs(value[k]-chosen['validation'][k])<1e-10
            validation_checked.add(key)
    p=pd.read_parquet(dest/'predictions.parquet');saved=json.loads((dest/'metrics_by_subject.json').read_text())
    keys=['subject','arm','calibration_mode','budget','view'];lookup={tuple(r[k] for k in keys):r for r in saved};checked=[];maxdiff=0.
    assert len(lookup)==done['metric_groups']==336
    for key,f in p.groupby(keys):
        original=source[key[0]].loc[f.decision_time]
        assert original.split.eq('test').all() and np.array_equal(original.label_low.to_numpy(),f.label_low.to_numpy())
        allowed=original.available.to_numpy() if key[1] not in ['pooled_fallback','pooled_mask_clock'] else original.available.to_numpy()|(original.ecg_completeness.fillna(0).ge(.9)&original.ecg_valid.eq(1)).to_numpy()
        if key[-1]=='common_wrist':allowed &= original.available.to_numpy()
        assert np.array_equal(np.isfinite(f.score),allowed)
        r=reconstruct(f,events[key[0]])
        for k,v in r.items():
            if k not in lookup[key]:continue
            expected=lookup[key][k]
            assert v is None and expected is None or v is not None and expected is not None and abs(v-expected)<1e-9,(key,k,v,expected)
            if v is not None:maxdiff=max(maxdiff,abs(v-expected))
        r.update(dict(zip(keys,key)),budget=int(key[3]),policy=f.policy.iloc[0],threshold=float(f.threshold.iloc[0]),parameter_index=int(f.parameter_index.iloc[0]));checked.append(r)
    # Primary contrasts all keep the full original reference-event denominator.
    results={}
    for arm in config['arms']:
        for mode in config['calibration_modes']:
            for budget in config['alarm_budgets_per_person_day']:
                for view in config['views']:
                    group=[r for r in checked if r['arm']==arm and r['calibration_mode']==mode and r['budget']==budget and r['view']==view]
                    assert len(group)==7 and sum(r['reference_events'] for r in group)==30
                    results[f'{arm}/{mode}/b{budget}/{view}']=summary(group)
    primary_key='pooled_fallback/pooled_validation/b1/end_to_end'
    baseline=[];old=pd.read_parquet(ROOT/'outputs/improvement_v2/predictions.parquet')
    for (subject,experiment),f in old[old.budget.eq(1)].groupby(['subject','experiment']):
        f=f.copy();f['policy']='legacy_edge';r=reconstruct(f,events[subject]);r.update(subject=subject,experiment=experiment);baseline.append(r)
    old_summary={e:summary([r for r in baseline if r['experiment']==e]) for e in ['clock_baseline','static_selected','temporal_selected']}
    diagnostics=[]
    for key,f in p[p.view.eq('end_to_end')].groupby(['subject','arm','calibration_mode','budget']):
        if key[2]!='pooled_validation':continue
        validation=val[val.subject.eq(key[0])&val.arm.eq(key[1])].copy();validation['policy']=f.policy.iloc[0];validation['threshold']=float(f.threshold.iloc[0])
        diagnostics.append({'subject':key[0],'arm':key[1],'budget':int(key[3]),**failure_diagnostics(f,validation,events[key[0]])})
    contrasts={}
    for control in ['pooled_mask_clock','pooled_residual','personal_residual']:
        for view in config['views']:
            a={r['subject']:r for r in checked if r['arm']==control and r['calibration_mode']=='pooled_validation' and r['budget']==1 and r['view']==view}
            b={r['subject']:r for r in checked if r['arm']=='pooled_fallback' and r['calibration_mode']=='pooled_validation' and r['budget']==1 and r['view']==view}
            comparable_ap=view=='common_wrist' or control=='pooled_mask_clock'
            contrasts[f'{control}__to__pooled_fallback/{view}']={k:bootstrap([b[s][k]-a[s][k] for s in a if b[s][k] is not None and a[s][k] is not None]) for k in ['event_recall','coverage']+(['ap'] if comparable_ap else [])}
            contrasts[f'{control}__to__pooled_fallback/{view}']['ap_same_scored_reference_anchors']=comparable_ap
    record={'stage':config['id'],'engineering_status':'passed','evaluation_status':'source_labels_nested_selection_selected_validation_policies_and_all_test_counts_independently_reconstructed',
        'effect_status':results[primary_key]['effect_status'],'scope':config['scope'],'groups_verified':len(checked),
        'selected_validation_configurations_verified':len(validation_checked),'maximum_metric_difference':maxdiff,
        'primary_key':primary_key,'primary':results[primary_key],'results':results,'paired_differences':contrasts,
        'same_opportunity_v2':old_summary,'metrics_by_subject':checked,'training_validation_audit':audit,'failure_diagnostics':diagnostics,
        'selected_parameters':[{k:r[k] for k in ['arm','subjects','parameter_index','parameters','inner_macro_ap','inner_ap_subjects']} for r in tuning
            if any(s['arm']==r['arm'] and s['subject'] in r['subjects'] and s['parameter_index']==r['parameter_index'] for s in selection)],
        'selections':selection,'source_and_protocol_sha256':done['source_and_protocol_sha256'],
        'limitations':['Previously viewed7-person cohort; all improvements exploratory, intervals unadjusted;30testevents.',
            'ECG failover uses a chest sensor; not a wrist-only result or a validated new hardware requirement.',
            'CGM/chest wall-clock relation remains a source assumption; no score-optimised time shifts.',
            'Reference-normal personal fitting uses earlierCGM labels; not zero-calibration or unseen-person inference.',
            'Inner temporal positive folds can be sparse/single-class. All retained; ties follow fixed order.',
            'Shared thresholds use the7people earlier validation; not LOSO or external validation.',
            'Failover changes both training opportunities and inputs; changes are strategy-level, not isolated causal sensor gains.',
            'PointAP uses available reference anchors; only common-wrist comparisons share score availability across regimes.',
            'Selected validation outcomes independently checked; all stored candidate selection ranks checked, not every trial refitted.',
            '30-minute repeat policies change notification behavior; evaluated separately with every unmatched alert counted.']}
    (dest/'verified_metrics.json').write_text(json.dumps(checked,indent=2),encoding='utf-8')
    (ROOT/'docs/acceptance/V3_MECHANISM1.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'groups':len(checked),'primary':record['primary'],'same_opportunity_v2':old_summary},indent=2))


if __name__=='__main__':main()
