"""Read each source BVP session once; resume only verified complete subject files."""
import argparse,hashlib,json,sys
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.ppg_morphology import window_features,sample_bounds


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--subjects',nargs='+');args=parser.parse_args()
    cfg=json.loads((ROOT/'configs/ppg_morphology_v5.json').read_text());dest=ROOT/cfg['extraction_directory'];dest.mkdir(parents=True,exist_ok=True)
    fingerprint=hashlib.sha256((ROOT/'src/t1d_lab/ppg_morphology.py').read_bytes()).hexdigest()
    raw=pd.read_parquet(ROOT/cfg['source_features']);clock=json.loads((ROOT/'docs/acceptance/S1b.json').read_text())
    offsets={r['subject']:r['clock_shift_hours'] for r in clock['audit'] if r['status']=='extracted'}
    for subject,g in raw.groupby('subject',sort=True):
        if args.subjects and subject not in args.subjects:continue
        path=dest/f'{subject}.parquet';manifest=dest/f'{subject}.json'
        if path.exists() and manifest.exists():
            m=json.loads(manifest.read_text());assert m['extractor_sha256']==fingerprint and m['features_sha256']==hashlib.sha256(path.read_bytes()).hexdigest();print(subject,'verified cached',flush=True);continue
        anchors=pd.DatetimeIndex(g.loc[g.available,'decision_time']);rows=[];used=set();session_count=0
        with ZipFile(ROOT/'data/raw/physiocgm'/f'{subject}_raw.zip') as z:
            for name in sorted(n for n in z.namelist() if n.endswith('/BVP.csv')):
                with z.open(name) as stream:
                    epoch=float(stream.readline().decode().split(',')[0])+offsets[subject]*3600;rate=float(stream.readline().decode().split(',')[0]);assert rate==64
                    try:values=pd.read_csv(stream,header=None,usecols=[0]).iloc[:,0].to_numpy(float)
                    except pd.errors.EmptyDataError:continue
                eligible=anchors[(anchors>=pd.Timestamp(epoch+300,unit='s'))&(anchors<pd.Timestamp(epoch+len(values)/rate,unit='s'))]
                for time in eligible:
                    if time in used:continue
                    a,b=sample_bounds(epoch,time.value/1e9,rate)
                    if a<0 or b>len(values):continue
                    r=window_features(values[a:b],rate);r.update(subject=subject,decision_time=time,pm_input_end=time);rows.append(r);used.add(time)
                session_count+=1
        f=pd.DataFrame(rows).sort_values('decision_time');f.to_parquet(path,index=False)
        m={'subject':subject,'source_sessions':session_count,'same_wrist_anchors':len(anchors),'extracted_anchors':len(f),'extractor_sha256':fingerprint,
           'features_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_shift_hours':offsets[subject],
           'short_pulse_support_mean':float(f.pm_short_valid_fraction.mean()),'scope':'No glucose-dependent exclusions; first complete lexical session in overlaps; pulse descriptors not expert-validated HRV'}
        manifest.write_text(json.dumps(m,indent=2));print(json.dumps(m),flush=True)

if __name__=='__main__':main()
