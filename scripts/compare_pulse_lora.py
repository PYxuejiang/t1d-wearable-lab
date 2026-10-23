"""Locked train/validation comparison; deliberately no test scoring path."""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.wearable_transformer import ModelConfig, WearableTransformer, attach_lora, save_base
from t1d_lab.pretrained_ppg import file_sha256
from t1d_lab.finetune_protocol import fit_normalization, apply_normalization, validate_subject_split


def partition(subjects, cache, source):
    sequences, labels, people, counts = [], [], [], []
    for subject in subjects:
        path = cache / f'{subject}.npz'
        audit = json.loads((cache / f'{subject}.json').read_text())
        if file_sha256(path) != audit['embedding_sha256']:
            raise ValueError('Unverified embedding cache')
        with np.load(path, allow_pickle=False) as data:
            times, embedding = data['decision_ns'], data['embedding']
        rows = source[source.subject == subject].copy()
        if rows.decision_time.duplicated().any():
            raise ValueError('Duplicate reference anchor')
        reference = dict(zip(rows.decision_time.astype('int64'), rows.glucose_mg_dl))
        used, missing_reference, incomplete_history = 0, 0, 0
        for i, stamp in enumerate(times):
            if i < 2 or not np.all(np.diff(times[i - 2:i + 1]) == 300_000_000_000):
                incomplete_history += 1
                continue
            label = reference.get(stamp, np.nan)
            if not np.isfinite(label):
                missing_reference += 1
                continue
            sequences.append(embedding[i - 2:i + 1])
            labels.append(float(label < 70))
            people.append(subject)
            used += 1
        counts.append({'reference_anchors': len(rows), 'embedded': len(times), 'usable_history': used,
                       'missing_reference': missing_reference, 'incomplete_history': incomplete_history})
    x, y = np.stack(sequences), np.array(labels, dtype=np.float32)
    if len(np.unique(y)) != 2:
        raise ValueError('Both classes required; do not silently change participants')
    return x, y, counts, people


def inputs(values, stats):
    observed = np.ones_like(values, dtype=bool)
    x = torch.tensor(apply_normalization(values, observed, stats))
    n = len(x)
    return (x, torch.ones_like(x, dtype=torch.bool),
            torch.tensor([0., .5, 1.])[None, :, None].expand(n, -1, -1),
            torch.zeros(n, 3), torch.zeros(n, 3, dtype=torch.bool))


def scores(y, probability):
    return {'AP': float(average_precision_score(y, probability)),
            'AUC': float(roc_auc_score(y, probability)), 'Brier': float(brier_score_loss(y, probability))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a fresh output directory')
    cfg_path = ROOT / 'configs/pulse_temporal_fit_v1.json'
    cfg = json.loads(cfg_path.read_text())
    split = cfg['subjects']
    validate_subject_split(split['train'], split['validation'], split['test'])
    source_path = ROOT / 'outputs/improvement_v2/features.parquet'
    source_sha = file_sha256(source_path)
    for subject in split['train'] + split['validation']:
        cache_meta = json.loads((args.cache / f'{subject}.json').read_text())
        if cache_meta['source_hashes']['configs/pulse_temporal_fit_v1.json'] != file_sha256(cfg_path) or cache_meta['source_hashes']['anchor_source'] != source_sha:
            raise ValueError('Embedding/source/protocol mismatch')
    # Projection and predicate prevent loading held-out labels into this study.
    source = pd.read_parquet(source_path,
            columns=['subject', 'decision_time', 'glucose_mg_dl'],
            filters=[('subject', 'in', split['train'] + split['validation'])])
    train, y, train_counts, _ = partition(split['train'], args.cache, source)
    validation, vy, validation_counts, _ = partition(split['validation'], args.cache, source)
    stats = fit_normalization(train, np.ones_like(train, dtype=bool))
    tx, vx = inputs(train, stats), inputs(validation, stats)
    labels = torch.from_numpy(y)
    torch.set_num_threads(4)
    torch.manual_seed(cfg['seed'])
    model = WearableTransformer(ModelConfig(channels=512, max_steps=3))
    args.output.mkdir(parents=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    held = torch.rand_like(vx[0]) < .2
    held[:, 0, :] = False
    best = float('inf')
    pretrain = []
    for epoch in range(cfg['pretrain_epochs']):
        model.train()
        for indices in torch.randperm(len(y)).split(cfg['batch_size']):
            batch = tuple(x[indices] for x in tx)
            mask = torch.rand_like(batch[0]) < .2
            mask[:, 0, :] = False
            optimizer.zero_grad()
            loss = F.mse_loss(model.reconstruct(batch[0], batch[1] & ~mask, *batch[2:])[mask], batch[0][mask])
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite reconstruction loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            value = F.mse_loss(model.reconstruct(vx[0], vx[1] & ~held, *vx[2:])[held], vx[0][held]).item()
        pretrain.append({'epoch': epoch + 1, 'validation_MSE': value})
        if value < best:
            best = value
            base = copy.deepcopy(model.state_dict())
            selected_epoch = epoch + 1
    model.load_state_dict(base)
    save_base(model, args.output / 'temporal_base.pt', {
        'data_kind': 'real', 'objective': 'training-subject-masked-PPG-embedding-reconstruction',
        'training_subjects': split['train'], 'steps': selected_epoch, 'feature_schema': '3x512-pinned-pulseppg',
        'normalization': stats, 'protocol_sha256': file_sha256(cfg_path),
    })
    candidates = []
    settings = [(kind, lr, None, None) for kind in ['linear', 'head', 'full'] for lr in cfg['learning_rate']]
    settings += [('lora', lr, rank, factor) for rank in cfg['lora_rank']
                 for factor in cfg['lora_alpha_over_rank'] for lr in cfg['learning_rate']]
    def infer(current, data, kind):
        return current(data[0].mean(1)).squeeze(-1) if kind == 'linear' else current(*data)
    for number, (kind, lr, rank, factor) in enumerate(settings):
        torch.manual_seed(cfg['seed'])
        current = nn.Linear(512, 1) if kind == 'linear' else WearableTransformer(model.config)
        if kind != 'linear':
            current.load_state_dict(base)
            if kind == 'head':
                current.requires_grad_(False)
                current.head.requires_grad_(True)
            elif kind == 'lora':
                attach_lora(current, rank=rank, alpha=rank * factor)
            current.reconstruction.requires_grad_(False)
        count = sum(p.numel() for p in current.parameters() if p.requires_grad)
        optimizer = torch.optim.Adam([p for p in current.parameters() if p.requires_grad], lr=lr)
        ledger, best_key, best_state = [], (-float('inf'), -float('inf')), None
        start = time.perf_counter()
        # Equal mini-batch order across all arms, independent of adapter initialization.
        generator = torch.Generator().manual_seed(cfg['seed'])
        for epoch in range(cfg['finetune_epochs']):
            current.train()
            for indices in torch.randperm(len(y), generator=generator).split(cfg['batch_size']):
                batch = tuple(x[indices] for x in tx)
                optimizer.zero_grad()
                loss = F.binary_cross_entropy_with_logits(infer(current, batch, kind), labels[indices])
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite fine-tuning loss')
                loss.backward()
                torch.nn.utils.clip_grad_norm_(current.parameters(), 1.)
                optimizer.step()
            current.eval()
            with torch.no_grad():
                probability = torch.sigmoid(infer(current, vx, kind)).numpy()
            metric = scores(vy, probability)
            ledger.append({'epoch': epoch + 1, **metric})
            key = (metric['AP'], -metric['Brier'])
            if key > best_key:
                best_key = key
                best_state = copy.deepcopy(current.state_dict())
                selected = ledger[-1]
        torch.save(best_state, args.output / f'candidate_{number}.pt')
        result = {'candidate': number, 'kind': kind, 'lr': lr, 'rank': rank,
                  'alpha': rank * factor if rank else None, 'trainable': count,
                  'seconds': time.perf_counter() - start, 'selected': selected, 'epochs': ledger}
        candidates.append(result)
        (args.output / 'candidates.json').write_text(json.dumps(candidates, indent=2))
        print(json.dumps({k: v for k, v in result.items() if k != 'epochs'}), flush=True)
    winner = max(candidates, key=lambda row: (row['selected']['AP'], -row['selected']['Brier'], -row['trainable']))
    output = {'protocol': cfg, 'protocol_sha256': file_sha256(cfg_path), 'test_opened': False,
              'runner_sha256': file_sha256(Path(__file__)), 'source_sha256': source_sha,
              'train_windows': len(y), 'validation_windows': len(vy),
              'train_positive': int(y.sum()), 'validation_positive': int(vy.sum()),
              'train_coverage': train_counts, 'validation_coverage': validation_counts,
              'validation_prevalence': float(vy.mean()),
              'constant_validation': scores(vy, np.full(len(vy), y.mean())),
              'pretrain': pretrain, 'selected_pretrain_epoch': selected_epoch,
              'selected_candidate': winner['candidate'], 'candidates': candidates,
              'clinical_validation': False, 'background_gain_evaluated': False,
              'claim': 'validation model selection only; no independent performance estimate'}
    (args.output / 'aggregate.json').write_text(json.dumps(output, indent=2))
    print('Completed validation comparison; test remains unopened', flush=True)


if __name__ == '__main__':
    main()
