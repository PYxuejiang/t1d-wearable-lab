import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.brist1d import read_subject
from t1d_lab.physiocgm import audit_archive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True, choices=['brist1d', 'physiocgm'])
    args = parser.parse_args()
    output = ROOT / 'outputs' / 'audit'
    output.mkdir(parents=True, exist_ok=True)
    suffix = '*.csv' if args.dataset == 'brist1d' else '*_raw.zip'
    reports = []
    for path in sorted((ROOT / 'data' / 'raw' / args.dataset).glob(suffix)):
        report = read_subject(path)[1] if args.dataset == 'brist1d' else audit_archive(path)
        reports.append(report)
        (output / f'{args.dataset}_{report["subject"]}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(report['subject'], 'audited', flush=True)
    result = {'dataset': args.dataset, 'subjects_audited': len(reports), 'reports': reports}
    (output / f'{args.dataset}_cohort.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'{len(reports)} subjects audited; no model performance claimed.', flush=True)


if __name__ == '__main__':
    main()
