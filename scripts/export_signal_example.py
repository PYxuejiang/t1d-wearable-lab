"""Local-only, real simultaneous PPG/ECG snippet; no synthetic waveform."""
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def main():
    features=pd.read_parquet(ROOT/'data/processed/c1s01_signal_features.parquet')
    rows=features[features.ppg_completeness.ge(.9)&features.ecg_completeness.ge(.9)&features.ppg_valid.eq(1)&features.ecg_valid.eq(1)]
    anchor=pd.Timestamp(rows.decision_time.iloc[0]);start=anchor-pd.Timedelta(seconds=10)
    audit=json.loads((ROOT/'outputs/audit/physiocgm_c1s01.json').read_text())
    shift=audit['best_clock_candidate']['shift_hours'];result={};members={}
    with ZipFile(ROOT/'data/raw/physiocgm/c1s01_raw.zip') as z:
        for name in sorted(n for n in z.namelist() if n.endswith('/BVP.csv')):
            with z.open(name) as stream:
                epoch=float(stream.readline().decode().split(',')[0]);rate=float(stream.readline().decode().split(',')[0])
                source_start=pd.Timestamp(epoch,unit='s')+pd.Timedelta(hours=shift)
                if source_start>start:continue
                try:values=pd.read_csv(stream,header=None).iloc[:,0].to_numpy(dtype=float)
                except pd.errors.EmptyDataError:continue
            left=int(np.ceil((start-source_start).total_seconds()*rate));right=left+int(rate*10)
            if 0<=left and right<=len(values):
                result['ppg']=np.column_stack([np.arange(right-left)/rate,values[left:right]]);members['ppg']=name;break
        for name in sorted(n for n in z.namelist() if n.endswith('_ECG.csv')):
            for chunk in pd.read_csv(z.open(name),usecols=['Time','EcgWaveform'],chunksize=250000):
                first=pd.to_datetime(chunk.Time.iloc[0],format='%d/%m/%Y %H:%M:%S.%f')
                last=first+pd.Timedelta(seconds=(len(chunk)-1)/250)
                if first>anchor:break
                if last<start:continue
                t=first+pd.to_timedelta(np.arange(len(chunk))/250,unit='s');mask=(t>=start)&(t<=anchor)
                if mask.any():
                    piece=np.column_stack([(t[mask]-start).total_seconds(),chunk.EcgWaveform.to_numpy(dtype=float)[mask]])
                    result['ecg']=np.concatenate([result.get('ecg',np.empty((0,2))),piece]);members['ecg']=name
                if last>=anchor:break
            if 'ecg' in result and len(result['ecg'])>=2400:break
    if any(k not in result for k in ['ppg','ecg']):raise RuntimeError('No traceable simultaneous snippet')
    for kind in ['ppg','ecg']:
        values=result[kind];values[:,1]=(values[:,1]-values[:,1].mean())/max(values[:,1].std(),1e-9)
        result[kind]=values.tolist()
    result.update(scope='本地真实 10 秒同步片段；按片段显示归一化，非设备精度或心搏标注证据。',source_members=members,source='PhysioCGM c1s01',clock_assumption='E4 shift checked with training HR; CGM/chest wall clock assumed.')
    dest=ROOT/'showcase/public/demo/signals_excerpt.json';dest.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print('Exported local-only real signal excerpt',len(result['ppg']),len(result['ecg']))


if __name__=='__main__':main()
