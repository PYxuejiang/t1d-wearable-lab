"""Independent searchsorted verifier for frozen calibration and tail metrics."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def recount(row, lag):
    a = np.asarray(row['reference']); b = np.asarray(row['detected']['v5_peaks']) - lag
    a = a[(a >= 4) & (a < 26)]; b = b[(b >= 4) & (b < 26)]
    pairs = []; next_index = 0
    for i, t in enumerate(a):
        j = max(next_index, int(np.searchsorted(b, t - .1 - 1e-12)))
        if j < len(b) and b[j] <= t + .1 + 1e-12:
            pairs.append((i, j)); next_index = j + 1
    errors = [abs((b[l] - b[j]) - (a[k] - a[i])) * 1000 for (i, j), (k, l) in zip(pairs, pairs[1:]) if k == i + 1 and l == j + 1]
    return np.array([len(pairs), len(a) - len(pairs), len(b) - len(pairs), len(errors), max(0, len(a) - 1), sum(errors)])


def main():
    public_path = ROOT / 'docs/acceptance/PPG_STABILITY_DEV1.json'
    public = json.loads(public_path.read_text())
    for file, digest in public['source_sha256'].items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == digest
    cache = ROOT / 'outputs/ppg_capture_v1/windows.json'
    assert hashlib.sha256(cache.read_bytes()).hexdigest() == public['cache_sha256']
    rows = [r for r in json.loads(cache.read_text()) if r['phase'] == 'development']
    local = json.loads((ROOT / 'outputs/ppg_stability_dev_v1/records_local.json').read_text())
    assert len(rows) == 211 and len(local) == 10
    segments = {'first60': (0, 60), 'second60': (60, 120), 'first120': (0, 120)}
    grid = np.round(np.arange(-1.5, 1.501, .01), 2)
    for record in local:
        rr = [r for r in rows if r['key'] == record['key']]
        denominators = []
        for name, (start, end) in segments.items():
            cal = [r for r in rr if start <= r['start'] < end]
            counts = {float(lag): int(sum(recount(r, lag)[0] for r in cal)) for lag in grid}
            tie = lambda lag: (counts[lag], -abs(lag - .2), -lag)
            chosen = max(counts, key=tie)
            rival = max((lag for lag in counts if abs(lag - chosen) >= .3 - 1e-9), key=tie)
            item = record['arms'][name]; choice = item['choice']
            assert chosen == choice['lag'] and rival == choice['rival_lag']
            assert counts[chosen] == choice['tp']
            ratio = counts[rival] / counts[chosen] if counts[chosen] else None
            assert ratio == choice['rival_fraction']
            rr_median = np.median(np.concatenate([np.diff(r['reference']) for r in cal]))
            cycles = abs(rival - chosen) / rr_median
            assert bool(round(cycles) >= 1 and abs(cycles - round(cycles)) <= .15) == choice['near_integer_cycle']
            totals = np.sum([recount(r, chosen) for r in rr if r['start'] >= 120], axis=0)
            keys = ['tp', 'fn', 'fp', 'ppi_pairs', 'reference_pairs', 'ppi_abs_sum_ms']
            assert np.allclose(totals, [item['tail'][k] for k in keys], rtol=0, atol=1e-8)
            tp, fn, fp, pp, rp, err = totals
            expected = {'f1': 2*tp/(2*tp+fn+fp), 'ppv': tp/(tp+fp), 'sensitivity': tp/(tp+fn), 'ppi_pair_coverage': pp/rp, 'ppi_mae_ms': err/pp}
            for key, value in expected.items(): assert abs(value - item['tail'][key]) < 1e-10
            denominators.append(tp+fn)
        assert len(set(denominators)) == 1
        assert abs(record['lag_difference_seconds'] - abs(record['arms']['first60']['choice']['lag'] - record['arms']['second60']['choice']['lag'])) < 1e-12
    meta = json.loads((ROOT / 'outputs/ppg_capture_v1/records.json').read_text())
    for activity in ['sitting', 'walking']:
        subset = [r for r in local if r['activity'] == activity]
        aggregate = public['by_activity'][activity]
        assert aggregate['stable_records'] == sum(r['lag_difference_seconds'] <= .1+1e-12 for r in subset)
        records = [r for r in meta if r['phase'] == 'development' and r['activity'] == activity]
        coverage = np.mean([22*r['score_windows']/(r['duration']-120) for r in records])
        assert abs(coverage - aggregate['core_time_coverage']) < 1e-12
        for name in segments:
            for metric in ['f1', 'ppv', 'sensitivity', 'ppi_pair_coverage', 'ppi_mae_ms']:
                assert abs(np.mean([r['arms'][name]['tail'][metric] for r in subset]) - aggregate['arms'][name][metric]) < 1e-10
            choices = [r['arms'][name]['choice'] for r in subset]
            ambiguous = [c for c in choices if c['rival_fraction'] is not None and c['rival_fraction'] >= .95]
            assert aggregate['arms'][name]['ambiguous_records'] == len(ambiguous)
            assert aggregate['arms'][name]['cycle_like_ambiguous_records'] == sum(c['near_integer_cycle'] for c in ambiguous)
    diffs = np.array([np.mean([abs(r['arms']['first60']['tail']['f1'] - r['arms']['second60']['tail']['f1']) for r in local if r['subject'] == subject]) for subject in sorted({r['subject'] for r in local})])
    boot = np.random.default_rng(20261019).choice(diffs, (10000, 5), replace=True).mean(axis=1)
    assert abs(diffs.mean() - public['tail_f1_sensitivity']['mean_absolute_difference']) < 1e-12
    assert np.allclose(np.quantile(boot, [.025, .975]), public['tail_f1_sensitivity']['95_interval'], rtol=0, atol=1e-12)
    assert all(key not in json.dumps(public) for key in ['S1/', 'S2/', 'S3/', 'S4/', 'S5/', '"rival_lag":', '"reference":'])
    public['verification'] = {'status': 'passed', 'calibration_choices': 30, 'tail_count_and_ppi_groups': 30, 'equal_reference_denominators': True, 'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    public_path.write_text(json.dumps(public, indent=2, allow_nan=False))
    print('Verified 30 calibration choices, 30 tail count/PPI groups, aggregates and paired interval')


if __name__ == '__main__':
    main()
