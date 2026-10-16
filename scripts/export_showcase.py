"""Publish aggregate evidence; optional participant examples stay git-ignored."""
import json
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.brist1d import read_subject


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def main():
    dest=ROOT/'showcase/public/demo';dest.mkdir(parents=True,exist_ok=True)
    acceptance={p.stem:load(p) for p in sorted((ROOT/'docs/acceptance').glob('S*.json'))}
    fingerprint=hashlib.sha256((ROOT/'configs/protocol.yaml').read_text(encoding='utf-8').encode())
    for stage in ['S2a','S2b','S3','S4']:
        p=ROOT/'docs/acceptance'/f'{stage}.json'
        if p.exists():fingerprint.update(json.dumps(load(p),sort_keys=True,separators=(',',':')).encode())
    run_id='t1d-'+fingerprint.hexdigest()[:12]
    regression=load(ROOT/'outputs/module1_forecasting/verified_summary.json')
    incident=load(ROOT/'outputs/module1_incident/verified_summary.json')
    detection=load(ROOT/'outputs/module2_detection/verified_summary.json')
    cohort=load(ROOT/'outputs/audit/brist1d_cohort.json')
    metrics=pd.read_csv(ROOT/'outputs/module1_forecasting/verified_metrics_by_subject.csv') if regression else pd.DataFrame()
    subject_comparison=[]
    if len(metrics):
        p=metrics[metrics.protocol.eq('loso')].pivot(index='subject',columns='model',values='mae')
        for i,(_,r) in enumerate(p.iterrows()):
            subject_comparison.append({'label':f'#{i+1:02d}','cgm':r['cgm'],'context':r['context'],'fusion':r['fusion'],'baseline':r['selected_simple']})
    data={'project':'T1D Wearable Lab','run_id':run_id,'protocol':'1.2-implementation-1','repository':'https://github.com/PYxuejiang/t1d-wearable-lab',
          'audit':{'subjects':cohort['subjects_audited'] if cohort else 0,'rows':sum(x['rows'] for x in cohort['reports']) if cohort else 0,
                   'signal_archives':len(list((ROOT/'data/raw/physiocgm').glob('*_raw.zip'))),
                   'signal_subjects_extracted':len(list((ROOT/'data/processed').glob('*signal_features.parquet')))},
          'regression':regression,'incident':incident,'detection':detection,'acceptance':acceptance,'subject_comparison':subject_comparison,
          'limitations':['回顾性公开小队列研究，结果不等于临床有效性。','事件预警与当前检测分别评价；负结果完整保留。','原始数据和个体预测未上传，本地示例需自行生成。']}
    (dest/'project_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if regression:
        predictions=pd.read_parquet(ROOT/'outputs/module1_forecasting/verified_predictions.parquet')
        example=predictions[predictions.subject.eq('P01')&predictions.protocol.eq('temporal')&predictions.model.isin(['context','fusion'])]
        low=example[example.target.lt(3.9)]
        center=low.decision_time.min() if len(low) else example.decision_time.min()
        start,end=center-pd.Timedelta(minutes=90),center+pd.Timedelta(minutes=90)
        example=example[example.decision_time.between(start,end)]
        ch,_=read_subject(ROOT/'data/raw/brist1d/P01.csv')
        glucose=ch['bg'].loc[start:end+pd.Timedelta(minutes=30)]
        origin=min(start,glucose.index.min())
        def minute(t):return float((t-origin).total_seconds()/60)
        observed=[[minute(t),float(v)] for t,v in glucose.items()]
        wide=example.pivot(index=['decision_time','target_time'],columns='model',values='prediction').reset_index()
        frames=[{'decision':minute(r.decision_time),'target':minute(r.target_time),'context':float(r.context),'fusion':float(r.fusion)} for r in wide.itertuples()]
        (dest/'timeline_example.json').write_text(json.dumps({'scope':'本地单个示例，仅用于历史回放；自动选择首个低参考值附近，不是总体性能证据。','observed':observed,'frames':frames},ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print('Exported aggregate evidence; individual timeline is ignored by git.',flush=True)


if __name__=='__main__':main()
