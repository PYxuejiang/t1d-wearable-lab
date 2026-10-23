"""Offline pretraining/LoRA runner for audited, pre-split local arrays.

No raw-source adapter, test-set scoring, alarm tuning or production inference.
See docs/TRANSFORMER_LORA.zh-CN.md for the frozen manifest contract.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
import torch
from torch.nn import functional as F
from t1d_lab.finetune_protocol import validate_subject_split, fit_normalization, apply_normalization
from t1d_lab.wearable_transformer import (
    ModelConfig, WearableTransformer, attach_lora, sha256, save_base, load_base, save_adapter,
)


def load_partition(path, subjects, config, labeled):
    with np.load(path, allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    required = {'values', 'observed', 'elapsed', 'context', 'context_observed', 'subject', 'cutoff', 'available_at', 'context_available_at'}
    if labeled:
        required.add('label')
    if not required <= data.keys():
        raise ValueError(f'Missing arrays: {required - data.keys()}')
    n = len(data['values'])
    if n < 1 or data['values'].ndim != 3 or data['values'].shape[2] != config.channels or not 1 <= data['values'].shape[1] <= config.max_steps:
        raise ValueError('Invalid sequence shape')
    t = data['values'].shape[1]
    shapes = {'observed': data['values'].shape, 'elapsed': (n, t, 1), 'context': (n, config.context_features),
              'context_observed': (n, config.context_features), 'subject': (n,), 'cutoff': (n,),
              'available_at': (n, t), 'context_available_at': (n,)}
    if any(data[key].shape != shape for key, shape in shapes.items()):
        raise ValueError('Shape mismatch in dataset contract')
    if set(map(str, data['subject'])) != set(map(str, subjects)):
        raise ValueError('Array subjects differ from frozen manifest')
    for key in ('cutoff', 'available_at', 'context_available_at'):
        if not np.issubdtype(data[key].dtype, np.number) or not np.isfinite(data[key]).all():
            raise ValueError('Availability timestamps must be finite UTC epoch seconds')
    if (data['available_at'] > data['cutoff'][:, None]).any() or (data['context_available_at'] > data['cutoff']).any():
        raise ValueError('Future input leakage')
    if data['observed'].dtype != bool or data['context_observed'].dtype != bool:
        raise ValueError('Masks must be boolean')
    if not data['observed'].reshape(n, -1).any(1).all():
        raise ValueError('All-missing windows require explicit abstention accounting')
    if labeled and (data['label'].shape != (n,) or not np.isin(data['label'], [0, 1]).all() or len(np.unique(data['label'])) != 2):
        raise ValueError('This runner requires both binary classes in each fitting/selection partition')
    return data


def tensors(data, stats):
    values = apply_normalization(data['values'], data['observed'], stats)
    return (torch.tensor(values), torch.tensor(data['observed']), torch.tensor(data['elapsed'], dtype=torch.float32),
            torch.tensor(data['context'], dtype=torch.float32), torch.tensor(data['context_observed']))


def run(manifest_path, stage, output):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('data_kind') not in ('synthetic', 'real') or manifest.get('scope') != 'offline-research-only':
        raise ValueError('Explicit data kind and offline scope required')
    if manifest.get('protein_measurements') is not False or manifest.get('training_authorized') is not True:
        raise ValueError('Authorized wearable/context inputs only; no pseudo-protein branch')
    for key in ('protocol_id', 'feature_schema', 'label_definition', 'context_encoding', 'data_authorization'):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise ValueError(f'Missing auditable {key}')
    splits = manifest['subjects']
    validate_subject_split(splits['train'], splits['validation'], splits['test'])
    config = ModelConfig(**manifest['model'])
    train_path = (manifest_path.parent / manifest['train_file']).resolve()
    validation_path = (manifest_path.parent / manifest['validation_file']).resolve()
    if train_path == validation_path:
        raise ValueError('Training and validation files must differ')
    train = load_partition(train_path, splits['train'], config, stage == 'finetune')
    validation = load_partition(validation_path, splits['validation'], config, stage == 'finetune')
    torch.manual_seed(2301); torch.set_num_threads(2)
    provenance = {'data_kind': manifest['data_kind'], 'training_subjects': list(map(str, splits['train'])),
                  'feature_schema': manifest['feature_schema'], 'manifest_sha256': sha256(manifest_path),
                  'train_sha256': sha256(train_path), 'validation_sha256': sha256(validation_path),
                  'protocol_id': manifest['protocol_id'], 'context_encoding': manifest['context_encoding']}
    if stage == 'pretrain':
        stats = fit_normalization(train['values'], train['observed'])
        model = WearableTransformer(config)
        provenance.update(objective='masked-reconstruction', normalization=stats)
    else:
        base_path = (manifest_path.parent / manifest['base_checkpoint']).resolve()
        model, base_provenance = load_base(base_path, manifest['base_sha256'])
        for key in ('data_kind', 'training_subjects', 'feature_schema', 'train_sha256', 'validation_sha256', 'context_encoding', 'protocol_id'):
            if base_provenance.get(key) != provenance[key]:
                raise ValueError(f'Base/fine-tuning provenance mismatch: {key}')
        if model.config != config or base_provenance.get('objective') != 'masked-reconstruction':
            raise ValueError('Incompatible base checkpoint')
        stats = base_provenance['normalization']
        attach_lora(model, rank=4, alpha=8)
        provenance.update(objective='binary-classification', normalization=stats, label_definition=manifest['label_definition'])
    train_inputs, val_inputs = tensors(train, stats), tensors(validation, stats)
    # Catch malformed context/time values before writing artifacts.
    with torch.no_grad():
        model(*tuple(x[:1] for x in train_inputs)); model(*val_inputs)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new output directory; never overwrite an experiment')
    output.mkdir(parents=True, exist_ok=True)
    optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=.001)
    best, ledger = float('inf'), []
    val_held = (torch.rand_like(val_inputs[0]) < .2) & val_inputs[1]
    # Retain at least one visible sample per window and do not score an empty mask.
    val_held[:, 0, :] = False
    if stage == 'pretrain' and (not val_held.any() or not (val_inputs[1] & ~val_held).flatten(1).any(1).all()):
        raise ValueError('Insufficient observed validation support for reconstruction')
    for epoch in range(1, 41):
        model.train()
        for indices in torch.randperm(len(train_inputs[0])).split(32):
            batch = tuple(x[indices] for x in train_inputs)
            optimizer.zero_grad()
            if stage == 'pretrain':
                held = (torch.rand_like(batch[0]) < .2) & batch[1]
                held[:, 0, :] = False
                if not held.any() or not (batch[1] & ~held).flatten(1).any(1).all():
                    raise ValueError('Insufficient observed training support; audit sparse windows')
                loss = F.mse_loss(model.reconstruct(batch[0], batch[1] & ~held, *batch[2:])[held], batch[0][held])
            else:
                loss = F.binary_cross_entropy_with_logits(model(*batch), torch.tensor(train['label'][indices.numpy()], dtype=torch.float32))
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite training loss')
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); optimizer.step()
        model.eval()
        with torch.no_grad():
            if stage == 'pretrain':
                prediction = model.reconstruct(val_inputs[0], val_inputs[1] & ~val_held, *val_inputs[2:])
                score = F.mse_loss(prediction[val_held], val_inputs[0][val_held]).item()
            else:
                score = F.binary_cross_entropy_with_logits(model(*val_inputs), torch.tensor(validation['label'], dtype=torch.float32)).item()
        if not np.isfinite(score):
            raise ValueError('Nonfinite validation loss')
        ledger.append({'epoch': epoch, 'validation_loss': score})
        (output / 'training.json').write_text(json.dumps({'status': 'running', 'stage': stage,
            'data_kind': manifest['data_kind'], 'test_opened': False, 'validation_ledger': ledger}, indent=2) + '\n', encoding='utf-8')
        if score < best:
            best = score
            selected = {**provenance, 'steps': epoch, 'steps_unit': 'epochs', 'selection': 'validation-loss'}
            if stage == 'pretrain':
                save_base(model, output / 'base.pt', selected)
            else:
                save_adapter(model, output / 'adapter.pt', manifest['base_sha256'], selected)
    result = {'status': 'completed', 'stage': stage, 'data_kind': manifest['data_kind'], 'test_opened': False,
              'clinical_acceptance': 'not-evaluated', 'validation_ledger': ledger,
              'checkpoint_sha256': sha256(output / ('base.pt' if stage == 'pretrain' else 'adapter.pt'))}
    (output / 'training.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--stage', choices=['pretrain', 'finetune'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.manifest.resolve(), args.stage, args.output.resolve())
