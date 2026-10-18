"""New fixed experiment; refuses to overwrite a completed/existing run."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from t1d_lab.mechanism import prepare,fit_normalizer,transform,event_metrics,aggregate,smooth_scores
from t1d_lab.late_fusion import COLUMNS,MODALITIES,available,training_weights,add_weight_groups,fit_model,predict,stack_design,mean_fusion
from t1d_lab.evaluation import reference_events
from t1d_lab.risk import point_metrics

def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
def times(frame):return pd.DatetimeIndex(frame.decision_time).as_unit('ns').asi8


def main():
    config=json.loads((ROOT/'configs/late_fusion_v4.json').read_text());dest=ROOT/'outputs'/config['output_directory']
    dest.mkdir(parents=True,exist_ok=False);save(dest/'config.json',config)
    raw=pd.read_parquet(ROOT/config['source_features']);frames=[];xs=[];xis=[];events={};audit=[];states={}
    for subject,source in raw.groupby('subject',sort=True):
        g=add_weight_groups(prepare(source));t=pd.DatetimeIndex(g.decision_time);bounds=[t[0]+(t[-1]-t[0])*v for v in [.6,.8]]
        ev=reference_events(pd.Series(g.label_proxy_mg_dl.to_numpy(),index=t),5,threshold=70)
        events[subject]=[(e.start.value,e.end.value) for e in ev if not e.left_censored and not any(e.start<b<e.end for b in bounds)]
        tr=g[g.split.eq('train')];cut=tr.decision_time.min()+(tr.decision_time.max()-tr.decision_time.min())*.75
        g['inner_train']=g.split.eq('train')&(g.decision_time+pd.Timedelta(minutes=15)<cut)
        g['inner_holdout']=g.split.eq('train')&(g.decision_time-pd.Timedelta(minutes=60)>=cut)
        state=fit_normalizer(tr);innerstate=fit_normalizer(g[g.inner_train]);states[subject]={'outer':state,'inner':innerstate}
        xs.append(transform(g,state));xis.append(transform(g,innerstate));frames.append(g)
        audit.append({'subject':subject,'inner_cut':str(cut),'inner_train_last':str(g.loc[g.inner_train,'decision_time'].max()),
                      'inner_holdout_first':str(g.loc[g.inner_holdout,'decision_time'].min()),
                      'outer_train_last':str(tr.decision_time.max()),'validation_first':str(g.loc[g.split.eq('validation'),'decision_time'].min()),
                      'validation_last':str(g.loc[g.split.eq('validation'),'decision_time'].max()),'test_first':str(g.loc[g.split.eq('test'),'decision_time'].min())})
    frame=pd.concat(frames,ignore_index=True);x=pd.concat(xs,ignore_index=True);xi=pd.concat(xis,ignore_index=True)
    save(dest/'audit.json',audit);save(dest/'normalizers.json',states)
    models={};selected={};tuning=[];inner_outputs=[];validation=[];stackers={};weight_audit=[];stack_training=[]
    inner=frame.inner_holdout.to_numpy();val=frame.split.eq('validation').to_numpy()
    with threadpool_limits(2):
      for weighting in config['weighting']:
        inner_scores={};val_scores={}
        for arm,columns in COLUMNS.items():
            mask=frame.inner_train.to_numpy()&available(frame,arm);w=training_weights(frame[mask],weighting)
            candidates=[];cache={}
            for name in config['base_candidates']:
                model,prior=fit_model(xi.loc[mask,columns],frame.loc[mask,'label_low'].to_numpy(int),w,name,config['seed'])
                support=inner&available(frame,arm);p=np.full(len(frame),np.nan);p[support]=predict(model,prior,xi.loc[support,columns])
                ap=[]
                for subject in sorted(events):
                    m=inner&frame.subject.eq(subject).to_numpy();v=point_metrics(frame.loc[m,'label_low'],p[m])
                    if v['ap'] is not None:ap.append(v['ap'])
                record={'arm':arm,'weighting':weighting,'candidate':name,'inner_macro_ap':float(np.mean(ap)) if ap else None,'ap_subjects':len(ap),'constant':model is None}
                tuning.append(record);candidates.append(record);cache[name]=p
                f=frame.loc[inner,['subject','decision_time','label_low']].copy();f['score']=p[inner];f['arm']=arm;f['weighting']=weighting;f['candidate']=name;inner_outputs.append(f)
            chosen=max(candidates,key=lambda r:r['inner_macro_ap'] if r['inner_macro_ap'] is not None else -1)
            selected[(arm,weighting)]=chosen;inner_scores[arm]=cache[chosen['candidate']]
            mask=frame.split.eq('train').to_numpy()&available(frame,arm);w=training_weights(frame[mask],weighting)
            model,prior=fit_model(x.loc[mask,columns],frame.loc[mask,'label_low'].to_numpy(int),w,chosen['candidate'],config['seed']);models[(arm,weighting)]=(model,prior)
            wa=frame.loc[mask,['subject','label_low','low_run','negative_block']].copy();wa['weight']=w
            weight_audit.extend({'arm':arm,'weighting':weighting,'subject':s,'label':int(y),'weight_sum':float(g.weight.sum()),'rows':len(g)} for (s,y),g in wa.groupby(['subject','label_low']))
            p=np.full(len(frame),np.nan);support=val&available(frame,arm);p[support]=predict(model,prior,x.loc[support,columns]);val_scores[arm]=p
            print('Selected',arm,weighting,chosen['candidate'],chosen['inner_macro_ap'],flush=True)
        design=stack_design(frame,inner_scores);mask=inner&available(frame,'early')
        stackrows=frame.loc[mask,['subject','decision_time','label_low','low_run','negative_block']].copy()
        for j in range(design.shape[1]):stackrows['x'+str(j)]=design[mask,j]
        stackrows['weight']=training_weights(frame[mask],weighting);stackrows['weighting']=weighting;stack_training.append(stackrows)
        model,prior=fit_model(design[mask],frame.loc[mask,'label_low'].to_numpy(int),training_weights(frame[mask],weighting),'logistic_C0.1',config['seed']);stackers[weighting]=(model,prior)
        p=np.full(len(frame),np.nan);mask=val&available(frame,'early');p[mask]=predict(model,prior,stack_design(frame,val_scores)[mask]);val_scores['late_stack']=p
        val_scores['late_mean']=mean_fusion(val_scores)
        for arm in config['arms']:
            f=frame.loc[val,['subject','decision_time','label_low','wrist_present','ecg_present']].copy();f['score']=val_scores[arm][val];f['arm']=arm;f['weighting']=weighting;validation.append(f)
    save(dest/'tuning.json',tuning);save(dest/'selected_parameters.json',list(selected.values()));save(dest/'weight_audit.json',weight_audit)
    pd.concat(inner_outputs,ignore_index=True).to_parquet(dest/'inner_predictions.parquet',index=False)
    pd.concat(stack_training,ignore_index=True).to_parquet(dest/'stack_training.parquet',index=False)
    validation=pd.concat(validation,ignore_index=True);validation.to_parquet(dest/'validation_predictions.parquet',index=False)
    candidates=[];selections=[]
    for (arm,weighting),block in validation.groupby(['arm','weighting'],sort=False):
        subjects={s:g for s,g in block.groupby('subject')};trials=[]
        for pi,policy in enumerate(config['policies']):
            p=np.concatenate([smooth_scores(times(f),f.score.to_numpy(),policy) for f in subjects.values()]);p=p[np.isfinite(p)]
            thresholds=np.unique(np.r_[np.quantile(p,np.linspace(0,1,config['threshold_quantiles'])) if len(p) else [],1.001])
            for threshold in thresholds:
                r=aggregate([event_metrics(times(f),f.score.to_numpy(),events[s],float(threshold),policy) for s,f in subjects.items()])
                row={'arm':arm,'weighting':weighting,'policy':policy,'policy_index':pi,'threshold':float(threshold),'validation':r};candidates.append(row);trials.append(row)
        for budget in config['budgets']:
            feasible=[r for r in trials if r['validation']['false_alerts_per_person_day']<=budget]
            chosen=max(feasible,key=lambda r:(r['validation']['event_recall'] or 0,-r['validation']['false_alerts_per_person_day'],-r['policy_index'],r['threshold']))
            selections.append({**chosen,'budget':budget})
        print('Decision frozen',arm,weighting,flush=True)
    save(dest/'decision_candidates.json',candidates);save(dest/'selections_frozen_before_test.json',selections)
    print('All selections written; test scoring starts',flush=True)
    predictions=[];metrics=[];test=frame.split.eq('test').to_numpy()
    with threadpool_limits(2):
      for weighting in config['weighting']:
        ps={}
        for arm,columns in COLUMNS.items():
            m,prior=models[(arm,weighting)];mask=test&available(frame,arm);p=np.full(len(frame),np.nan);p[mask]=predict(m,prior,x.loc[mask,columns]);ps[arm]=p
        ps['late_mean']=mean_fusion(ps);mask=test&available(frame,'early');m,prior=stackers[weighting]
        p=np.full(len(frame),np.nan);p[mask]=predict(m,prior,stack_design(frame,ps)[mask]);ps['late_stack']=p
        for choice in [r for r in selections if r['weighting']==weighting]:
            arm=choice['arm']
            for subject in sorted(events):
                mask=test&frame.subject.eq(subject).to_numpy();base=frame.loc[mask,['subject','decision_time','label_low','wrist_present','ecg_present']].copy()
                for view in config['views']:
                    f=base.copy();p=ps[arm][mask].copy()
                    if view=='common_wrist':p[~f.wrist_present.eq(1).to_numpy()]=np.nan
                    f['score']=p
                    key={k:choice[k] for k in ['arm','weighting','budget','policy','threshold']};key.update(subject=subject,view=view)
                    for k,v in key.items():f[k]=v
                    predictions.append(f);r=event_metrics(times(f),p,events[subject],choice['threshold'],choice['policy'])
                    r.update(point_metrics(f.label_low,smooth_scores(times(f),p,choice['policy'])));metrics.append({**r,**key})
    pd.concat(predictions,ignore_index=True).to_parquet(dest/'predictions.parquet',index=False);save(dest/'metrics_by_subject.json',metrics)
    paths=['configs/late_fusion_v4.json','scripts/run_late_fusion.py','src/t1d_lab/late_fusion.py','src/t1d_lab/mechanism.py',config['source_features']]
    save(dest/'completed.json',{'id':config['id'],'metric_groups':len(metrics),'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
         'selection_sha256':hashlib.sha256((dest/'selections_frozen_before_test.json').read_bytes()).hexdigest(),'prediction_sha256':hashlib.sha256((dest/'predictions.parquet').read_bytes()).hexdigest()})
    print('Completed',len(metrics),'groups; independent verification required',flush=True)

if __name__=='__main__':main()
