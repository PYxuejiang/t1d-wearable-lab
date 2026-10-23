import numpy as np
import pytest

torch = pytest.importorskip('torch')
from t1d_lab.wearable_transformer import (
    ModelConfig, WearableTransformer, attach_lora, save_base, load_base, save_adapter, restore_adapter,
)
from t1d_lab.finetune_protocol import validate_subject_split, fit_normalization, apply_normalization


def batch():
    torch.manual_seed(8)
    x = torch.randn(3, 8, 2)
    observed = torch.ones_like(x, dtype=torch.bool)
    elapsed = torch.arange(8).float()[None, :, None].expand(3, -1, -1)
    context = torch.randn(3, 3)
    return x, observed, elapsed, context, torch.ones_like(context, dtype=torch.bool)


def model():
    return WearableTransformer(ModelConfig(channels=2, width=8, heads=2, layers=1, max_steps=10))


def test_missing_values_cannot_affect_predictions():
    m = model(); x, mask, t, ctx, cm = batch()
    mask[:, 2, :] = False; cm[:, 1] = False
    a = m(x, mask, t, ctx, cm)
    x[:, 2, :] = float('nan'); ctx[:, 1] = float('nan')
    torch.testing.assert_close(a, m(x, mask, t, ctx, cm), rtol=0, atol=0)


def test_empty_signals_and_invalid_times_abstain():
    m = model(); x, mask, t, ctx, cm = batch()
    with pytest.raises(ValueError, match='No observed'):
        m(x, mask & False, t, ctx, cm)
    with pytest.raises(ValueError, match='ordered'):
        m(x, mask, -t, ctx, cm)
    x[0, 0, 0] = float('nan')
    with pytest.raises(ValueError, match='finite'):
        m(x, mask, t, ctx, cm)


def test_lora_updates_without_mutating_frozen_weights(tmp_path):
    m = model(); data = batch()
    # Unit fixture only; actual training provenance exercised by the smoke runner.
    provenance = {'data_kind': 'synthetic', 'objective': 'unit-fixture', 'training_subjects': ['fixture'], 'steps': 1, 'feature_schema': 'test'}
    base_path = tmp_path / 'base.pt'
    base_sha = save_base(m, base_path, provenance)
    original = m(*data).detach()
    trainable = attach_lora(m, rank=2)
    assert any('.q.a' in name for name in trainable)
    torch.testing.assert_close(original, m(*data), rtol=0, atol=0)
    frozen = {name: p.detach().clone() for name, p in m.named_parameters() if not p.requires_grad}
    optimizer = torch.optim.SGD([p for p in m.parameters() if p.requires_grad], lr=.1)
    optimizer.zero_grad(); m(*data).square().mean().backward(); optimizer.step()
    assert all(torch.equal(frozen[name], p) for name, p in m.named_parameters() if name in frozen)
    assert any(p.abs().sum() > 0 for name, p in m.named_parameters() if name.endswith('.b'))
    adapter_path = tmp_path / 'adapter.pt'
    save_adapter(m, adapter_path, base_sha, {'data_kind': 'synthetic'})
    reloaded, _ = restore_adapter(base_path, adapter_path)
    torch.testing.assert_close(m(*data), reloaded(*data), rtol=0, atol=0)
    with pytest.raises(ValueError, match='already'):
        attach_lora(m)
    with pytest.raises(ValueError, match='hash'):
        load_base(base_path, '0' * 64)
    bundle = torch.load(adapter_path, weights_only=True)
    bundle['state']['unapproved_weight'] = torch.zeros(1)
    torch.save(bundle, adapter_path)
    with pytest.raises(ValueError, match='unexpected'):
        restore_adapter(base_path, adapter_path)


def test_random_checkpoint_requires_provenance(tmp_path):
    with pytest.raises(ValueError, match='provenance'):
        save_base(model(), tmp_path / 'base.pt', {})


def test_subject_splits_and_training_only_normalization():
    validate_subject_split(['a'], ['b'], ['c'])
    with pytest.raises(ValueError, match='leakage'):
        validate_subject_split(['a'], ['a'], ['c'])
    train = np.array([[[1., 2.], [3., np.nan]]])
    observed = np.isfinite(train)
    stats = fit_normalization(train, observed)
    assert stats['mean'] == [2., 2.]
    test = np.array([[[100., np.nan]]])
    transformed = apply_normalization(test, np.isfinite(test), stats)
    assert transformed[0, 0, 0] == 98
    assert transformed[0, 0, 1] == 0
    assert stats['mean'] == [2., 2.]


def test_context_changes_can_reach_output():
    m = model(); x, mask, t, ctx, cm = batch()
    assert not torch.equal(m(x, mask, t, ctx, cm), m(x, mask, t, ctx + 5, cm))


def runner():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('train_wearable_lora', Path(__file__).resolve().parents[1] / 'scripts/train_wearable_lora.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audited_runner_pretrains_finetunes_and_rejects_leakage(tmp_path):
    import json
    run = runner()
    def write_partition(path, group):
        x, mask, elapsed, context, context_mask = batch()
        # Distinct subjects per partition; both binary classes represented.
        np.savez(path, values=x.numpy(), observed=mask.numpy(), elapsed=elapsed.numpy(),
                 context=context.numpy(), context_observed=context_mask.numpy(),
                 subject=np.array([group] * 3), cutoff=np.ones(3) * 100,
                 available_at=np.ones((3, 8)) * 90, context_available_at=np.ones(3) * 80,
                 label=np.array([0, 1, 0]))
    write_partition(tmp_path / 'train.npz', 'train-person')
    write_partition(tmp_path / 'validation.npz', 'validation-person')
    manifest = {'scope': 'offline-research-only', 'data_kind': 'synthetic', 'protein_measurements': False,
                'training_authorized': True, 'data_authorization': 'synthetic unit fixture',
                'protocol_id': 'unit-only-v1', 'feature_schema': 'two-channel-fixture',
                'label_definition': 'arbitrary synthetic binary labels', 'context_encoding': 'three synthetic scalars',
                'subjects': {'train': ['train-person'], 'validation': ['validation-person'], 'test': ['never-read']},
                'model': {'channels': 2, 'width': 8, 'heads': 2, 'layers': 1, 'max_steps': 10},
                'train_file': 'train.npz', 'validation_file': 'validation.npz'}
    path = tmp_path / 'manifest.json'; path.write_text(json.dumps(manifest))
    pretrain = run.run(path, 'pretrain', tmp_path / 'pretrain')
    assert pretrain['test_opened'] is False
    assert len(pretrain['validation_ledger']) == 40
    manifest.update(base_checkpoint='pretrain/base.pt', base_sha256=pretrain['checkpoint_sha256'])
    path.write_text(json.dumps(manifest))
    result = run.run(path, 'finetune', tmp_path / 'finetune')
    assert result['clinical_acceptance'] == 'not-evaluated'
    restored, _ = restore_adapter(tmp_path / 'pretrain/base.pt', tmp_path / 'finetune/adapter.pt')
    assert restored.config.channels == 2
    manifest['subjects']['validation'] = ['train-person']
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='leakage'):
        run.run(path, 'finetune', tmp_path / 'must-not-exist')
    assert not (tmp_path / 'must-not-exist').exists()


def test_array_loader_rejects_future_information(tmp_path):
    run = runner(); x, mask, t, ctx, cm = batch()
    path = tmp_path / 'future.npz'
    np.savez(path, values=x.numpy(), observed=mask.numpy(), elapsed=t.numpy(), context=ctx.numpy(),
             context_observed=cm.numpy(), subject=np.array(['a'] * 3), cutoff=np.ones(3),
             available_at=np.ones((3, 8)) * 2, context_available_at=np.ones(3), label=np.array([0, 1, 0]))
    with pytest.raises(ValueError, match='Future'):
        run.load_partition(path, ['a'], model().config, True)
