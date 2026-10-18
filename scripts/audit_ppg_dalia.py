"""Download fixed published MAT files and audit schema, without detector scoring."""
import argparse, hashlib, json
from pathlib import Path
import requests
import numpy as np
from scipy.io import loadmat
ROOT = Path(__file__).resolve().parents[1]

def digest(path, algorithm):
    h=hashlib.new(algorithm)
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');args=parser.parse_args()
    cfg=json.loads((ROOT/'configs/ppg_dalia_audit_v1.json').read_text());dest=ROOT/cfg['directory'];dest.mkdir(parents=True,exist_ok=True)
    report={'protocol_id':cfg['protocol_id'],'status':'schema_audit_only','scores_computed':False,'files':[],'reference_caveats':cfg['reference_caveats']}
    for entry in cfg['files']:
        path=dest/entry['file']
        if not path.exists():
            if not args.download:raise FileNotFoundError(path)
            temporary=path.with_suffix('.part')
            with requests.get(cfg['record']+'/files/'+entry['file']+'?download=1',stream=True,timeout=(30,90)) as response:
                response.raise_for_status()
                with temporary.open('wb') as out:
                    for chunk in response.iter_content(1024*1024):
                        if chunk:out.write(chunk)
                        if out.tell()>entry['bytes']:raise ValueError('Response exceeds published size')
            if temporary.stat().st_size!=entry['bytes'] or digest(temporary,'md5')!=entry['md5']:raise ValueError('Published checksum mismatch')
            temporary.replace(path)
        assert path.stat().st_size==entry['bytes'] and digest(path,'md5')==entry['md5']
        data=loadmat(path,simplify_cells=True)['data']
        rows=list(data) if isinstance(data,(list,np.ndarray)) else [data]
        summaries=[]
        for row in rows:
            ppg=np.asarray(row['ppg']['v']).reshape(-1);ecg=np.asarray(row['ecg']['v']).reshape(-1);peaks=np.asarray(row['ecg']['rpeaks']).reshape(-1)
            summaries.append({'subject':str(row['fix']['subj_name']),'ppg_fs':float(row['ppg']['fs']),'ecg_fs':float(row['ecg']['fs']),'duration_seconds':len(ppg)/float(row['ppg']['fs']),'ppg_samples':len(ppg),'ecg_samples':len(ecg),'ppg_finite_fraction':float(np.isfinite(ppg).mean()),'reference_beats':len(peaks),'reference_integer':bool(np.all(peaks==np.round(peaks))),'reference_strictly_increasing':bool(np.all(np.diff(peaks)>0)),'reference_valid_zero_based':bool(np.all((peaks>=0)&(peaks<len(ecg)))),'reference_valid_one_based':bool(np.all((peaks>=1)&(peaks<=len(ecg)))),'hr_offset':str(row['ref']['param']['hr'].get('offset','unspecified'))})
        assert len(set(r['subject'] for r in summaries))==len(rows)
        report['files'].append({**entry,'sha256':digest(path,'sha256'),'subjects':len(rows),'summaries':summaries})
        print(entry['activity'],len(rows),'subjects; checksum passed; schema audited',flush=True)
    (ROOT/'docs/acceptance/PPG_DALIA_AUDIT1.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
