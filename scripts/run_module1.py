import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.forecasting import build_features, run_forecast

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--protocol', choices=['temporal', 'loso', 'both'], default='both')
    parser.add_argument('--max-subjects', type=int)
    args = parser.parse_args()
    if args.build_only:
        result = build_features(ROOT)
        print('Causal features',len(result),'subjects',result.subject.nunique())
    else:
        protocols = ('temporal','loso') if args.protocol == 'both' else (args.protocol,)
        print(json.dumps(run_forecast(ROOT, protocols, args.max_subjects),indent=2))
