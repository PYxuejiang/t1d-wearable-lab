"""Strict dual-annotator label audit; no detector training or scoring."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'on': ('os', 0, 2), 'off': ('os', 1, 2), 'pk': ('pk', 0, 1), 'u': ('u', 0, 1)}


def parse(annot, field, n, fs):
    source, index, required = FIELDS[field]
    values = np.asarray(annot.get(source, {}).get('t', []), dtype=float).reshape(-1)
    if len(values) != required: return None, 'wrong_count'
    if not np.isfinite(values).all(): return None, 'nonfinite'
    if source == 'os' and values[1] <= values[0]: return None, 'unordered_boundaries'
    t = float(values[index])
    if t < 0 or t > (n-1)/fs: return None, 'outside_sample_time'
    return t, 'valid'


def stats(values):
    x = np.asarray(values, float)*1000
    if not len(x): return {'pairs': 0, 'pair_coverage': 0}
    return {'pairs': len(x), 'pair_coverage': len(x)/219, 'bias_ms_mg_minus_pc': float(x.mean()),
            'mae_ms': float(np.abs(x).mean()), 'median_abs_ms': float(np.median(abs(x))),
            'p95_abs_ms': float(np.quantile(abs(x), .95)),
            'within_ms': {str(t): float(np.mean(abs(x) <= t+1e-9)) for t in [10, 20, 50]}}


def main():
    out = ROOT/'outputs/ppg_label_audit_v1'; out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()): raise RuntimeError('Preserve previous results; output must be empty')
    raw = (ROOT/'data/ppg_bp_annot/PPG-BP_annot.zip').read_bytes()
    assert hashlib.md5(raw).hexdigest() == '1b03371ca9cfad39ab7209425673b351'
    archive = zipfile.ZipFile(io.BytesIO(raw))
    signals = loadmat(io.BytesIO(archive.read('PPG-BP_ref1.mat')), simplify_cells=True)['ppg_data']
    sets = {}
    for who in ['MG', 'PC']:
        path = f'{who}final_PPG-BP_annot/{who}final_PPG-BP_annot.mat'
        values = loadmat(io.BytesIO(archive.read(path)), simplify_cells=True)['fiducial_annot']
        sets[who] = {r['name']: r['annot'] for r in values}
        assert len(values) == len(sets[who]) == 219
    counts = {who: {f: {} for f in FIELDS} for who in sets}
    mismatch = {who: 0 for who in sets}; order_bad = {who: 0 for who in sets}
    endpoint_extra = {who: {f: 0 for f in FIELDS} for who in sets}
    local = []
    for row in signals:
        name, n, fs = row['name'], len(row['sig']), row['fs']; item = {'name': name, 'values': {}}
        for who in sets:
            a = sets[who][name]
            merged = loadmat(io.BytesIO(archive.read(f'{who}final_PPG-BP_annot/merged/{name}.mat')), simplify_cells=True)['annot']
            matches = all(np.array_equal(np.asarray(a[k]['t']), np.asarray(merged[k]['t']), equal_nan=True) for k in ['pk','u','os'])
            mismatch[who] += int(not matches)
            v = {}
            for f in FIELDS:
                value, reason = parse(a, f, n, fs); v[f] = value
                counts[who][f][reason] = counts[who][f].get(reason, 0)+1
                source, index, required = FIELDS[f]
                arr = np.asarray(a.get(source, {}).get('t', []), float).reshape(-1)
                if len(arr) == required and np.isfinite(arr).all():
                    endpoint_extra[who][f] += int((n-1)/fs < arr[index] <= n/fs)
            if all(x is not None for x in v.values()):
                order_bad[who] += int(not (v['on'] < v['u'] < v['pk'] < v['off']))
            item['values'][who] = v
        local.append(item)
    summaries = {f: stats([r['values']['MG'][f]-r['values']['PC'][f] for r in local if all(r['values'][w][f] is not None for w in sets)]) for f in FIELDS}
    result = {'stage': 'PPG_LABEL_AUDIT1', 'scope': 'Label audit only; no algorithm performance', 'entries': 219,
              'archive_sha256': hashlib.sha256(raw).hexdigest(), 'counts': counts, 'summary_merged_mismatch_records': mismatch,
              'order_violations_among_complete': order_bad, 'duration_endpoint_extra': endpoint_extra,
              'agreement': summaries, 'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/audit_ppg_labels.py', 'docs/METHOD_PPG_LABEL_AUDIT1.zh-CN.md']}}
    (out/'records_local.json').write_text(json.dumps(local, indent=2, allow_nan=False))
    (ROOT/'docs/acceptance/PPG_LABEL_AUDIT1.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
