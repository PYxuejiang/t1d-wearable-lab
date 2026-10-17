"""Independent source/one-to-one count/HR checks; publish aggregates only."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching

ROOT = Path(__file__).resolve().parents[1]


def main():
    import wfdb
    config = json.loads((ROOT / 'configs/ecg_capture_pilot_v1.json').read_text())
    dest = ROOT / 'outputs' / config['experiment']
    done = json.loads((dest / 'completed.json').read_text())
    arrays = json.loads((dest / 'peaks.json').read_text())
    metrics = json.loads((dest / 'metrics.json').read_text())
    audit = json.loads((dest / 'source_audit.json').read_text())
    assert len(arrays) == len(metrics) == done['metric_groups'] == 48
    for path, expected in done['frozen_files_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((dest / 'peaks.json').read_bytes()).hexdigest() == done['peaks_sha256']
    raw_annotations = {}
    for record in config['records']:
        ann = wfdb.rdann(str(ROOT / 'data/raw/mitdb_pilot' / record), 'atr')
        raw_annotations[record] = ann.sample[np.isin(ann.symbol, config['beat_symbols'])]
    checked = []
    timing_by_record = {}
    for values, row in zip(arrays, metrics):
        for key in ['record', 'window', 'method', 'fs']:
            assert values[key] == row[key]
        fs = values['fs']; width = int(round(fs * config['window_seconds']))
        assert values['start_sample'] == values['window'] * width
        assert values['end_sample_exclusive'] == values['start_sample'] + width
        ref, pred = np.array(values['reference']), np.array(values['predicted'])
        source = raw_annotations[values['record']] - values['start_sample']
        margin = round(config['edge_exclusion_seconds'] * fs)
        expected_ref = source[(source >= margin) & (source < width - margin)]
        assert np.array_equal(ref, expected_ref)
        assert np.all((pred >= margin) & (pred < width - margin))
        assert np.all(np.diff(pred) > 0)
        # Independent maximum-cardinality bipartite graph, not the runner's greedy matcher.
        graph = csr_matrix(abs(ref[:, None] - pred[None, :]) <= round(fs * config['match_tolerance_seconds']))
        matched = maximum_bipartite_matching(graph, perm_type='column')
        tp = int(np.sum(matched >= 0)); fn = len(ref) - tp; fp = len(pred) - tp
        # Reconstruct chronological pairs using binary search, independently of
        # the runner's two-pointer matcher. The graph above checks maximal count.
        next_prediction = 0
        timing = []
        tolerance = round(fs * config['match_tolerance_seconds'])
        for sample in ref:
            candidate = max(next_prediction, int(np.searchsorted(pred, sample - tolerance)))
            if candidate < len(pred) and pred[candidate] <= sample + tolerance:
                timing.append(abs(int(pred[candidate]) - int(sample)) / fs * 1000)
                next_prediction = candidate + 1
        assert len(timing) == tp
        assert abs(row['matched_timing_median_ms'] - np.median(timing)) < 1e-12
        timing_by_record.setdefault((values['record'], values['method']), []).extend(timing)
        expected = {'tp': tp, 'fn': fn, 'fp': fp, 'sensitivity': tp / len(ref),
                    'ppv': tp / len(pred), 'f1': 2 * tp / (len(ref) + len(pred))}
        for name, peaks in [('reference_hr', ref), ('predicted_hr', pred)]:
            rr = np.diff(peaks).astype(float) / fs
            rr = rr[(rr >= .3) & (rr <= 2)]
            expected[name] = float(60 / np.median(rr)) if len(rr) >= 5 else None
        for key, value in expected.items():
            assert row[key] is None if value is None else abs(row[key] - value) < 1e-12, (key, row, value)
        checked.append(row)
    assert {(r['record'], r['window'], r['method']) for r in checked} == {
        (r, w, m) for r in config['records'] for w in range(6) for m in config['methods']}
    record_summary = []
    for record in config['records']:
        for method in config['methods']:
            group = [r for r in checked if r['record'] == record and r['method'] == method]
            counts = {k: sum(r[k] for r in group) for k in ['tp', 'fn', 'fp']}
            tp, fn, fp = (counts[k] for k in ['tp', 'fn', 'fp'])
            errors = [r['predicted_hr'] - r['reference_hr'] for r in group
                      if r['predicted_hr'] is not None and r['reference_hr'] is not None]
            record_summary.append({'record': record, 'method': method, **counts,
                'sensitivity': tp / (tp + fn), 'ppv': tp / (tp + fp), 'f1': 2 * tp / (2 * tp + fp + fn),
                'window_hr_mae_bpm': float(np.mean(np.abs(errors))),
                'window_hr_bias_bpm': float(np.mean(errors)), 'valid_hr_windows': len(errors),
                'matched_timing_median_ms': float(np.median(timing_by_record[(record, method)]))})
    summary = {}
    gate = config['internal_pilot_gate']
    for method in config['methods']:
        groups = [r for r in record_summary if r['method'] == method]
        summary[method] = {k: float(np.mean([r[k] for r in groups]))
                          for k in ['f1', 'sensitivity', 'ppv', 'window_hr_mae_bpm', 'window_hr_bias_bpm']}
        summary[method]['pilot_gate_passed'] = bool(all(r['sensitivity'] >= gate['each_record_sensitivity_min'] and
            r['ppv'] >= gate['each_record_ppv_min'] for r in groups) and
            summary[method]['window_hr_mae_bpm'] <= gate['window_hr_mae_bpm_max'] and
            sum(r['valid_hr_windows'] for r in groups) == 24)
    result = {'experiment': config['experiment'], 'engineering_acceptance': 'passed',
        'independently_verified_metric_groups': len(checked), 'scope': config['scope'],
        'summary': summary, 'record_summary': record_summary, 'source_audit': audit,
        'frozen_protocol': config, 'provenance': done,
        'limitations': ['Four convenience records only; not all48 records or an independent target-device cohort.',
                       'ECG capture validation, not PPG, glucose estimation, hypoglycemia or clinical alarm validation.',
                       'Within-window retrospective defaults may use future samples relative to an individual beat; all samples precede window-end output.',
                       'Two-second edges per five-minute window and incomplete tails unscored for both methods.',
                       'HR uses RR in0.3–2s for both methods and expert reference; does not validate abnormal intervals or HRV morphology.',
                       'No detector replacement in PhysioCGM until a separate all-record check and target-domain quality gate.']}
    path = ROOT / 'docs/acceptance/ECG_CAPTURE_PILOT1.json'
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'groups': len(checked), 'summary': summary}, indent=2))


if __name__ == '__main__':
    main()
