"""Nested parameter tuning, activity residuals and ECG failover; no test selection."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.mechanism import prepare,availability,fit_normalizer,transform,SETS,POLICIES,event_metrics,aggregate,smooth_scores,NS_MINUTE
from t1d_lab.evaluation import reference_events
from t1d_lab.risk import point_metrics


def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')


def specifications(config):
    grid=config['grid'];rows=[]
    for c in grid['logistic_C']:
        for weight in grid['class_weight']:rows.append({'model':'logistic','C':c,'class_weight':weight})
    for leaves in grid['hgb_leaves']:
        for weight in grid['class_weight']:rows.append({'model':'hgb','leaves':leaves,'class_weight':weight})
    return rows


def fitted(x,y,weights,spec,config):
    prior=float(np.average(y,weights=weights)) if len(y) else 0.
    if len(y)<100 or np.sum(y)<5 or len(np.unique(y))<2:return None,prior
    if spec['model']=='logistic':model=LogisticRegression(C=spec['C'],class_weight=spec['class_weight'],max_iter=1500,random_state=config['seed'])
    else:
        p=config['grid'];model=HistGradientBoostingClassifier(max_iter=p['hgb_iterations'],learning_rate=p['hgb_learning_rate'],
            max_leaf_nodes=spec['leaves'],min_samples_leaf=p['hgb_min_leaf'],l2_regularization=p['hgb_l2'],
            class_weight=spec['class_weight'],early_stopping=False,random_state=config['seed'])
    pipeline=make_pipeline(SimpleImputer(strategy='constant',fill_value=0,keep_empty_features=True),StandardScaler(),model)
    pipeline.fit(x,y,**{list(pipeline.named_steps)[-1]+'__sample_weight':weights})
    return pipeline,prior


def scores(model,prior,x):return model.predict_proba(x)[:,1] if model is not None else np.repeat(prior,len(x))


def time_array(frame):return pd.DatetimeIndex(frame.decision_time).as_unit('ns').asi8


def main():
    path=ROOT/'configs/mechanism_v3_1.json';config=json.loads(path.read_text());dest=ROOT/'outputs'/config['output_directory']
    dest.mkdir(parents=True,exist_ok=False);save(dest/'config.json',config)
    source=ROOT/config['source_features'];raw=pd.read_parquet(source)
    subjects=sorted(raw.subject.unique());frames={};events={};audit=[];normalizers={};inner_states={};inner={};matrices={};inner_matrices={}
    for subject in subjects:
        g=prepare(raw[raw.subject.eq(subject)])
        all_times=pd.DatetimeIndex(g.decision_time);bounds=[all_times[0]+(all_times[-1]-all_times[0])*v for v in [.6,.8]]
        ev=reference_events(pd.Series(g.label_proxy_mg_dl.to_numpy(),index=all_times),5,threshold=70)
        ev=[e for e in ev if not e.left_censored and not any(e.start<b<e.end for b in bounds)]
        events[subject]=[(e.start.value,e.end.value) for e in ev]
        train=g[g.split.eq('train')];cut=train.decision_time.min()+(train.decision_time.max()-train.decision_time.min())*.75
        a=g.split.eq('train')&(g.decision_time+pd.Timedelta(minutes=15)<cut)
        b=g.split.eq('train')&(g.decision_time-pd.Timedelta(minutes=60)>=cut)
        inner[subject]={'train':a.to_numpy(),'validation':b.to_numpy()}
        normalizers[subject]=fit_normalizer(train);inner_states[subject]=fit_normalizer(g[a])
        frames[subject]=g;matrices[subject]=transform(g,normalizers[subject]);inner_matrices[subject]=transform(g,inner_states[subject])
        record={'subject':subject,'inner_cut':str(cut),'inner_train_last':str(g.loc[a,'decision_time'].max()),
            'inner_validation_first':str(g.loc[b,'decision_time'].min()),'outer_train_last':str(train.decision_time.max()),
            'outer_validation_first':str(g.loc[g.split.eq('validation'),'decision_time'].min()),
            'outer_validation_last':str(g.loc[g.split.eq('validation'),'decision_time'].max()),
            'test_first':str(g.loc[g.split.eq('test'),'decision_time'].min())}
        for split in ['train','validation']:
            f=g[g.split.eq(split)];t=time_array(f)
            record[split]={}
            for mask_name,arm in [('wrist','personal_raw'),('union','pooled_fallback')]:
                p=np.where(availability(f,arm),.1,np.nan)
                r=event_metrics(t,p,events[subject],1.001,'legacy_edge')
                record[split][mask_name]={k:r[k] for k in ['reference_events','events_with_input_opportunity','coverage','observable_event_ceiling']}
                record[split][mask_name].update(rows=len(f),available_positive_points=int(f.loc[np.isfinite(p),'label_low'].sum()))
        audit.append(record)
    save(dest/'audit.json',audit);save(dest/'normalizers.json',normalizers);save(dest/'inner_normalizers.json',inner_states)
    specs=specifications(config);tuning=[];inner_predictions=[];params={};models={};validation=[]
    # Every hyperparameter uses only the nested partition inside earlier training.
    with threadpool_limits(2):
        for arm in config['arms']:
            pooled=arm.startswith('pooled_');blocks=[subjects] if pooled else [[s] for s in subjects]
            for block in blocks:
                candidate_rows=[]
                for index,spec in enumerate(specs):
                    xs=[];ys=[];ws=[]
                    for subject in block:
                        g=frames[subject];mask=inner[subject]['train']&availability(g,arm);x=inner_matrices[subject].loc[mask,SETS[arm]].to_numpy()
                        xs.append(x);ys.append(g.loc[mask,'label_low'].to_numpy(dtype=int));ws.append(np.repeat(1/max(1,len(x)),len(x)))
                    x=np.concatenate(xs);y=np.concatenate(ys);w=np.concatenate(ws);w=w/w.mean() if len(w) else w
                    model,prior=fitted(x,y,w,spec,config);aps=[]
                    for subject in block:
                        g=frames[subject];mask=inner[subject]['validation']&availability(g,arm)
                        p=scores(model,prior,inner_matrices[subject].loc[mask,SETS[arm]].to_numpy()) if mask.any() else np.array([])
                        m=point_metrics(g.loc[mask,'label_low'],p)
                        if m['ap'] is not None:aps.append(m['ap'])
                        f=g.loc[mask,['subject','decision_time','label_low']].copy();f['arm']=arm;f['parameter_index']=index;f['score']=p
                        inner_predictions.append(f)
                    ap=float(np.mean(aps)) if aps else None
                    row={'arm':arm,'subjects':block,'parameter_index':index,'parameters':spec,'inner_macro_ap':ap,'inner_ap_subjects':len(aps),'constant_fallback':model is None}
                    tuning.append(row);candidate_rows.append(row)
                chosen=max(candidate_rows,key=lambda r:r['inner_macro_ap'] if r['inner_macro_ap'] is not None else -1.)
                for subject in block:params[(subject,arm)]=chosen
                xs=[];ys=[];ws=[]
                for subject in block:
                    g=frames[subject];mask=g.split.eq('train').to_numpy()&availability(g,arm);x=matrices[subject].loc[mask,SETS[arm]].to_numpy()
                    xs.append(x);ys.append(g.loc[mask,'label_low'].to_numpy(dtype=int));ws.append(np.repeat(1/max(1,len(x)),len(x)))
                x=np.concatenate(xs);y=np.concatenate(ys);w=np.concatenate(ws);w=w/w.mean() if len(w) else w
                model,prior=fitted(x,y,w,chosen['parameters'],config)
                for subject in block:
                    models[(subject,arm)]=(model,prior)
                    g=frames[subject];mask=g.split.eq('validation').to_numpy();f=g.loc[mask,['subject','decision_time','label_low','wrist_present','ecg_present']].copy()
                    p=np.full(len(f),np.nan);valid=availability(g,arm)&mask
                    p[availability(f,arm)]=scores(model,prior,matrices[subject].loc[valid,SETS[arm]].to_numpy()) if valid.any() else []
                    f['score']=p;f['arm']=arm;validation.append(f)
                print('Tuned',arm,','.join(block),'parameter',chosen['parameter_index'],'inner AP',chosen['inner_macro_ap'],flush=True)
    save(dest/'tuning.json',tuning)
    pd.concat(inner_predictions,ignore_index=True).to_parquet(dest/'inner_predictions.parquet',index=False)
    val=pd.concat(validation,ignore_index=True);val.to_parquet(dest/'validation_predictions.parquet',index=False)
    # Select alert policies on outer validation. No test score has been computed.
    options=[];selections=[]
    for arm in config['arms']:
        blocks={s:val[val.subject.eq(s)&val.arm.eq(arm)] for s in subjects}
        for mode in config['calibration_modes']:
            scopes=[subjects] if mode=='pooled_validation' else [[s] for s in subjects]
            for block in scopes:
                trials=[]
                for policy_index,policy in enumerate(config['policies']):
                    finite=np.concatenate([smooth_scores(time_array(blocks[s]),blocks[s].score.to_numpy(),policy) for s in block])
                    finite=finite[np.isfinite(finite)]
                    thresholds=np.unique(np.r_[np.quantile(finite,np.linspace(0,1,config['threshold_quantiles'])) if len(finite) else [],1.001])
                    for threshold in thresholds:
                        rows=[]
                        for subject in block:
                            f=blocks[subject];rows.append(event_metrics(time_array(f),f.score.to_numpy(),events[subject],float(threshold),policy))
                        r=aggregate(rows)
                        row={'arm':arm,'calibration_mode':mode,'subjects':block,'policy':policy,'policy_index':policy_index,'threshold':float(threshold),'validation':r}
                        options.append(row);trials.append(row)
                for budget in config['alarm_budgets_per_person_day']:
                    feasible=[r for r in trials if r['validation']['false_alerts_per_person_day'] is not None and r['validation']['false_alerts_per_person_day']<=budget]
                    chosen=max(feasible,key=lambda r:(r['validation']['event_recall'] or 0,-r['validation']['false_alerts_per_person_day'],-r['policy_index'],r['threshold']))
                    for subject in block:selections.append({**chosen,'subject':subject,'budget':budget,'parameter_index':params[(subject,arm)]['parameter_index'],'columns':SETS[arm]})
                print('Validation selected',arm,mode,','.join(block),flush=True)
    save(dest/'operating_candidates.json',options);save(dest/'selections_frozen_before_test.json',selections)
    print('All model and policy choices frozen; starting test scoring',flush=True)
    predictions=[];rows=[]
    with threadpool_limits(2):
        for subject in subjects:
            g=frames[subject];test=g.split.eq('test').to_numpy();f=g.loc[test,['subject','decision_time','label_low','wrist_present','ecg_present']].copy()
            for arm in config['arms']:
                model,prior=models[(subject,arm)];raw_score=np.full(len(f),np.nan);mask=test&availability(g,arm)
                raw_score[availability(f,arm)]=scores(model,prior,matrices[subject].loc[mask,SETS[arm]].to_numpy()) if mask.any() else []
                for selection in [r for r in selections if r['subject']==subject and r['arm']==arm]:
                    for view in config['views']:
                        p=raw_score.copy()
                        if view=='common_wrist':p[~f.wrist_present.eq(1).to_numpy()]=np.nan
                        key={k:selection[k] for k in ['arm','calibration_mode','subject','budget','policy','threshold','parameter_index']};key['view']=view
                        r=event_metrics(time_array(f),p,events[subject],selection['threshold'],selection['policy'])
                        smoothed=smooth_scores(time_array(f),p,selection['policy']);r.update(point_metrics(f.label_low,smoothed));r.update(key);rows.append(r)
                        out=f.copy();out['score']=p
                        for k,v in key.items():out[k]=v
                        predictions.append(out)
    pd.concat(predictions,ignore_index=True).to_parquet(dest/'predictions.parquet',index=False)
    save(dest/'metrics_by_subject.json',rows)
    fingerprints={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['configs/mechanism_v3_1.json','src/t1d_lab/mechanism.py','scripts/run_mechanism.py',config['source_features']]}
    save(dest/'completed.json',{'id':config['id'],'subjects':subjects,'metric_groups':len(rows),'source_and_protocol_sha256':fingerprints,
        'selection_sha256':hashlib.sha256((dest/'selections_frozen_before_test.json').read_bytes()).hexdigest(),
        'test_predictions_sha256':hashlib.sha256((dest/'predictions.parquet').read_bytes()).hexdigest()})
    print('Completed',len(rows),'groups; independent verification required',flush=True)


if __name__=='__main__':main()
