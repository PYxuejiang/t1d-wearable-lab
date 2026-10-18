"""Audit original reference labels and fixed author-processed probes, without ML."""
import hashlib
import io
import json
import pickle
import sys
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.physiocgm import read_cgm


class RestrictedArrayReader(pickle.Unpickler):
    def find_class(self,module,name):
        if module in ('numpy.core.multiarray','numpy._core.multiarray') and name in ('scalar','_reconstruct'):
            return getattr(np.core.multiarray,name)
        if module=='numpy' and name in ('dtype','ndarray'):return getattr(np,name)
        if module=='pandas._libs.tslibs.timestamps' and name=='_unpickle_timestamp':
            from pandas._libs.tslibs.timestamps import _unpickle_timestamp
            return _unpickle_timestamp
        raise pickle.UnpicklingError('Disallowed global: '+module+'.'+name)


def match_e4(z,probe):
    # Match a sequence of values, not glucose correlation or a chosen clock offset.
    for kind in ['EDA','BVP','HR','TEMP']:
        values=probe['e4'][kind].get(kind);times=probe['e4'][kind].get('Time')
        if values is None or len(values)<16:continue
        needle=np.asarray(values[:16],dtype=float)
        if not np.isfinite(needle).all() or np.std(needle)<1e-8:continue
        matches=[]
        for name in sorted(n for n in z.namelist() if n.endswith('/'+kind+'.csv')):
            with z.open(name) as stream:
                epoch=float(stream.readline().decode().split(',')[0]);rate=float(stream.readline().decode().split(',')[0])
                try:arr=pd.read_csv(stream,header=None,usecols=[0]).iloc[:,0].to_numpy(float)
                except pd.errors.EmptyDataError:continue
            candidates=np.flatnonzero(np.isclose(arr,needle[0],atol=1e-9,rtol=0))
            for i in candidates[candidates<=len(arr)-len(needle)]:
                if np.allclose(arr[i:i+16],needle,atol=1e-9,rtol=0):
                    stamp=pd.Timestamp(epoch+i/rate,unit='s')
                    delta=(pd.Timestamp(times[0])-stamp).total_seconds()
                    matches.append({'offset_seconds':delta,'source_member_sha256':hashlib.sha256(name.encode()).hexdigest()})
        return {'channel':kind,'sequence_length':16,'matches':matches,'unique_value_match':len(matches)==1}
    return {'channel':None,'matches':[],'unique_value_match':False,'reason':'No nonconstant 16-sample sequence in first fixed probe'}


def main():
    dest=ROOT/'outputs/source_audit_v1';rows=[]
    source=pd.read_parquet(ROOT/'outputs/improvement_v2/features.parquet')
    for archive in sorted((ROOT/'data/raw/physiocgm').glob('*_raw.zip')):
        subject=archive.name.removesuffix('_raw.zip');meta=json.loads((dest/f'{subject}_probe.json').read_text())
        payload=(dest/f'{subject}_probe.pkl').read_bytes()
        assert hashlib.sha256(payload).hexdigest()==meta['member_sha256']
        probe=RestrictedArrayReader(io.BytesIO(payload)).load()
        with ZipFile(archive) as z:
            name=next(n for n in z.namelist() if n.lower().endswith('cgm.csv'))
            d=pd.read_csv(z.open(name),low_memory=False);d=d[d['Event Type'].eq('EGV')].copy()
            timecol=next(c for c in d if c.startswith('Timestamp'));t=pd.to_datetime(d[timecol],format='mixed')
            text=d['Glucose Value (mg/dL)'].astype(str).str.strip();numeric=pd.to_numeric(text,errors='coerce')
            proxy=numeric.copy();proxy.loc[text.str.lower().eq('low')]=39;proxy.loc[text.str.lower().eq('high')]=401
            check=pd.DataFrame({'time':t,'proxy':proxy});conflicts=int(check.groupby('time').proxy.nunique().gt(1).sum())
            original=d[d.Index.eq(probe['Index'])];assert len(original)==1
            originaltime=pd.Timestamp(original[timecol].iloc[0]);pg=float(probe['glucose'])
            native=str(original['Glucose Value (mg/dL)'].iloc[0]).strip().lower()
            expected=40. if native=='low' else 400. if native=='high' else float(native)
            assert pg==expected and originaltime==pd.Timestamp(probe['Timestamp'])
            chesttime=pd.DatetimeIndex(probe['zephyr']['ECG']['Time'])
            lag=(pd.Timestamp(probe['Timestamp'])-chesttime).total_seconds()
            e4=match_e4(z,probe)
            # Source summary values and timestamps are cross-checked without label shifts.
            ss=probe['zephyr']['Summary'];st=pd.DatetimeIndex(ss['Time']);verified=False
            if len(st):
                for n in sorted(n for n in z.namelist() if n.endswith('_SummaryEnhanced.csv')):
                    raw=pd.read_csv(z.open(n),usecols=['Time','HR','BR','HRConfidence','ECGNoise'])
                    rt=pd.to_datetime(raw.Time,format='%d/%m/%Y %H:%M:%S.%f')
                    hit=raw.loc[rt.eq(st[0])]
                    if len(hit):
                        verified=all(np.isclose(float(hit[c].iloc[0]),float(ss[c][0]),equal_nan=True) for c in ['HR','BR','HRConfidence','ECGNoise']);break
        clean=read_cgm(archive);f=source[source.subject.eq(subject)]
        mismatch=0
        if len(f):
            reference=clean.reindex(pd.DatetimeIndex(f.decision_time)).label_proxy_mg_dl.to_numpy()
            mismatch=int(np.sum(reference!=f.label_proxy_mg_dl.to_numpy()))
            assert mismatch==0 and np.array_equal(reference<70,f.label_low.to_numpy())
        row={'subject':subject,'egv_rows':len(d),'timestamp_tz_explicit':t.dt.tz is not None,
             'exact_duplicate_rows':int(check.duplicated().sum()),'conflicting_timestamps':conflicts,
             'unknown_glucose_encoding':int(proxy.isna().sum()),'censored_low':int(text.str.lower().eq('low').sum()),
             'censored_high':int(text.str.lower().eq('high').sum()),'feature_anchors_checked':len(f),'feature_label_mismatches':mismatch,
             'processed_index_timestamp_glucose_match':True,'processed_chest_samples':len(chesttime),
             'processed_chest_lag_seconds_min':float(min(lag)),'processed_chest_lag_seconds_max':float(max(lag)),
             'processed_chest_all_past_within330s':bool(np.all((lag>=0)&(lag<=330))),
             'first_processed_summary_matches_raw':verified if len(st) else None,'e4_value_sequence':e4,
             'probe_integrity':meta}
        rows.append(row);print(subject,'labels checked',len(f),'E4 offsets',[x['offset_seconds'] for x in e4['matches']],flush=True)
    code={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.glob('author_*') if p.is_file()}
    result={'id':'SOURCE_TIME1','date':'2026-10-18','status':'provenance_checked_physical_clock_unresolved',
            'author_commit':'6940f1d587f8f68b131cf129d5a9f65237f61fcc','source_code_sha256':code,'subjects':rows,
            'feature_anchors_checked':sum(r['feature_anchors_checked'] for r in rows),
            'feature_label_mismatches':sum(r['feature_label_mismatches'] for r in rows),
            'limitations':['One outcome-independent processed probe per subject, not full archive validation.',
                          'Naive CGM and chest clocks have no independent physical offset calibration.',
                          'Author E4 preprocessing uses host localtime; source-code consistency is not clock ground truth.',
                          'No clock adjustment, new subject inclusion or label change performed.']}
    (dest/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    (ROOT/'docs/acceptance/SOURCE_TIME1.json').write_text(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
