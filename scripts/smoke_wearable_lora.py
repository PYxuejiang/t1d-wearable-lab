"""CPU synthetic wiring acceptance. Never reports patient performance.

Run from repo root with an environment containing torch and project src installed.
The base is actually pretrained (masked reconstruction); it is NOT a foundation
model or an externally pretrained checkpoint. All artifacts stay under outputs/.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import torch
from torch.nn import functional as F
from t1d_lab.wearable_transformer import (
    ModelConfig, WearableTransformer, attach_lora, save_base, load_base,
    save_adapter, restore_adapter,
)
from t1d_lab.finetune_protocol import validate_subject_split


def synthetic_batch(n, seed):
    generator = torch.Generator().manual_seed(seed)
    time = torch.linspace(0, 1, 24)[None, :, None].expand(n, -1, -1)
    phase = torch.rand(n, 1, 6, generator=generator) * 6.28
    values = torch.sin(time * 6.28 + phase) + torch.randn(n, 24, 6, generator=generator) * .04
    observed = torch.rand(n, 24, 6, generator=generator) > .1
    context = F.one_hot(torch.randint(0, 3, (n,), generator=generator), 3).float()
    # Artificial task ONLY: waveform and context determine a synthetic binary target.
    label = ((values[:, -6:, 0].mean(1) + context[:, 0] * .5) > .15).float()
    return (values, observed, time, context, torch.ones_like(context, dtype=torch.bool)), label


def run(output):
    torch.manual_seed(2301)
    torch.set_num_threads(2)
    output.mkdir(parents=True, exist_ok=True)
    validate_subject_split(range(48), range(48, 64), range(64, 80))
    inputs, labels = synthetic_batch(48, 1)
    validation, validation_labels = synthetic_batch(16, 2)
    model = WearableTransformer(ModelConfig())
    optimizer = torch.optim.Adam(model.parameters(), lr=.003)
    held = (torch.rand_like(inputs[0]) < .2) & inputs[1]
    masked = (inputs[0], inputs[1] & ~held, *inputs[2:])
    with torch.no_grad():
        pre_initial = F.mse_loss(model.reconstruct(*masked)[held], inputs[0][held]).item()
    for _ in range(60):
        optimizer.zero_grad()
        loss = F.mse_loss(model.reconstruct(*masked)[held], inputs[0][held])
        loss.backward(); optimizer.step()
    pre_final = F.mse_loss(model.reconstruct(*masked)[held], inputs[0][held]).item()
    provenance = {'data_kind': 'synthetic', 'objective': 'masked-reconstruction',
                  'training_subjects': [f'synthetic-{i}' for i in range(48)], 'steps': 60,
                  'feature_schema': 'synthetic-six-channel-v1'}
    base_path = output / 'base.pt'
    base_sha = save_base(model, base_path, provenance)
    base, _ = load_base(base_path, base_sha)
    with torch.no_grad():
        before = base(*validation).clone()
    trainable = attach_lora(base)
    with torch.no_grad():
        initial_delta = (base(*validation) - before).abs().max().item()
    frozen = {name: p.detach().clone() for name, p in base.named_parameters() if not p.requires_grad}
    optimizer = torch.optim.Adam([p for p in base.parameters() if p.requires_grad], lr=.01)
    best, best_step = float('inf'), 0
    for step in range(1, 81):
        optimizer.zero_grad()
        loss = F.binary_cross_entropy_with_logits(base(*inputs), labels)
        loss.backward(); optimizer.step()
        with torch.no_grad():
            score = F.binary_cross_entropy_with_logits(base(*validation), validation_labels).item()
        if score < best:
            best, best_step = score, step
            save_adapter(base, output / 'adapter.pt', base_sha,
                         {'data_kind': 'synthetic', 'selection': 'validation-bce', 'step': step})
    frozen_unchanged = all(torch.equal(p, frozen[name]) for name, p in base.named_parameters() if name in frozen)
    trained = any(p.detach().abs().sum().item() > 0 for name, p in base.named_parameters() if name.endswith('.b'))
    # Verify final state roundtrip separately from the validation-selected artifact.
    save_adapter(base, output / 'roundtrip.pt', base_sha, {'data_kind': 'synthetic', 'step': 80})
    restored, _ = restore_adapter(base_path, output / 'roundtrip.pt')
    with torch.no_grad():
        roundtrip_error = (base(*validation) - restored(*validation)).abs().max().item()
    summary = {
        'scope': 'synthetic-engineering-only', 'clinical_performance_evaluated': False,
        'real_paired_protein_data_used': False, 'qlora_used': False, 'seed': 2301,
        'pretraining_steps': 60, 'finetuning_steps': 80, 'validation_selected_step': best_step,
        'synthetic_pretraining_loss_initial': pre_initial, 'synthetic_pretraining_loss_final': pre_final,
        'parameters_total': sum(p.numel() for p in base.parameters()), 'parameters_trainable': sum(trainable.values()),
        'trainable_scope': ['Q/V LoRA', 'context projection', 'classification head'],
        'initial_adapter_output_max_delta': initial_delta, 'frozen_parameters_unchanged': frozen_unchanged,
        'adapters_updated': trained, 'restore_output_max_error': roundtrip_error, 'base_sha256': base_sha,
        'passed': initial_delta == 0 and frozen_unchanged and trained and roundtrip_error == 0 and pre_final < pre_initial,
    }
    (output / 'acceptance.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    if not summary['passed']:
        raise RuntimeError('Engineering acceptance failed')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs' / 'wearable_lora_smoke_v1')
    run(parser.parse_args().output)
