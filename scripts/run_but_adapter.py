"""Frozen four-record adapter check. Private waveform cache; public aggregates."""
import hashlib,json,sys,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests,numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'outputs/adapter_tools'))
from t1d_lab.but_ppg import read_but_raw

IDS=['100001','111004','112001','149108']
def main():
    import wfdb
    assert wfdb.__version__=='4.3.1'
    out=ROOT/'outputs/but_adapter_v1';out.mkdir(exist_ok=True)
    if (out/'completed.json').exists():raise RuntimeError('Completed; preserve previous run')
    meta=ROOT/'outputs/but_source_v1'
    hashes={line.split(maxsplit=1)[1].strip():line.split()[0] for line in (meta/'SHA256SUMS.txt').read_text().splitlines()}
    def get(identifier):
        d=out/identifier;d.mkdir(exist_ok=True)
        for suffix in ['.hea','.dat']:
            name=f'{identifier}/{identifier}_PPG{suffix}';p=out/name
            if not p.exists():
                if suffix=='.hea':shutil.copyfile(meta/name,p)
                else:
                    r=requests.get('https://physionet-open.s3.amazonaws.com/butppg/2.0.0/'+name,timeout=(15,45))
                    r.raise_for_status();p.write_bytes(r.content)
            assert hashlib.sha256(p.read_bytes()).hexdigest()==hashes[name]
        return identifier
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(get,IDS))
    results=[]
    for identifier in IDS:
        stem=out/identifier/(identifier+'_PPG');p=stem.with_suffix('.hea')
        own=read_but_raw(p)
        digital=wfdb.rdrecord(str(stem),physical=False)
        physical=wfdb.rdrecord(str(stem),physical=True)
        assert own['fs']==digital.fs==physical.fs==30
        # WFDB 4.3.1 truncates dotted a.u. to a; retain both metadata values.
        # This discrepancy is reported, never repaired by changing source headers.
        unit_metadata_equal=own['units']==digital.units
        assert np.array_equal(own['digital'],digital.d_signal)
        assert np.array_equal(np.isnan(own['physical']),np.isnan(physical.p_signal))
        error=float(np.nanmax(np.abs(own['physical']-physical.p_signal)))
        assert error<=1e-10
        shape=list(own['digital'].shape)
        assert shape==([1,300] if identifier in IDS[:2] else [300,3])
        results.append({'layout':own['layout'],'shape':shape,'digital_exact':True,'physical_max_abs_error':error,
                        'missing_digital_values':int((own['digital']==-32768).sum()),
                        'positive_rail_values':int((own['digital']==32767).sum()),
                        'finite_physical_values':int(np.isfinite(own['physical']).sum()),'values':int(own['physical'].size),
                        'source_units':sorted(set(own['units'])),
                        'wfdb_units':sorted(set(digital.units)),
                        'unit_metadata_equal':unit_metadata_equal})
    public={'stage':'BUT_ADAPTER1','protocol_commit':'96e0162','scope':'Four fixed PPG records; no feature or model scoring',
            'verification':{'status':'passed_raw_layout_decode_only','official_file_hashes_matched':8,'independent_reader':'wfdb 4.3.1',
                            'numpy':np.__version__,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            'records_checked':4,'records_expected':4,'source_sample_selection':'Initial and extension releases: first and last ID, fixed before waveform download',
            'results':results,'rgb_records_with_300_time_samples':2,'legacy_records_with_one_time_sample':2,
            'legacy_reshape_performed':False,'all_corpus_import_validated':False,'clinical_effect_changed':False,
            'next_gate':'Resolve legacy time-axis evidence; full-corpus adapter coverage; freeze subject grouping before model evaluation'}
    (ROOT/'docs/acceptance/BUT_ADAPTER1.json').write_text(json.dumps(public,indent=2))
    (out/'completed.json').write_text(json.dumps({'status':'complete','public_sha256':hashlib.sha256((ROOT/'docs/acceptance/BUT_ADAPTER1.json').read_bytes()).hexdigest()}))
    print(json.dumps(public,indent=2))
if __name__=='__main__':main()
