"""Cache official BUT PPG 2.0 metadata and four fixed headers, not waveforms.
Checksum manifest uses the public S3 mirror linked from the PhysioNet page.
Existing files are reused and checked by audit_but_source.py.
"""
from pathlib import Path
import csv, hashlib, json, time
import requests
ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://physionet.org/files/butppg/2.0.0/'
S3 = 'https://physionet-open.s3.amazonaws.com/butppg/2.0.0/'
def fetch(root=ROOT):
    out = root/'outputs/but_source_v1'
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    def cache(name):
        p = out/name
        p.parent.mkdir(parents=True, exist_ok=True)
        url = (S3 if name == 'SHA256SUMS.txt' else BASE)+name
        if not p.exists():
            temporary = p.with_name(p.name+'.partial')
            started = time.monotonic()
            with requests.get(url, stream=True, timeout=(15, 30)) as r:
                r.raise_for_status()
                with temporary.open('wb') as stream:
                    for chunk in r.iter_content(4096):
                        if time.monotonic()-started > 180:
                            raise TimeoutError('Metadata transfer exceeded 180 seconds')
                        stream.write(chunk)
            temporary.replace(p)
        manifest[name] = {'url':url,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    for name in ['LICENSE.txt','RECORDS.txt','quality-hr-ann.csv','subject-info.csv','ANNOTATORS','SHA256SUMS.txt']:
        cache(name)
    with (out/'quality-hr-ann.csv').open(encoding='utf-8-sig',newline='') as f:
        ids = [r['ID'] for r in csv.DictReader(f)]
    old = sorted(i for i in ids if int(i[:3]) < 112)
    new = sorted(i for i in ids if int(i[:3]) >= 112)
    for i in [old[0],old[-1],new[0],new[-1]]:
        cache(f'{i}/{i}_PPG.hea')
    (out/'download_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('metadata_and_headers_cached',len(manifest))
if __name__=='__main__':fetch()
