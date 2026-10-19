"""Frozen development-only calibration sensitivity; never selects on tail scores."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.ppg_capture import match_seconds, metrics, summarize

GRID = np.round(np.arange(-1.5, 1.501, .01), 2)
SEGMENTS = {'first60': (0, 60), 'second60': (60, 120), 'first120': (0, 120)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arrays(row, lag):
    a = np.asarray(row['reference'])
    b = np.asarray(row['detected']['v5_peaks']) - lag
    return a[(a >= 4) & (a < 26)], b[(b >= 4) & (b < 26)]


def select(rows):
    scores = [(sum(len(match_seconds(*arrays(row, lag))) for row in rows), float(lag)) for lag in GRID]
    key = lambda item: (item[0], -abs(item[1] - .2), -item[1])
    tp, lag = max(scores, key=key)
    rival_tp, rival = max((item for item in scores if abs(item[1] - lag) >= .3 - 1e-9), key=key)
    intervals = np.concatenate([np.diff(np.asarray(row['reference'])) for row in rows])
    rr = float(np.median(intervals))
    cycles = abs(rival - lag) / rr
    return {'lag': lag, 'tp': tp, 'rival_lag': rival, 'rival_fraction': rival_tp / tp if tp else None,
            'near_integer_cycle': bool(round(cycles) >= 1 and abs(cycles - round(cycles)) <= .15),
            'boundary': bool(abs(lag) == 1.5)}


def score(rows, lag):
    return summarize([metrics(*arrays(row, lag)) for row in rows])


def synthetic():
    rng = np.random.default_rng(20261019)
    irregular = np.cumsum(rng.uniform(.42, 1.4, 55))
    irregular = irregular[irregular < 28]
    row = lambda ref, lag: {'reference': ref.tolist(), 'detected': {'v5_peaks': (ref + lag).tolist()}}
    stable = select([row(irregular, .45)])
    periodic = select([row(np.arange(.5, 29, .8), .2)])
    changed = select([row(irregular, .85)])
    # A 100ms matching plateau need not recover the exact synthetic offset.
    assert abs(stable['lag'] - .45) <= .1 + 1e-12
    assert periodic['rival_fraction'] >= .95 and periodic['near_integer_cycle']
    assert abs(changed['lag'] - stable['lag']) > .1
    return {'fixed_offset_within_tolerance': True, 'periodic_ambiguity_flagged': True,
            'changed_offset_flagged': True, 'scope': 'Synthetic software controls only'}


def main():
    out = ROOT / 'outputs/ppg_stability_dev_v1'
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise RuntimeError('Preserve completed or partial attempt; output must be empty')
    cache = ROOT / 'outputs/ppg_capture_v1'
    digest = sha(cache / 'windows.json')
    assert digest == json.loads((cache / 'complete.json').read_text())['windows_sha256']
    rows = [r for r in json.loads((cache / 'windows.json').read_text()) if r['phase'] == 'development']
    assert {r['subject'] for r in rows} == {'S1', 'S2', 'S3', 'S4', 'S5'} and len(rows) == 211
    meta = {r['key']: r for r in json.loads((cache / 'records.json').read_text()) if r['phase'] == 'development'}
    controls = synthetic()
    local = []
    for key in sorted(meta):
        rr = [r for r in rows if r['key'] == key]
        tail = [r for r in rr if r['start'] >= 120]
        arms = {}
        for name, (start, end) in SEGMENTS.items():
            calibration = [r for r in rr if start <= r['start'] < end]
            assert len(calibration) == (end - start) // 30
            choice = select(calibration)
            arms[name] = {'choice': choice, 'tail': score(tail, choice['lag'])}
        assert len({v['tail']['tp'] + v['tail']['fn'] for v in arms.values()}) == 1
        local.append({'key': key, 'subject': rr[0]['subject'], 'activity': rr[0]['activity'], 'arms': arms,
                      'coverage': 22 * len(tail) / (meta[key]['duration'] - 120),
                      'lag_difference_seconds': abs(arms['first60']['choice']['lag'] - arms['second60']['choice']['lag']),
                      'tail_f1_absolute_difference': abs(arms['first60']['tail']['f1'] - arms['second60']['tail']['f1'])})
    public = {'stage': 'PPG_STABILITY_DEV1', 'subjects': 5, 'records': len(local), 'windows': len(rows),
              'scope': 'Development-only reference-assisted sensitivity; no detector or disease gain',
              'synthetic': controls, 'cache_sha256': digest, 'by_activity': {},
              'source_sha256': {p: sha(ROOT / p) for p in ['scripts/audit_ppg_stability_dev.py', 'docs/METHOD_PPG_STABILITY_DEV1.zh-CN.md', 'src/t1d_lab/ppg_capture.py']}}
    metric_names = ['f1', 'ppv', 'sensitivity', 'ppi_mae_ms', 'ppi_pair_coverage']
    for activity in ['sitting', 'walking']:
        subset = [r for r in local if r['activity'] == activity]
        result = {'records': len(subset), 'stable_records': sum(r['lag_difference_seconds'] <= .1 + 1e-12 for r in subset),
                  'median_lag_difference_seconds': float(np.median([r['lag_difference_seconds'] for r in subset])),
                  'mean_tail_f1_absolute_difference': float(np.mean([r['tail_f1_absolute_difference'] for r in subset])),
                  'core_time_coverage': float(np.mean([r['coverage'] for r in subset])), 'arms': {}}
        for name in SEGMENTS:
            choices = [r['arms'][name]['choice'] for r in subset]
            ambiguous = [c for c in choices if c['rival_fraction'] is not None and c['rival_fraction'] >= .95]
            values = {m: float(np.mean([r['arms'][name]['tail'][m] for r in subset])) for m in metric_names}
            values.update(ambiguous_records=len(ambiguous), cycle_like_ambiguous_records=sum(c['near_integer_cycle'] for c in ambiguous), boundary_records=sum(c['boundary'] for c in choices))
            result['arms'][name] = values
        public['by_activity'][activity] = result
    subject_diffs = np.array([np.mean([r['tail_f1_absolute_difference'] for r in local if r['subject'] == subject]) for subject in sorted({r['subject'] for r in local})])
    rng = np.random.default_rng(20261019)
    boot = rng.choice(subject_diffs, (10000, 5), replace=True).mean(axis=1)
    public['tail_f1_sensitivity'] = {'mean_absolute_difference': float(subject_diffs.mean()), '95_interval': np.quantile(boot, [.025, .975]).tolist(), 'subjects': 5}
    (out / 'records_local.json').write_text(json.dumps(local, indent=2, allow_nan=False))
    (ROOT / 'docs/acceptance/PPG_STABILITY_DEV1.json').write_text(json.dumps(public, indent=2, allow_nan=False))
    print(json.dumps(public, indent=2))


if __name__ == '__main__':
    main()
