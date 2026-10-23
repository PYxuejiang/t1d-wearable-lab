"""Reconstruct validation windows independently and reload every selected model."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.wearable_transformer import WearableTransformer, ModelConfig, attach_lora
from t1d_lab.pretrained_ppg import file_sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads((args.run / 'aggregate.json').read_text())
    cfg = report['protocol']
    base = torch.load(args.run / 'temporal_base.pt', weights_only=True, map_location='cpu')
    torch.set_num_threads(4)
    frame = pd.read_parquet(ROOT / 'outputs/improvement_v2/features.parquet',
            columns=['subject', 'decision_time', 'glucose_mg_dl'],
            filters=[('subject', 'in', cfg['subjects']['validation'])])
    windows, labels, elapsed = [], [], []
    for subject in cfg['subjects']['validation']:
        reference = frame[frame.subject == subject].set_index('decision_time').glucose_mg_dl
        with np.load(args.cache / f'{subject}.npz', allow_pickle=False) as data:
            lookup = {int(t): e for t, e in zip(data['decision_ns'], data['embedding'])}
        ordered = sorted(lookup)
        for index, stamp in enumerate(ordered):
            if index < 2:
                continue
            history = ordered[index - 2:index + 1]
            tolerance = cfg.get('history_tolerance_seconds', 0) * 1e9
            if any(abs(history[j + 1] - history[j] - 300e9) > tolerance for j in [0, 1]):
                continue
            label = reference.get(pd.Timestamp(stamp), np.nan)
            if all(t in lookup for t in history) and np.isfinite(label):
                windows.append([lookup[t] for t in history])
                labels.append(int(label < 70))
                elapsed.append([(t - history[0]) / 600e9 for t in history])
    stats = base['provenance']['normalization']
    values = torch.tensor(((np.array(windows) - np.array(stats['mean'])) /
                            np.array(stats['scale'])).astype(np.float32))
    n = len(values)
    assert n == report['validation_windows'] and sum(labels) == report['validation_positive']
    tensors = (values, torch.ones_like(values, dtype=torch.bool),
               torch.tensor(np.array(elapsed, dtype=np.float32)[:, :, None]),
               torch.zeros(n, 3), torch.zeros(n, 3, dtype=torch.bool))
    verified, maximum_error = [], 0.
    for row in report['candidates']:
        kind = row['kind']
        current = nn.Linear(512, 1) if kind == 'linear' else WearableTransformer(ModelConfig(**base['config']))
        if kind == 'lora':
            attach_lora(current, rank=row['rank'], alpha=row['alpha'])
        checkpoint = args.run / f"candidate_{row['candidate']}.pt"
        current.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cpu'), strict=True)
        current.eval()
        if kind == 'lora':
            for name, param in current.named_parameters():
                if not param.requires_grad:
                    key = name.replace('.base.', '.')
                    if not torch.equal(param, base['state'][key]):
                        raise ValueError(f'Frozen temporal base changed: {name}')
        with torch.no_grad():
            logits = current(values.mean(1)).squeeze(-1) if kind == 'linear' else current(*tensors)
            probability = torch.sigmoid(logits).numpy()
        metrics = {'AP': average_precision_score(labels, probability),
                   'AUC': roc_auc_score(labels, probability), 'Brier': brier_score_loss(labels, probability)}
        error = max(abs(metrics[k] - row['selected'][k]) for k in metrics)
        if error > 1e-7:
            raise ValueError('Checkpoint score differs from selection ledger')
        maximum_error = max(error, maximum_error)
        expected = max(row['epochs'], key=lambda e: (e['AP'], -e['Brier']))
        if expected != row['selected']:
            raise ValueError('Epoch selection differs from protocol')
        verified.append({'candidate': row['candidate'], 'checkpoint_sha256': file_sha256(checkpoint),
                         'metrics_match': True, 'frozen_base_checked': kind == 'lora'})
    selected = max(report['candidates'], key=lambda r: (r['selected']['AP'], -r['selected']['Brier'], -r['trainable']))
    assert selected['candidate'] == report['selected_candidate']
    result = {'protocol_id': cfg['protocol_id'] + '_VERIFY', 'status': 'passed',
              'validation_windows': n, 'candidates_verified': len(verified),
              'maximum_metric_difference': maximum_error, 'test_opened': False,
              'clinical_validation': False, 'verified': verified,
              'aggregate_sha256': file_sha256(args.run / 'aggregate.json')}
    (args.run / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'verified'}, indent=2))


if __name__ == '__main__':
    main()
