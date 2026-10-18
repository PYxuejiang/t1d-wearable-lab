"""Independent metric, weighting, out-of-fit stack and selection checks."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from verify_module2 import event_runs
from verify_mechanism import reconstruct,summary,rank_metrics,failure_diagnostics
from verify_smartwatch_replication import bootstrap


def main():
    dest=ROOT/'outputs/late_fusion_v4';config=json.loads((dest/'config.json').read_text());done=json.loads((dest/'completed.json').read_text())
    for path,digest in done['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    for path,key in [('predictions.parquet','prediction_sha256'),('selections_frozen_before_test.json','selection_sha256')]:
        assert hashlib.sha256((dest/path).read_bytes()).hexdigest()==done[key]
    raw=pd.read_parquet(ROOT/config['source_features']);source={};events={}
    for subject,g in raw.groupby('subject'):
        g=g.sort_values('decision_time');t=pd.DatetimeIndex(g.decision_time);bounds=[t[0]+(t[-1]-t[0])*v for v in [.6,.8]]
        ev=event_runs(pd.Series(g.label_proxy_mg_dl.to_numpy(),index=t));events[subject]=[(s,e) for s,e in ev if not any(s<b<e for b in bounds)]
        source[subject]=g.set_index('decision_time',drop=False)
        for kind in ['ecg','ppg','eda','acc','temp']:assert (g[kind+'_input_end'].dropna()<=g.loc[g[kind+'_input_end'].notna(),'decision_time']).all()
    audit=json.loads((dest/'audit.json').read_text())
    for a in audit:
        assert pd.Timestamp(a['inner_train_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(a['inner_cut'])
        assert pd.Timestamp(a['inner_holdout_first'])-pd.Timedelta(minutes=60)>=pd.Timestamp(a['inner_cut'])
        assert pd.Timestamp(a['outer_train_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(a['validation_first'])-pd.Timedelta(minutes=60)
        assert pd.Timestamp(a['validation_last'])+pd.Timedelta(minutes=15)<pd.Timestamp(a['test_first'])-pd.Timedelta(minutes=60)
    inner=pd.read_parquet(dest/'inner_predictions.parquet');tuning=json.loads((dest/'tuning.json').read_text());selected=json.loads((dest/'selected_parameters.json').read_text())
    for row in tuning:
        f=inner[inner.arm.eq(row['arm'])&inner.weighting.eq(row['weighting'])&inner.candidate.eq(row['candidate'])];aps=[]
        for subject,g in f.groupby('subject'):
            native=source[subject].loc[g.decision_time];assert native.split.eq('train').all()
            assert np.array_equal(native.label_low.to_numpy(),g.label_low.to_numpy())
            a=next(a for a in audit if a['subject']==subject);assert (g.decision_time-pd.Timedelta(minutes=60)>=pd.Timestamp(a['inner_cut'])).all()
            ap=rank_metrics(g.label_low,g.score)['ap']
            if ap is not None:aps.append(ap)
        expected=float(np.mean(aps)) if aps else None
        assert expected is None and row['inner_macro_ap'] is None or expected is not None and abs(expected-row['inner_macro_ap'])<1e-10
    for row in selected:
        choices=[r for r in tuning if (r['arm'],r['weighting'])==(row['arm'],row['weighting'])]
        assert row==max(choices,key=lambda r:r['inner_macro_ap'] if r['inner_macro_ap'] is not None else -1)
    val=pd.read_parquet(dest/'validation_predictions.parquet');pred=pd.read_parquet(dest/'predictions.parquet')
    stack=pd.read_parquet(dest/'stack_training.parquet');stack_error=0.
    for weighting,g in stack.groupby('weighting'):
        expected_weights=np.zeros(len(g));g=g.reset_index(drop=True)
        for subject,person in g.groupby('subject'):
            # Independent positive run reconstruction using full reference, before masking.
            native=source[subject];times=pd.DatetimeIndex(native.decision_time);labels=native.label_low.to_numpy(bool)
            ids=[];group=0
            for i,(t,y) in enumerate(zip(times,labels)):
                if i==0 or y!=labels[i-1] or (t-times[i-1]).total_seconds()>450:group+=1
                ids.append(group)
            ids=pd.Series(ids,index=times)
            assert np.array_equal(ids.loc[person.decision_time],person.low_run)
            for label,c in person.groupby('label_low'):
                if weighting=='point':w=np.ones(len(c))
                else:
                    groupvalues=c.low_run if label else pd.DatetimeIndex(c.decision_time).as_unit('ns').asi8//int(6*3600e9)
                    _,inverse,counts=np.unique(groupvalues,return_inverse=True,return_counts=True);w=1/counts[inverse]
                expected_weights[c.index]=w/w.sum()/person.label_low.nunique()
        expected_weights/=expected_weights.mean();assert np.allclose(expected_weights,g.weight,atol=1e-12)
        # Rebuild stack inputs from chosen out-of-fit predictions. No in-sample base scores.
        for j,modality in enumerate(['ecg','ppg','eda']):
            chosen=next(r for r in selected if r['arm']==modality and r['weighting']==weighting)
            f=inner[inner.arm.eq(modality)&inner.weighting.eq(weighting)&inner.candidate.eq(chosen['candidate'])]
            joined=g.merge(f[['subject','decision_time','score']],on=['subject','decision_time'],how='left',validate='one_to_one')
            pp=joined.score.to_numpy();valid=np.isfinite(pp);clipped=np.clip(pp,1e-4,1-1e-4)
            assert np.allclose(g['x'+str(j)],np.where(valid,np.log(clipped/(1-clipped)),0))
            assert np.array_equal(g['x'+str(j+3)].to_numpy(),valid.astype(float))
        xx=g[['x'+str(i) for i in range(8)]].to_numpy();scaler=StandardScaler().fit(xx)
        with threadpool_limits(2):m=LogisticRegression(C=.1,max_iter=1500,random_state=config['seed']).fit(scaler.transform(xx),g.label_low,sample_weight=g.weight)
        for phase in [val,pred[pred.budget.eq(1)&pred.view.eq('end_to_end')]]:
            f=phase[phase.weighting.eq(weighting)];target=f[f.arm.eq('late_stack')].sort_values(['subject','decision_time'])
            pp=[]
            for modality in ['ecg','ppg','eda']:
                right=f[f.arm.eq(modality)][['subject','decision_time','score']]
                pp.append(target[['subject','decision_time']].merge(right,on=['subject','decision_time'],validate='one_to_one').score.to_numpy())
            p=np.column_stack(pp);valid=np.isfinite(p);cp=np.clip(p,1e-4,1-1e-4)
            clock=np.vstack([source[s].loc[t,['hour_sin','hour_cos']].to_numpy(float) for s,t in zip(target.subject,target.decision_time)])
            design=np.column_stack([np.where(valid,np.log(cp/(1-cp)),0),valid.astype(float),clock]);mask=np.isfinite(target.score.to_numpy())
            calculated=m.predict_proba(scaler.transform(design[mask]))[:,1]
            error=float(np.max(np.abs(calculated-target.score.to_numpy()[mask])));assert error<1e-9;stack_error=max(stack_error,error)
            mean=f[f.arm.eq('late_mean')].sort_values(['subject','decision_time']).score.to_numpy()
            counts=valid.sum(axis=1);calc=np.divide(np.nansum(p,axis=1),counts,out=np.full(len(p),np.nan),where=counts>0)
            assert np.allclose(calc,mean,equal_nan=True)
    choices=json.loads((dest/'selections_frozen_before_test.json').read_text());candidates=json.loads((dest/'decision_candidates.json').read_text())
    for c in choices:
        trials=[r for r in candidates if r['arm']==c['arm'] and r['weighting']==c['weighting'] and r['validation']['false_alerts_per_person_day']<=c['budget']]
        rank=lambda r:(r['validation']['event_recall'] or 0,-r['validation']['false_alerts_per_person_day'],-r['policy_index'],r['threshold'])
        win=max(trials,key=rank);assert (win['policy'],win['threshold'])==(c['policy'],c['threshold'])
        rows=[]
        for subject,f in val[val.arm.eq(c['arm'])&val.weighting.eq(c['weighting'])].groupby('subject'):
            f=f.copy();f['policy']=c['policy'];f['threshold']=c['threshold'];rows.append(reconstruct(f,events[subject]))
        actual=summary(rows)
        for key in c['validation']:
            if key not in actual:continue
            a,b=actual[key],c['validation'][key];assert a is None and b is None or a is not None and b is not None and abs(a-b)<1e-10,(key,a,b)
    saved=json.loads((dest/'metrics_by_subject.json').read_text());keys=['subject','arm','weighting','budget','view'];lookup={tuple(r[k] for k in keys):r for r in saved}
    verified=[];maxdiff=0.;diagnostics=[]
    for key,f in pred.groupby(keys):
        subject,arm,weighting,budget,view=key;original=source[subject].loc[f.decision_time]
        assert original.split.eq('test').all() and np.array_equal(original.label_low.to_numpy(),f.label_low.to_numpy())
        wrist=original.available.to_numpy();ecg=(original.ecg_completeness.fillna(0).ge(.9)&original.ecg_valid.eq(1)).to_numpy()
        allowed=ecg if arm=='ecg' else wrist if arm in ['ppg','eda'] else wrist|ecg
        if view=='common_wrist':allowed=allowed&wrist
        assert np.array_equal(allowed,np.isfinite(f.score.to_numpy()))
        actual=reconstruct(f,events[subject]);savedrow=lookup[key]
        for k,v in actual.items():
            if k not in savedrow:continue
            b=savedrow[k];assert v is None and b is None or v is not None and b is not None and abs(v-b)<1e-9,(key,k,v,b)
            if v is not None:maxdiff=max(maxdiff,abs(v-b))
        choice=next(c for c in choices if (c['arm'],c['weighting'],c['budget'])==(arm,weighting,budget))
        assert f.policy.eq(choice['policy']).all() and f.threshold.eq(choice['threshold']).all()
        verified.append({**actual,**dict(zip(keys,key)),'budget':int(budget)})
        if arm=='late_stack' and weighting=='run' and budget==1 and view=='end_to_end':
            v=val[val.subject.eq(subject)&val.arm.eq(arm)&val.weighting.eq(weighting)].copy();v['policy']=f.policy.iloc[0];v['threshold']=f.threshold.iloc[0]
            diagnostics.append({'subject':subject,**failure_diagnostics(f,v,events[subject])})
    assert len(verified)==done['metric_groups']==392
    results={}
    for arm in config['arms']:
      for weighting in config['weighting']:
       for budget in config['budgets']:
        for view in config['views']:
            group=[r for r in verified if (r['arm'],r['weighting'],r['budget'],r['view'])==(arm,weighting,budget,view)]
            assert len(group)==7 and sum(r['reference_events'] for r in group)==30
            results[f'{arm}/{weighting}/b{budget}/{view}']=summary(group)
    contrasts={}
    for control,weight in [('early','run'),('mask_clock','run'),('late_stack','point')]:
        a={r['subject']:r for r in verified if (r['arm'],r['weighting'],r['budget'],r['view'])==(control,weight,1,'end_to_end')}
        b={r['subject']:r for r in verified if (r['arm'],r['weighting'],r['budget'],r['view'])==('late_stack','run',1,'end_to_end')}
        contrasts[control+'/'+weight]={k:bootstrap([b[s][k]-a[s][k] for s in a if a[s][k] is not None and b[s][k] is not None]) for k in ['ap','roc_auc','event_recall','coverage']}
    record={'stage':config['id'],'engineering_status':'passed','effect_status':results[config['primary']]['effect_status'],
            'groups_verified':len(verified),'inner_candidates_verified':len(tuning),'selected_validation_operating_points_verified':len(choices),
            'maximum_metric_difference':maxdiff,'stack_refit_maximum_score_difference':stack_error,'primary_key':config['primary'],
            'primary':results[config['primary']],'results':results,'paired_differences':contrasts,'failure_diagnostics':diagnostics,
            'metrics_by_subject':verified,'selected_parameters':selected,'selections':choices,'audit':audit,'source_sha256':done['source_sha256'],
            'limitations':[config['scope'],'Previously seen test cohort; unadjusted subject bootstrap; no independent efficacy confirmation.',
                          'Modality experts use existing coarse features, not a reproduction of author raw-waveform deep learning.',
                          'Base hyperparameters and stack fit share inner holdout; outer validation/test stay separate. Refit may shift stack score distributions.',
                          'All candidate ranks and selected validation outcomes checked; not every candidate model independently refitted.',
                          'Positive weighting uses low runs including brief lows; run labels never enter inference.',
                          'Single-modality AP has different availability; only identical union comparisons support paired AP contrasts.']}
    # Additional descriptive contrasts of frozen scores after seeing modality results.
    # These do not replace the registered primary or select a new threshold/model.
    extra={}
    for arm in ['ppg','eda']:
      for weight in config['weighting']:
        a={r['subject']:r for r in verified if (r['arm'],r['weighting'],r['budget'],r['view'])==('mask_clock',weight,1,'common_wrist')}
        b={r['subject']:r for r in verified if (r['arm'],r['weighting'],r['budget'],r['view'])==(arm,weight,1,'common_wrist')}
        extra[arm+'/'+weight]={k:bootstrap([b[s][k]-a[s][k] for s in a if a[s][k] is not None and b[s][k] is not None]) for k in ['ap','roc_auc','event_recall']}
    record['posthoc_modality_contrasts']={'scope':'Descriptive after seeing results; fixed original scores and thresholds, same wrist mask; unadjusted, not primary confirmation.','comparisons':extra}
    (dest/'verified_metrics.json').write_text(json.dumps(verified,indent=2))
    (ROOT/'docs/acceptance/V4_LATE_FUSION1.json').write_text(json.dumps(record,indent=2,allow_nan=False))
    print(json.dumps({'groups':len(verified),'primary':record['primary'],'contrasts':contrasts},indent=2))

if __name__=='__main__':main()
