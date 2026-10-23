"""Finite/deterministic real-waveform transfer pilot, never disease scoring."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import loadmat
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.pretrained_ppg import load_encoder, encode_segments, file_sha256
from t1d_lab.wearable_transformer import ModelConfig, WearableTransformer, attach_lora


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.manual_seed(20261023)
    checkpoint = ROOT / 'outputs/multimodal_source_v1/pulseppg_checkpoint.pt'
    expected = '485ade5033b3baa9b82e252fc131042dda897d7bdfc0d1a030d9746a1e98857c'
    encoder = load_encoder(ROOT / 'outputs/pulseppg_source/pulseppg/nets/ResNet1D/ResNet1D_Net.py', checkpoint, expected)
    audit = json.loads((ROOT / 'docs/acceptance/PPG_DALIA_AUDIT1.json').read_text())
    segments, groups, activity = [], [], []
    for entry in audit['files']:
        path = ROOT / 'data/ppg_dalia_mat' / entry['file']
        if file_sha256(path) != entry['sha256']:
            raise ValueError('Source MAT hash mismatch')
        for raw in loadmat(path, simplify_cells=True)['data']:
            name = str(raw['fix']['subj_name'])
            if name not in ['S1', 'S2', 'S3', 'S4', 'S5']:
                continue
            if raw['ppg']['fs'] != 64:
                raise ValueError('Unexpected source rate')
            ppg = np.asarray(raw['ppg']['v'], float)
            for start in range(0, 120, 8):
                segments.append(ppg[start * 64:(start + 8) * 64])
                groups.append(name)
                activity.append(entry['activity'])
    start = time.perf_counter()
    embeddings = encode_segments(encoder, segments)
    duration = time.perf_counter() - start
    single = encode_segments(encoder, segments[:8], batch_size=1)
    repeated = encode_segments(encoder, segments[:8])
    np.testing.assert_allclose(embeddings[:8], single, rtol=1e-4, atol=1e-5)
    np.testing.assert_array_equal(embeddings[:8], repeated)
    # Show the tensor bridge works; this random temporal head has NOT been pretrained.
    temporal = WearableTransformer(ModelConfig(channels=512, max_steps=15))
    values = torch.from_numpy(embeddings.reshape(10, 15, 512))
    mask = torch.ones_like(values, dtype=torch.bool)
    elapsed = torch.arange(15).float()[None, :, None].expand(10, -1, -1) / 15
    context = torch.zeros(10, 3)
    context_mask = torch.zeros_like(context, dtype=torch.bool)
    inputs = values, mask, elapsed, context, context_mask
    before = temporal(*inputs).detach()
    adapters = attach_lora(temporal)
    after = temporal(*inputs).detach()
    torch.testing.assert_close(before, after, rtol=0, atol=0)
    np.savez_compressed(args.output / 'private_embeddings.npz', embeddings=embeddings,
                        subject=np.array(groups), activity=np.array(activity))
    result = {
        'protocol_id': 'PPG_TRANSFER1_ENGINEERING', 'data_kind': 'real',
        'source': 'PPG-DaLiA development S1-S5, sitting and walking',
        'subjects': 5, 'records': 10, 'windows': len(segments), 'window_seconds': 8,
        'embedding_width': embeddings.shape[1], 'finite_fraction': float(np.isfinite(embeddings).mean()),
        'batch_single_max_abs_difference': float(np.max(np.abs(embeddings[:8] - single))),
        'repeat_max_abs_difference': float(np.max(np.abs(embeddings[:8] - repeated))),
        'encoder_seconds': duration, 'seconds_per_window': duration / len(segments),
        'checkpoint_sha256': expected, 'upstream_commit': '716eaf9cf966e8f76436f2263872ef38b1f90166',
        'encoder_frozen': all(not p.requires_grad for p in encoder.parameters()),
        'temporal_lora_trainable_parameters': sum(adapters.values()),
        'temporal_adapter_initial_delta': float((after - before).abs().max()),
        'temporal_training_completed': False, 'background_measured': False,
        'clinical_validation': False,
        'limitations': ['Real pretrained CNN, but newly initialized temporal Transformer.',
                        'Source model used PPG-DaLiA in downstream evaluation; this pilot is not independent validation.',
                        'No patient background was invented; all context masks missing.',
                        'Bounded-window preprocessing differs from author whole-record preprocessing.',
                        'No heart-rate, glucose, disease or activity accuracy measured.'],
        'protocol_sha256': file_sha256(ROOT / 'configs/ppg_transfer_v1.json'),
    }
    (args.output / 'aggregate.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
