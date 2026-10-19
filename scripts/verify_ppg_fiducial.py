"""Independent MAT/object parse and extrema/aggregate verification; local records stay private."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np
from scipy import signal
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('raw', 'causal5', 'offline12')


def equal(actual, expected):
    if isinstance(expected, dict):
        assert set(actual) == set(expected)
        for key in expected: equal(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for a, e in zip(actual, expected): equal(a, e)
    elif isinstance(expected, (float, np.floating)):
        assert np.isclose(actual, expected, rtol=0, atol=1e-10)
    else:
        assert actual == expected


def reference(annotation, length, fs):
    bounds = np.atleast_1d(annotation.os.t).astype(float)
    peaks = np.atleast_1d(annotation.pk.t).astype(float)
    slopes = np.atleast_1d(annotation.u.t).astype(float)
    if bounds.size != 2 or not all(np.isfinite(bounds)): return None
    left, right = bounds
    if not 0 <= left < right <= (length-1)/fs: return None
    inside = [p for p in peaks if left < p < right]
    if len(inside) != 1 or slopes.size != 1: return None
    if not left < slopes[0] < inside[0] < right: return None
    return {'pk': float(inside[0]), 'u': float(slopes[0])}


def extrema(x, fs, bounds, arm):
    values = np.asarray(x, float)
    if arm != 'raw':
        sections = signal.butter(3, [.5, 5 if arm == 'causal5' else 12], fs=fs, btype='bandpass', output='sos')
        values = signal.sosfilt(sections, values) if arm == 'causal5' else signal.sosfiltfilt(sections, values)
    left, right = [round(float(t)*fs) for t in bounds]
    assert 0 <= left < right < len(values)
    peak = max(range(left, right), key=lambda i: (values[i], -i))
    def derivative(i):
        if i == 0: return (values[1]-values[0])*fs
        if i == len(values)-1: return (values[-1]-values[-2])*fs
        return (values[i+1]-values[i-1])*fs/2
    up = max(range(left, peak+1), key=lambda i: (derivative(i), -i))
    return {'pk': peak/fs, 'u': up/fs, 'strict_order': bool(left < up < peak < right)}


def summary(errors, denominator):
    values = np.asarray(errors)*1000
    absolute = np.abs(values)
    return {'n': len(values), 'reference_coverage': len(values)/denominator,
            'mae_ms': float(np.mean(absolute)), 'median_abs_ms': float(np.median(absolute)),
            'p95_abs_ms': float(np.percentile(absolute, 95)), 'bias_ms': float(np.mean(values)),
            'within_ms': {str(t): float(np.count_nonzero(absolute <= t+1e-9)/len(values)) for t in (10,20,50)}}


def main():
    path = ROOT/'docs/acceptance/PPG_FIDUCIAL1.json'
    public = json.loads(path.read_text())
    for name, digest in public['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
    raw = (ROOT/'data/ppg_bp_annot/PPG-BP_annot.zip').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == public['archive_sha256']
    archive = zipfile.ZipFile(io.BytesIO(raw))
    def read(name): return loadmat(io.BytesIO(archive.read(name)), struct_as_record=False, squeeze_me=True)
    signals = read('PPG-BP_ref1.mat')['ppg_data']
    annotations = {w: {r.name: r.annot for r in read(f'{w}final_PPG-BP_annot/{w}final_PPG-BP_annot.mat')['fiducial_annot']} for w in ('MG','PC')}
    names = [s.name for s in signals]
    assert len(set(names)) == len(names) == 219
    assert all(set(a) == set(names) for a in annotations.values())
    development = set(sorted(names, key=lambda n: hashlib.sha256(('PPG_FIDUCIAL1/'+n).encode()).hexdigest())[:70])
    rebuilt = []
    for s in signals:
        rebuilt.append({'name': s.name, 'phase': 'development' if s.name in development else 'evaluation',
                        'reference': {w: reference(annotations[w][s.name], s.sig.size, s.fs) for w in annotations},
                        'predictions': {a: extrema(s.sig, s.fs, np.atleast_1d(annotations['MG'][s.name].os.t), a) for a in ARMS}})
    saved = json.loads((ROOT/'outputs/ppg_fiducial_v1/records_local.json').read_text())
    equal(saved, rebuilt)
    totals = {'development': 70, 'evaluation': 149, 'total': 219}
    equal(public['counts'], totals)
    computed = {}
    for phase in ('development','evaluation'):
        rows = [r for r in rebuilt if r['phase'] == phase]
        assert len(rows) == totals[phase]
        computed[phase] = {}
        for arm in ARMS:
            item = {'output_fraction': sum(r['predictions'][arm] is not None for r in rows)/len(rows),
                    'strict_order_fraction': sum(r['predictions'][arm]['strict_order'] for r in rows)/len(rows)}
            for who in annotations:
                item[who] = {f: summary([r['predictions'][arm][f]-r['reference'][who][f] for r in rows if r['reference'][who] is not None], len(rows)) for f in ('pk','u')}
            computed[phase][arm] = item
    equal(public['results'], computed)
    objectives = {a: sum(computed['development'][a]['MG'][f]['mae_ms'] for f in ('pk','u'))/2 for a in ARMS}
    chosen = min(ARMS, key=lambda a: (objectives[a], ARMS.index(a)))
    equal(public['selection'], {'selected': chosen, 'development_mg_joint_mae_ms': objectives, 'evaluation_used': False})
    paired = {}
    for who in annotations:
        rows = [r for r in rebuilt if r['phase'] == 'evaluation' and r['reference'][who] is not None]
        paired[who] = {}
        for field in ('pk','u','joint'):
            fields = ('pk','u') if field == 'joint' else (field,)
            deltas = np.array([sum((abs(r['predictions'][chosen][f]-r['reference'][who][f])-abs(r['predictions']['causal5'][f]-r['reference'][who][f]))*1000 for f in fields)/len(fields) for r in rows])
            indices = np.random.default_rng(20261019).integers(0, len(rows), size=(10000,len(rows)))
            paired[who][field] = {'n': len(rows), 'selected_minus_causal5_mae_ms': float(deltas.mean()), '95_interval': np.percentile(deltas[indices].mean(axis=1), [2.5,97.5]).tolist()}
    equal(public['paired'], paired)
    # Analytic synthetic checks test the frozen runner, not patient labels.
    from run_ppg_fiducial import locate
    fs = 1000
    t = np.arange(2000)/fs
    gaussian = np.exp(-((t-1)/.1)**2/2)
    p = locate(gaussian, fs, [.5,1.5], 'raw')
    assert p == {'pk': 1., 'u': .9, 'strict_order': True}
    assert locate(np.ones(2000),fs,[.5,1.5],'raw') == {'pk':.5,'u':.5,'strict_order':False}
    assert locate(gaussian,fs,[1.5,.5],'raw') is None
    public['verification'] = {'status': 'passed', 'entries': 219, 'predictions_recomputed': 657,
                              'reference_mappings_reparsed': 438, 'metric_groups_checked': 24,
                              'paired_intervals_checked': 6, 'synthetic_checks': 3,
                              'shared_numerical_dependency': 'SciPy filter kernels; separate parser/extrema/derivative/aggregation code',
                              'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    path.write_text(json.dumps(public, indent=2, allow_nan=False))
    print(json.dumps(public['verification'], indent=2))


if __name__ == '__main__': main()
