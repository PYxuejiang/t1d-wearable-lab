"""Fixed four-record ECG pilot. Never tunes against the expert annotation."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.beat_capture import existing_energy_peaks, core_peaks, beat_metrics


def main():
    import wfdb
    from wfdb.processing import xqrs_detect
    config_path = ROOT / 'configs/ecg_capture_pilot_v1.json'
    config = json.loads(config_path.read_text())
    if importlib.metadata.version('wfdb') != config['wfdb_version']:
        raise RuntimeError('Use the frozen WFDB version')
    dest = ROOT / 'outputs' / config['experiment']
    dest.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'data/raw/mitdb_pilot'
    manifest = json.loads((source / 'manifest.json').read_text())
    for entry in manifest:
        assert hashlib.sha256((source / entry['file']).read_bytes()).hexdigest() == entry['sha256']
    rows, arrays, audits = [], [], []
    for record in config['records']:
        path = str(source / record)
        raw = wfdb.rdrecord(path, channels=[config['channel_index']])
        ann = wfdb.rdann(path, 'atr')
        fs = float(raw.fs)
        values = raw.p_signal[:, 0]
        assert np.isfinite(values).all()
        references = ann.sample[np.isin(ann.symbol, config['beat_symbols'])]
        width = int(round(fs * config['window_seconds']))
        audits.append({'record': record, 'fs': fs, 'channel': raw.sig_name[0],
                       'total_samples': len(values), 'complete_windows': len(values) // width,
                       'unused_tail_samples': len(values) % width,
                       'annotation_symbols': {s: ann.symbol.count(s) for s in sorted(set(ann.symbol))},
                       'scored_seconds': (len(values) // width) * (config['window_seconds'] - 2 * config['edge_exclusion_seconds'])})
        for index, start in enumerate(range(0, len(values) - width + 1, width)):
            window = values[start:start + width]
            ref = references[(references >= start) & (references < start + width)] - start
            ref = core_peaks(ref, width, fs, config['edge_exclusion_seconds'])
            candidates = {'existing_energy': existing_energy_peaks(window, fs),
                          'wfdb_xqrs_default': xqrs_detect(window, fs=fs, verbose=False)}
            for method, peaks in candidates.items():
                predicted = core_peaks(peaks, width, fs, config['edge_exclusion_seconds'])
                metrics = beat_metrics(ref, predicted, fs, int(round(fs * config['match_tolerance_seconds'])))
                key = {'record': record, 'window': index, 'method': method, 'fs': fs}
                rows.append({**key, **metrics})
                arrays.append({**key, 'reference': ref.tolist(), 'predicted': predicted.tolist(),
                               'start_sample': start, 'end_sample_exclusive': start + width})
        print(record, 'all complete windows scored', flush=True)
    for name, value in [('metrics.json', rows), ('peaks.json', arrays), ('source_audit.json', audits)]:
        (dest / name).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    fingerprints = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [config_path, Path(__file__), ROOT / 'src/t1d_lab/beat_capture.py', ROOT / 'src/t1d_lab/signals.py']}
    (dest / 'completed.json').write_text(json.dumps({'experiment': config['experiment'], 'metric_groups': len(rows),
        'source_files': manifest, 'frozen_files_sha256': fingerprints,
        'runtime': {p: importlib.metadata.version(p) for p in ['wfdb', 'numpy', 'scipy', 'pandas']},
        'peaks_sha256': hashlib.sha256((dest / 'peaks.json').read_bytes()).hexdigest()}, indent=2), encoding='utf-8')
    print('Complete:', len(rows), 'groups; run independent verifier next')


if __name__ == '__main__':
    main()
