import argparse
import json
import hashlib
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.physiocgm import audit_archive
from t1d_lab.signals import extract_subject

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int)
    parser.add_argument('--watch',action='store_true',help='Process arriving verified ZIPs until all 10 subjects are handled')
    args=parser.parse_args()
    fingerprint=hashlib.sha256((ROOT/'src/t1d_lab/signals.py').read_bytes()).hexdigest()
    handled=set()
    while True:
      paths=sorted((ROOT/'data/raw/physiocgm').glob('*_raw.zip'))
      if args.limit: paths=paths[:args.limit]
      for path in paths:
        subject=path.name.removesuffix('_raw.zip')
        if subject in handled: continue
        output=ROOT/'data/processed'/f'{subject}_signal_features.parquet'
        provenance=output.with_suffix('.provenance.json')
        if output.exists() and provenance.exists() and json.loads(provenance.read_text()).get('extractor_sha256')==fingerprint:
            print('Already extracted',subject,flush=True)
            handled.add(subject)
            continue
        audit_path=ROOT/'outputs/audit'/f'physiocgm_{subject}.json'
        report=json.loads(audit_path.read_text()) if audit_path.exists() else audit_archive(path)
        audit_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        if not report['clock_resolved_by_sensor_check']:
            print('QUARANTINED unresolved clock',subject,flush=True)
            handled.add(subject)
            continue
        frame,clock=extract_subject(path,report)
        output.parent.mkdir(exist_ok=True,parents=True)
        frame.to_parquet(output,index=False)
        provenance.write_text(json.dumps({'extractor_sha256':fingerprint,'source_archive':path.name,'clock_shift_hours':report['best_clock_candidate']['shift_hours']},indent=2),encoding='utf-8')
        (ROOT/'outputs/audit'/f'{subject}_sample_clocks.json').write_text(json.dumps(clock,indent=2),encoding='utf-8')
        print('Extracted',subject,len(frame),'reference anchors',flush=True)
        handled.add(subject)
      if not args.watch or len(handled)>=10: break
      print('Waiting for verified source ZIPs; handled',len(handled),flush=True)
      time.sleep(10)
