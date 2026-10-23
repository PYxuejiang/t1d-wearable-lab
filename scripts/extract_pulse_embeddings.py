"""Label-blind fixed-source embedding cache. No test subjects loaded by default."""
import argparse
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.pretrained_ppg import load_encoder, encode_segments, file_sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / 'configs/pulse_temporal_fit_v1.json').read_text())
    torch.set_num_threads(4)
    encoder = load_encoder(ROOT / 'outputs/pulseppg_source/pulseppg/nets/ResNet1D/ResNet1D_Net.py',
                           ROOT / 'outputs/multimodal_source_v1/pulseppg_checkpoint.pt',
                           '485ade5033b3baa9b82e252fc131042dda897d7bdfc0d1a030d9746a1e98857c')
    source = ROOT / 'outputs/improvement_v2/features.parquet'
    # Column projection excludes all glucose and label columns from extraction.
    frame = pd.read_parquet(source, columns=['subject', 'available', 'decision_time'])
    clock = json.loads((ROOT / 'docs/acceptance/S1b.json').read_text())
    offsets = {r['subject']: r['clock_shift_hours'] for r in clock['audit'] if r['status'] == 'extracted'}
    fingerprint = {name: file_sha256(ROOT / name) for name in ['configs/pulse_temporal_fit_v1.json',
                    'src/t1d_lab/pretrained_ppg.py', 'scripts/extract_pulse_embeddings.py']}
    fingerprint['anchor_source'] = file_sha256(source)
    for subject in cfg['subjects']['train'] + cfg['subjects']['validation']:
        dest, marker = args.output / f'{subject}.npz', args.output / f'{subject}.json'
        if marker.exists():
            old = json.loads(marker.read_text())
            if old['source_hashes'] != fingerprint or old['embedding_sha256'] != file_sha256(dest):
                raise ValueError('Cached embedding provenance changed')
            print(subject, 'verified cache', flush=True)
            continue
        if dest.exists():
            raise ValueError('Unverified partial cache; use new output directory')
        anchors = pd.DatetimeIndex(frame.loc[(frame.subject == subject) & frame.available, 'decision_time'])
        used, failed, vectors, times = set(), 0, [], []
        with ZipFile(ROOT / 'data/raw/physiocgm' / f'{subject}_raw.zip') as archive:
            for member in sorted(n for n in archive.namelist() if n.endswith('/BVP.csv')):
                with archive.open(member) as stream:
                    epoch = float(stream.readline().decode().split(',')[0]) + offsets[subject] * 3600
                    fs = float(stream.readline().decode().split(',')[0])
                    if fs != 64:
                        raise ValueError('Unexpected raw sample rate')
                    try:
                        values = pd.read_csv(stream, header=None, usecols=[0]).iloc[:, 0].to_numpy(float)
                    except pd.errors.EmptyDataError:
                        continue
                eligible = anchors[(anchors >= pd.Timestamp(epoch + 8, unit='s')) &
                                   (anchors < pd.Timestamp(epoch + len(values) / fs, unit='s'))]
                windows, ends = [], []
                for time in eligible:
                    if time.value in used:
                        continue
                    end = int(np.floor((time.value / 1e9 - epoch) * fs))
                    segment = values[end - 512:end]
                    if len(segment) != 512 or not np.isfinite(segment).all() or segment.std() < 1e-8:
                        failed += 1
                        used.add(time.value)
                        continue
                    windows.append(segment)
                    ends.append(time.value)
                    used.add(time.value)
                if windows:
                    vectors.append(encode_segments(encoder, windows, batch_size=32))
                    times.extend(ends)
        if not vectors:
            raise ValueError('No valid PPG for a required subject')
        order = np.argsort(times)
        np.savez_compressed(dest, embedding=np.concatenate(vectors)[order],
                            decision_ns=np.asarray(times, dtype=np.int64)[order])
        result = {'subject': subject, 'anchors': len(anchors), 'embedded': len(times),
                  'invalid_windows': failed, 'missing_source': len(anchors) - len(used),
                  'source_hashes': fingerprint, 'embedding_sha256': file_sha256(dest),
                  'clock_shift_hours': offsets[subject], 'labels_read': False, 'test_subjects_read': False}
        marker.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
