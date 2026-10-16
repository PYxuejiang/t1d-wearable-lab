"""Fixed-prediction uncertainty, calibration and acquisition robustness."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from verify_module2 import evaluate,event_runs
from t1d_lab.risk import point_metrics
from t1d_lab.physiocgm import read_cgm


def interval(rows,key):
    values=np.array([r[key] for r in rows if r.get(key) is not None and np.isfinite(r[key])])
    if not len(values):return {'subjects':0,'mean':None,'95_interval':None}
    rng=np.random.default_rng(20261016)
    means=values[rng.integers(0,len(values),(2000,len(values)))].mean(axis=1)
    return {'subjects':len(values),'mean':float(values.mean()),'95_interval':np.quantile(means,[.025,.975]).tolist()}


def reliability(frame,label):
    f=frame[np.isfinite(frame.score)&frame[label].notna()]
    bins=[]
    for a,b in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
        g=f[f.score.ge(a)&(f.score.lt(b) if b<1 else f.score.le(b))]
        bins.append({'lower':float(a),'upper':float(b),'n':len(g),'mean_score':float(g.score.mean()) if len(g) else None,'observed_fraction':float(g[label].mean()) if len(g) else None})
    return {'point_metrics':point_metrics(f[label],f.score),'bins':bins,'scope':'Pooled eligible scored test anchors; descriptive, temporally dependent; no test recalibration.'}


def main():
    output=ROOT/'outputs/robustness';output.mkdir(parents=True,exist_ok=True)
    calibration={};uncertainty={}
    for task,folder,label,metricfile in [('incident','module1_incident','incident_y','metrics_by_subject.json'),('detection','module2_detection','label_low','verified_metrics.json')]:
        directory=ROOT/'outputs'/folder
        rows=json.loads((directory/metricfile).read_text())
        if task=='detection':rows=[r for r in rows if r['view']=='end_to_end']
        uncertainty[task]={}
        for protocol in ['temporal','loso']:
            uncertainty[task][protocol]={m:{k:interval([r for r in rows if r['protocol']==protocol and r['model']==m],k) for k in ['event_recall','coverage','ap','brier']} for m in sorted({r['model'] for r in rows})}
        predictions=pd.read_parquet(directory/'predictions.parquet')
        calibration[task]={f'{p}/{m}':reliability(g,label) for (p,m),g in predictions.groupby(['protocol','model'])}
    p=pd.read_parquet(ROOT/'outputs/module2_detection/predictions.parquet')
    sources={};features={}
    for s in p.subject.unique():
        features[s]=pd.read_parquet(ROOT/'data/processed'/f'{s}_signal_features.parquet').set_index('decision_time')
        reference=read_cgm(ROOT/'data/raw/physiocgm'/f'{s}_raw.zip').label_proxy_mg_dl.reindex(features[s].index)
        t=features[s].index;bounds=[t[0]+(t[-1]-t[0])*r for r in [.6,.8]]
        sources[s]=[e for e in event_runs(reference) if not any(e[0]<b<e[1] for b in bounds)]
    kinds={'ppg':['ppg'],'wrist':['ppg','acc'],'wrist_eda_temp':['ppg','acc','eda','temp'],'ecg':['ecg'],'all':['ppg','acc','eda','temp','ecg']}
    robustness=[];strata=[];agreement=[]
    for (protocol,subject,model),g in p.groupby(['protocol','subject','model']):
        extra=features[subject].reindex(pd.DatetimeIndex(g.decision_time))
        for quality in [.9,.95,1.]:
            for dropout in [0.,.1,.3]:
                frame=g.copy();valid=np.ones(len(g),dtype=bool)
                for kind in kinds[model]:valid &= extra[kind+'_completeness'].fillna(0).to_numpy()>=quality-1e-9
                # Same per-subject/timestamp dropout mask for every sensor configuration.
                hashed=pd.util.hash_pandas_object(frame[['subject','decision_time']],index=False).to_numpy(dtype=np.uint64)
                valid &= (hashed % 10000)/10000 >= dropout
                frame.loc[~valid,'score']=np.nan
                r=evaluate(frame,sources[subject]);r.update(protocol=protocol,subject=subject,model=model,quality=quality,dropout=dropout,
                    event_recall=r['matched_events']/r['reference_events'] if r['reference_events'] else None)
                robustness.append(r)
        for group,mask in [('wall_clock_00_06',g.decision_time.dt.hour.lt(6)),('wall_clock_06_24',g.decision_time.dt.hour.ge(6))]:
            r=point_metrics(g.loc[mask,'label_low'],g.loc[mask,'score']);r.update(protocol=protocol,subject=subject,model=model,stratum=group);strata.append(r)
    for subject,f in features.items():
        good=f.ppg_valid.eq(1)&f.ecg_valid.eq(1)&f.ppg_completeness.ge(.9)&f.ecg_completeness.ge(.9)
        pair=f.loc[good,['ppg_rate','ecg_rate']].dropna()
        difference=(pair.ppg_rate-pair.ecg_rate)
        agreement.append({'subject':subject,'paired_windows':len(pair),'mae_bpm':float(difference.abs().mean()) if len(pair) else None,'bias_bpm':float(difference.mean()) if len(pair) else None})
    clocks=json.loads((ROOT/'outputs/module2_detection/clock_sensitivity.json').read_text())
    record={'stage':'S4','engineering_status':'passed','evaluation_status':'fixed_test_predictions_uncertainty_and_sensitivity_reported',
        'effect_status':'inconclusive','analysis_scope':'exploratory_stress_tests','bootstrap_repetitions':2000,'bootstrap_unit':'subject','uncertainty':uncertainty,
        'calibration':calibration,'robustness_summary':[], 'clock_sensitivity_summary':[],
        'pulse_agreement':agreement,'limitations':['No test-driven parameter selection; these analyses do not upgrade failed primary targets.','Pooled reliability bins are descriptive and mix dependent observations.','PPG/ECG rates both use heuristic peak detection; ECG is not manually adjudicated ground truth.','No external independent cohort or prospective intervention validation.','Wall-clock strata are not validated sleep stages.','Quality thresholds 0.9/0.95/1 and deterministic score dropout 0/10/30% are post-primary engineering stress tests, not a second validation dataset.']}
    for protocol in ['temporal','loso']:
      for model in kinds:
       for quality in [.9,.95,1.]:
        for dropout in [0.,.1,.3]:
            rows=[r for r in robustness if r['protocol']==protocol and r['model']==model and r['quality']==quality and r['dropout']==dropout]
            record['robustness_summary'].append({'protocol':protocol,'model':model,'quality':quality,'dropout':dropout,
                'recall':interval(rows,'event_recall'),'coverage':interval(rows,'coverage'),
                'false_alerts_per_person_day':sum(r['unmatched_alarms'] for r in rows)/(sum(r['observation_hours'] for r in rows)/24) if rows else None})
       for shift in [-5,0,5]:
           rows=[r for r in clocks if r['protocol']==protocol and r['model']==model and r['label_shift_minutes']==shift]
           record['clock_sensitivity_summary'].append({'protocol':protocol,'model':model,'label_shift_minutes':shift,'recall':interval(rows,'event_recall')})
    for filename,value in [('robustness_by_subject.json',robustness),('clock_strata.json',strata),('calibration.json',calibration)]:
        (output/filename).write_text(json.dumps(value,indent=2),encoding='utf-8')
    (ROOT/'docs/acceptance/S4.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('S4 written: subject bootstrap, reliability, quality/coverage, dropout and clock sensitivity')


if __name__=='__main__':main()
