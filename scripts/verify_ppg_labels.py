"""Reparse MATLAB objects independently; verify label-only aggregate audit."""
import collections
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT/'docs/acceptance/PPG_LABEL_AUDIT1.json'
    public = json.loads(target.read_text())
    for p, digest in public['source_sha256'].items(): assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == digest
    raw = (ROOT/'data/ppg_bp_annot/PPG-BP_annot.zip').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == public['archive_sha256']
    z = zipfile.ZipFile(io.BytesIO(raw))
    def read(p): return loadmat(io.BytesIO(z.read(p)), struct_as_record=False, squeeze_me=True)
    signals = {r.name: r for r in read('PPG-BP_ref1.mat')['ppg_data']}
    fields = {'on': ('os', 0, 2), 'off': ('os', 1, 2), 'pk': ('pk', 0, 1), 'u': ('u', 0, 1)}
    values = {}; diagnostics = {}
    for who in ['MG', 'PC']:
        rows = read(f'{who}final_PPG-BP_annot/{who}final_PPG-BP_annot.mat')['fiducial_annot']
        assert len(rows) == 219 and {r.name for r in rows} == set(signals)
        counts = {f: collections.Counter() for f in fields}; output = {}; cardinality = collections.Counter(); in_bounds = collections.Counter()
        mismatch = order_bad = 0; extra = {f: 0 for f in fields}
        for r in rows:
            s = signals[r.name]; output[r.name] = {}
            merged = read(f'{who}final_PPG-BP_annot/merged/{r.name}.mat')['annot']
            mismatch += int(any(not np.array_equal(np.atleast_1d(getattr(r.annot,k).t), np.atleast_1d(getattr(merged,k).t), equal_nan=True) for k in ['pk','os','u']))
            pk = np.atleast_1d(r.annot.pk.t).astype(float); os = np.atleast_1d(r.annot.os.t).astype(float)
            cardinality[str(len(pk))] += 1
            if len(os) == 2 and np.isfinite(os).all() and os[1] > os[0]:
                in_bounds[str(int(np.sum((pk > os[0]) & (pk < os[1]))))] += 1
            else: in_bounds['invalid_os'] += 1
            for f, (src, index, size) in fields.items():
                x = np.atleast_1d(getattr(r.annot,src).t).astype(float)
                reason = 'valid'; v = None
                if len(x) != size: reason = 'wrong_count'
                elif not np.isfinite(x).all(): reason = 'nonfinite'
                elif src == 'os' and x[1] <= x[0]: reason = 'unordered_boundaries'
                elif not 0 <= x[index] <= (s.sig.size-1)/s.fs: reason = 'outside_sample_time'
                else: v = float(x[index])
                if len(x) == size and np.isfinite(x).all(): extra[f] += int((s.sig.size-1)/s.fs < x[index] <= s.sig.size/s.fs)
                counts[f][reason] += 1; output[r.name][f] = v
            v = output[r.name]
            if all(x is not None for x in v.values()): order_bad += int(not v['on'] < v['u'] < v['pk'] < v['off'])
        assert {f: dict(v) for f,v in counts.items()} == public['counts'][who]
        assert mismatch == public['summary_merged_mismatch_records'][who] == 0
        assert order_bad == public['order_violations_among_complete'][who]
        assert extra == public['duration_endpoint_extra'][who]
        values[who] = output
        diagnostics[who] = {'pk_cardinality': dict(cardinality), 'pk_count_strictly_inside_own_os': dict(in_bounds)}
    local = json.loads((ROOT/'outputs/ppg_label_audit_v1/records_local.json').read_text())
    for r in local:
        for who in values: assert r['values'][who] == values[who][r['name']]
    for f in fields:
        x = np.array([(values['MG'][n][f]-values['PC'][n][f])*1000 for n in signals if all(values[w][n][f] is not None for w in values)])
        a = public['agreement'][f]
        assert a['pairs'] == len(x) and a['pair_coverage'] == len(x)/219
        for key,v in [('bias_ms_mg_minus_pc',x.mean()),('mae_ms',abs(x).mean()),('median_abs_ms',np.median(abs(x))),('p95_abs_ms',np.quantile(abs(x),.95))]: assert abs(a[key]-v)<1e-10
        for t in [10,20,50]: assert abs(a['within_ms'][str(t)]-np.mean(abs(x)<=t+1e-9))<1e-12
    public['post_audit_cardinality_diagnostic'] = diagnostics
    public['verification'] = {'status': 'passed', 'entries': 219, 'collections': 2, 'field_slots_reparsed': 1752, 'aggregate_fields_checked': 4, 'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    target.write_text(json.dumps(public, indent=2, allow_nan=False))
    print(json.dumps({'verification':public['verification'],'cardinality':diagnostics},indent=2))


if __name__ == '__main__': main()
