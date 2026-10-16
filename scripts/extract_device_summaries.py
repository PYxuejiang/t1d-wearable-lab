"""Add causal device-provided HR/respiration summaries; no glucose features."""
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.physiocgm import e4_series

CHEST=['HR','BR','Posture','Activity','PeakAccel','BRAmplitude','ECGAmplitude','ECGNoise','HRConfidence','HRV','DeviceTemp']


def prior_summary(series,anchors,minutes=5):
    s=series.sort_index();a=pd.DatetimeIndex(anchors).as_unit('ns').asi8;x=s.index.as_unit('ns').asi8
    r=np.searchsorted(x,a,side='right');l=np.searchsorted(x,a-pd.Timedelta(minutes=minutes).value,side='right')
    values=s.to_numpy(dtype=float);out=[]
    for left,right in zip(l,r):
        finite=values[left:right];finite=finite[np.isfinite(finite)]
        out.append((float(np.median(finite)) if len(finite) else np.nan,float(np.std(finite)) if len(finite) else np.nan,len(finite)))
    return np.asarray(out)


def main():
    dest=ROOT/'data/processed'
    provenance=[]
    for path in sorted(dest.glob('*signal_features.parquet')):
        subject=path.name.removesuffix('_signal_features.parquet');target=dest/f'{subject}_device_summaries.parquet'
        if target.exists():print('Already extracted summaries',subject,flush=True);continue
        features=pd.read_parquet(path);anchors=pd.DatetimeIndex(features.decision_time);offset=json.loads((ROOT/'outputs/audit'/f'physiocgm_{subject}.json').read_text())['best_clock_candidate']['shift_hours']
        with ZipFile(ROOT/'data/raw/physiocgm'/f'{subject}_raw.zip') as z:
            parts=[]
            for name in sorted(n for n in z.namelist() if n.endswith('_SummaryEnhanced.csv')):
                f=pd.read_csv(z.open(name),usecols=['Time']+CHEST)
                f['time']=pd.to_datetime(f.Time,format='%d/%m/%Y %H:%M:%S.%f');f=f.set_index('time')[CHEST]
                f.loc[f.HRConfidence.lt(80),['HR','HRV']]=np.nan
                parts.append(f)
            chest=pd.concat(parts).groupby(level=0).median().sort_index()
            wrist=pd.concat([e4_series(z,n)[0].iloc[:,0] for n in z.namelist() if n.endswith('/HR.csv')]).groupby(level=0).median().sort_index()
            # Minute bins from the clock audit contain data after their left edge;
            # put each value at its bin END before any causal feature construction.
            wrist.index=wrist.index+pd.Timedelta(hours=offset)+pd.Timedelta(minutes=1)
        frame=pd.DataFrame({'decision_time':anchors,'subject':subject})
        for key in CHEST:
            values=prior_summary(chest[key],anchors)
            for i,suffix in enumerate(['median','std','samples']):frame[f'chest_{key}_{suffix}']=values[:,i]
        values=prior_summary(wrist.where(wrist.gt(0)),anchors)
        for i,suffix in enumerate(['median','std','samples']):frame[f'wrist_HR_{suffix}']=values[:,i]
        frame.to_parquet(target,index=False)
        provenance.append({'subject':subject,'source':'Zephyr SummaryEnhanced (1-second source), E4 HR (minute bin end)','reference_clock':'same declared v1 clock, no outcome-dependent adjustment','rows':len(frame),'features':len(frame.columns)-2})
        print('Extracted device summaries',subject,len(frame),flush=True)
    (ROOT/'outputs/audit/device_summaries.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')


if __name__=='__main__':main()
