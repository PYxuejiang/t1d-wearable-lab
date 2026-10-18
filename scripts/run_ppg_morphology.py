"""Frozen same-mask PPG information experiment; refuses existing output directory."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from t1d_lab.mechanism import prepare,fit_normalizer,transform,event_metrics,aggregate,smooth_scores
from t1d_lab.late_fusion import COLUMNS,training_weights,fit_model,predict
from t1d_lab.ppg_morphology import QUALITY,MORPH
from t1d_lab.evaluation import reference_events
from t1d_lab.risk import point_metrics
from run_late_fusion import save,times

PM=[f'pm_{k}_{s}' for k in QUALITY+MORPH for s in ['median','iqr']]+['pm_short_valid_fraction']
QC=[f'pm_{k}_{s}' for k in QUALITY for s in ['median','iqr']]+['pm_short_valid_fraction']
ARMS={'coarse':COLUMNS['ppg'],'quality_time':QC+['hour_sin','hour_cos'],
      'morphology':COLUMNS['ppg']+PM}
for name in ['quality_time','morphology']:
    ARMS[name]=ARMS[name]+[c+'_missing' for c in (QC if name=='quality_time' else PM)]


def pm_normalizer(train):
    result={}
    for c in PM:
        v=train[c].replace([np.inf,-np.inf],np.nan).dropna()
        result[c]={'center':float(v.median()) if len(v) else 0.,
                   'scale':max(float(v.quantile(.75)-v.quantile(.25)),.01) if len(v) else 1.,'rows':len(v)}
    return result


def pm_transform(g,x,state):
    for c,p in state.items():
        v=g[c].replace([np.inf,-np.inf],np.nan)
        x[c+'_missing']=v.isna().astype(float)
        x[c]=((v-p['center'])/p['scale']).clip(-8,8)
    return x


def main():
    config=json.loads((ROOT/'configs/ppg_morphology_v5.json').read_text());dest=ROOT/'outputs'/config['output_directory']
    raw=pd.read_parquet(ROOT/config['source_features']);files=[]
    for s in sorted(raw.subject.unique()):
        p=ROOT/config['extraction_directory']/f'{s}.parquet';m=json.loads(p.with_suffix('.json').read_text())
        assert hashlib.sha256(p.read_bytes()).hexdigest()==m['features_sha256']
        assert hashlib.sha256((ROOT/'src/t1d_lab/ppg_morphology.py').read_bytes()).hexdigest()==m['extractor_sha256']
        files.extend([str(p.relative_to(ROOT)),str(p.with_suffix('.json').relative_to(ROOT))])
    dest.mkdir(parents=True,exist_ok=False);save(dest/'config.json',config)
    frames=[];xs=[];xis=[];events={};audit=[];states={}
    for s,source in raw.groupby('subject',sort=True):
        g=prepare(source);pm=pd.read_parquet(ROOT/config['extraction_directory']/f'{s}.parquet')
        assert (pm.pm_input_end<=pm.decision_time).all()
        g=g.merge(pm,on=['subject','decision_time'],how='left',validate='one_to_one')
        t=pd.DatetimeIndex(g.decision_time);bounds=[t[0]+(t[-1]-t[0])*v for v in [.6,.8]]
        ev=reference_events(pd.Series(g.label_proxy_mg_dl.to_numpy(),index=t),5,threshold=70)
        events[s]=[(e.start.value,e.end.value) for e in ev if not e.left_censored and not any(e.start<b<e.end for b in bounds)]
        tr=g[g.split.eq('train')];cut=tr.decision_time.min()+(tr.decision_time.max()-tr.decision_time.min())*.75
        g['inner_train']=g.split.eq('train')&(g.decision_time+pd.Timedelta(minutes=15)<cut)
        g['inner_holdout']=g.split.eq('train')&(g.decision_time-pd.Timedelta(minutes=60)>=cut)
        it=g[g.inner_train];state=fit_normalizer(tr);istate=fit_normalizer(it)
        ps=pm_normalizer(tr);ips=pm_normalizer(it);states[s]={'outer':state,'inner':istate,'pm_outer':ps,'pm_inner':ips}
        xs.append(pm_transform(g,transform(g,state),ps));xis.append(pm_transform(g,transform(g,istate),ips));frames.append(g)
        audit.append({'subject':s,'inner_cut':str(cut),'inner_train_last':str(it.decision_time.max()),
            'inner_holdout_first':str(g.loc[g.inner_holdout,'decision_time'].min()),'outer_train_last':str(tr.decision_time.max()),
            'validation_first':str(g.loc[g.split.eq('validation'),'decision_time'].min()),'validation_last':str(g.loc[g.split.eq('validation'),'decision_time'].max()),
            'test_first':str(g.loc[g.split.eq('test'),'decision_time'].min()),'available_anchors':int(g.available.sum()),
            'extracted_anchors':len(pm),'short_support_mean':float(pm.pm_short_valid_fraction.mean())})
    f=pd.concat(frames,ignore_index=True);x=pd.concat(xs,ignore_index=True);xi=pd.concat(xis,ignore_index=True)
    save(dest/'normalizers.json',states);save(dest/'audit.json',audit)
    mask=f.available.to_numpy(bool);inner=f.inner_holdout.to_numpy();val=f.split.eq('validation').to_numpy();test=f.split.eq('test').to_numpy()
    models={};tuning=[];selected=[];inners=[];vals=[]
    with threadpool_limits(2):
      for arm,cols in ARMS.items():
        train=f.inner_train.to_numpy()&mask;candidates=[]
        for name in config['candidates']:
            model,prior=fit_model(xi.loc[train,cols],f.loc[train,'label_low'].to_numpy(int),training_weights(f[train],'point'),name,config['seed'])
            p=np.full(len(f),np.nan);support=inner&mask;p[support]=predict(model,prior,xi.loc[support,cols]);aps=[]
            for s in events:
                take=inner&f.subject.eq(s).to_numpy();ap=point_metrics(f.loc[take,'label_low'],p[take])['ap']
                if ap is not None:aps.append(ap)
            row={'arm':arm,'candidate':name,'inner_macro_ap':float(np.mean(aps)) if aps else None,'ap_subjects':len(aps)}
            tuning.append(row);candidates.append(row)
            out=f.loc[inner,['subject','decision_time','label_low']].copy();out['score']=p[inner];out['arm']=arm;out['candidate']=name;inners.append(out)
        choice=max(candidates,key=lambda r:r['inner_macro_ap'] if r['inner_macro_ap'] is not None else -1);selected.append(choice)
        train=f.split.eq('train').to_numpy()&mask
        model,prior=fit_model(x.loc[train,cols],f.loc[train,'label_low'].to_numpy(int),training_weights(f[train],'point'),choice['candidate'],config['seed']);models[arm]=(model,prior)
        p=np.full(len(f),np.nan);support=val&mask;p[support]=predict(model,prior,x.loc[support,cols])
        out=f.loc[val,['subject','decision_time','label_low']].copy();out['score']=p[val];out['arm']=arm;vals.append(out)
        print('Selected',choice,flush=True)
    save(dest/'tuning.json',tuning);save(dest/'selected_parameters.json',selected)
    pd.concat(inners,ignore_index=True).to_parquet(dest/'inner_predictions.parquet',index=False)
    validation=pd.concat(vals,ignore_index=True);validation.to_parquet(dest/'validation_predictions.parquet',index=False)
    candidates=[];selections=[]
    for arm,block in validation.groupby('arm',sort=False):
        subjects={s:g for s,g in block.groupby('subject')};trials=[]
        for pi,policy in enumerate(config['policies']):
            p=np.concatenate([smooth_scores(times(g),g.score.to_numpy(),policy) for g in subjects.values()]);p=p[np.isfinite(p)]
            thresholds=np.unique(np.r_[np.quantile(p,np.linspace(0,1,101)) if len(p) else [],1.001])
            for th in thresholds:
                r=aggregate([event_metrics(times(g),g.score.to_numpy(),events[s],float(th),policy) for s,g in subjects.items()])
                row={'arm':arm,'policy':policy,'policy_index':pi,'threshold':float(th),'validation':r};trials.append(row);candidates.append(row)
        for budget in config['budgets']:
            feasible=[r for r in trials if r['validation']['false_alerts_per_person_day']<=budget]
            best=max(feasible,key=lambda r:(r['validation']['event_recall'] or 0,-r['validation']['false_alerts_per_person_day'],-r['policy_index'],r['threshold']))
            selections.append({**best,'budget':budget})
    save(dest/'decision_candidates.json',candidates);save(dest/'selections_frozen_before_test.json',selections)
    print('All selections frozen; test scoring starts',flush=True)
    predictions=[];metrics=[]
    with threadpool_limits(2):
      for arm,cols in ARMS.items():
        model,prior=models[arm];p=np.full(len(f),np.nan);support=test&mask;p[support]=predict(model,prior,x.loc[support,cols])
        for choice in [c for c in selections if c['arm']==arm]:
          for s in events:
            take=test&f.subject.eq(s).to_numpy();out=f.loc[take,['subject','decision_time','label_low']].copy();out['score']=p[take]
            key={k:choice[k] for k in ['arm','budget','policy','threshold']};key['subject']=s
            for k,v in key.items():out[k]=v
            predictions.append(out);r=event_metrics(times(out),p[take],events[s],choice['threshold'],choice['policy'])
            r.update(point_metrics(out.label_low,smooth_scores(times(out),p[take],choice['policy'])));metrics.append({**r,**key})
    pd.concat(predictions,ignore_index=True).to_parquet(dest/'predictions.parquet',index=False);save(dest/'metrics_by_subject.json',metrics)
    paths=['configs/ppg_morphology_v5.json','scripts/run_ppg_morphology.py','scripts/extract_ppg_morphology.py','src/t1d_lab/ppg_morphology.py',
           'src/t1d_lab/late_fusion.py','src/t1d_lab/mechanism.py',config['source_features']]+files
    save(dest/'completed.json',{'id':config['id'],'metric_groups':len(metrics),'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
         'selection_sha256':hashlib.sha256((dest/'selections_frozen_before_test.json').read_bytes()).hexdigest(),
         'prediction_sha256':hashlib.sha256((dest/'predictions.parquet').read_bytes()).hexdigest()})
    print('Completed',len(metrics),'groups; verification pending',flush=True)

if __name__=='__main__':main()
