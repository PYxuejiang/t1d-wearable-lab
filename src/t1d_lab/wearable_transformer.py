"""Offline research Transformer. No clinical inference or protein pseudo-features.

LoRA is implemented directly over Q/V Linear modules; this is not QLoRA.
All sequence samples must be available by the prediction cutoff. Attention is
bidirectional within that historical window, never across future observations.
"""
from dataclasses import asdict, dataclass
import hashlib
import math

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class ModelConfig:
    channels: int = 6
    context_features: int = 3
    width: int = 32
    heads: int = 4
    layers: int = 2
    max_steps: int = 64


class Attention(nn.Module):
    def __init__(self, width, heads):
        super().__init__()
        self.heads = heads
        self.q = nn.Linear(width, width)
        self.k = nn.Linear(width, width)
        self.v = nn.Linear(width, width)
        self.out = nn.Linear(width, width)

    def forward(self, x, valid):
        b, n, d = x.shape
        q, k, v = [layer(x).reshape(b, n, self.heads, d // self.heads)
                   .transpose(1, 2) for layer in (self.q, self.k, self.v)]
        scores = (q @ k.transpose(-1, -2)) / math.sqrt(d // self.heads)
        scores = scores.masked_fill(~valid[:, None, None, :], float('-inf'))
        y = (scores.softmax(-1) @ v).transpose(1, 2).reshape(b, n, d)
        return self.out(y)


class Block(nn.Module):
    def __init__(self, width, heads):
        super().__init__()
        self.norm1, self.norm2 = nn.LayerNorm(width), nn.LayerNorm(width)
        self.attention = Attention(width, heads)
        self.ff = nn.Sequential(nn.Linear(width, width * 2), nn.GELU(), nn.Linear(width * 2, width))

    def forward(self, x, valid):
        x = x + self.attention(self.norm1(x), valid)
        return x + self.ff(self.norm2(x))


class WearableTransformer(nn.Module):
    def __init__(self, config=ModelConfig()):
        super().__init__()
        if min(config.channels, config.context_features, config.layers, config.max_steps, config.heads, config.width) < 1 or config.width % config.heads:
            raise ValueError('Invalid Transformer dimensions')
        self.config = config
        self.signal = nn.Linear(config.channels * 2 + 1, config.width)
        self.context = nn.Linear(config.context_features * 2, config.width)
        self.position = nn.Parameter(torch.zeros(1, config.max_steps + 1, config.width))
        nn.init.normal_(self.position, std=0.02)
        self.blocks = nn.ModuleList([Block(config.width, config.heads) for _ in range(config.layers)])
        self.norm = nn.LayerNorm(config.width)
        self.reconstruction = nn.Linear(config.width, config.channels)
        self.head = nn.Linear(config.width, 1)

    def encode(self, values, observed, elapsed, context, context_observed):
        if values.ndim != 3 or values.shape[2] != self.config.channels or not 1 <= values.shape[1] <= self.config.max_steps:
            raise ValueError('Invalid sequence shape')
        b, t, _ = values.shape
        if observed.shape != values.shape or elapsed.shape != (b, t, 1) or context.shape != (b, self.config.context_features) or context_observed.shape != context.shape:
            raise ValueError('Mask/time/context shape mismatch')
        if observed.dtype != torch.bool or context_observed.dtype != torch.bool:
            raise ValueError('Observation masks must be boolean')
        if not torch.isfinite(values[observed]).all() or not torch.isfinite(context[context_observed]).all() or not torch.isfinite(elapsed).all():
            raise ValueError('Observed values must be finite')
        if (elapsed < 0).any() or (elapsed[:, 1:] < elapsed[:, :-1]).any():
            raise ValueError('Elapsed times must be nonnegative and ordered')
        if not observed.flatten(1).any(1).all():
            raise ValueError('No observed signal: abstain instead of context-only prediction')
        clean = torch.where(observed, values, 0)
        ctx = torch.where(context_observed, context, 0)
        x = self.signal(torch.cat([clean, observed.to(values.dtype), elapsed], -1))
        context_token = self.context(torch.cat([ctx, context_observed.to(values.dtype)], -1))[:, None]
        x = torch.cat([context_token, x], 1) + self.position[:, :t + 1]
        # Always-valid context token prevents all-masked attention, including absent context.
        valid = torch.cat([torch.ones(b, 1, dtype=torch.bool, device=values.device), observed.any(-1)], 1)
        for block in self.blocks:
            x = block(x, valid)
        return self.norm(x), valid

    def forward(self, values, observed, elapsed, context, context_observed):
        x, _ = self.encode(values, observed, elapsed, context, context_observed)
        return self.head(x[:, 0]).squeeze(-1)

    def reconstruct(self, *inputs):
        x, _ = self.encode(*inputs)
        return self.reconstruction(x[:, 1:])


class LoRALinear(nn.Module):
    def __init__(self, base, rank=4, alpha=8):
        super().__init__()
        if not isinstance(base, nn.Linear) or not 0 < rank <= min(base.in_features, base.out_features) or not math.isfinite(alpha) or alpha <= 0:
            raise ValueError('Invalid LoRA target/rank/alpha')
        self.base = base.requires_grad_(False)
        self.a = nn.Parameter(torch.empty(rank, base.in_features, device=base.weight.device, dtype=base.weight.dtype))
        self.b = nn.Parameter(torch.zeros(base.out_features, rank, device=base.weight.device, dtype=base.weight.dtype))
        nn.init.kaiming_uniform_(self.a, a=math.sqrt(5))
        self.scale = alpha / rank

    def forward(self, x):
        return self.base(x) + F.linear(F.linear(x, self.a), self.b) * self.scale


def attach_lora(model, rank=4, alpha=8):
    """Train Q/V adapters, context projection and task head; freeze other weights."""
    if any(isinstance(m, LoRALinear) for m in model.modules()):
        raise ValueError('Adapters already attached')
    if not 0 < rank <= model.config.width or not math.isfinite(alpha) or alpha <= 0:
        raise ValueError('Invalid adapter configuration')
    model.requires_grad_(False)
    for block in model.blocks:
        block.attention.q = LoRALinear(block.attention.q, rank, alpha)
        block.attention.v = LoRALinear(block.attention.v, rank, alpha)
    model.context.requires_grad_(True)
    model.head.requires_grad_(True)
    model.adapter_config = {'rank': rank, 'alpha': alpha}
    return {name: p.numel() for name, p in model.named_parameters() if p.requires_grad}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save_base(model, path, provenance):
    if hasattr(model, 'adapter_config'):
        raise ValueError('Base checkpoint must precede adapter attachment')
    required = {'data_kind', 'objective', 'training_subjects', 'steps', 'feature_schema'}
    if not required <= provenance.keys() or provenance['steps'] < 1 or not provenance['training_subjects']:
        raise ValueError('Training provenance required; random freezing is not pretraining')
    if provenance['data_kind'] not in ('synthetic', 'real'):
        raise ValueError('Unknown training data kind')
    torch.save({'config': asdict(model.config), 'state': model.state_dict(), 'provenance': provenance}, path)
    return sha256(path)


def load_base(path, expected_sha):
    if sha256(path) != expected_sha:
        raise ValueError('Base checkpoint hash mismatch')
    bundle = torch.load(path, map_location='cpu', weights_only=True)
    model = WearableTransformer(ModelConfig(**bundle['config']))
    model.load_state_dict(bundle['state'], strict=True)
    return model, bundle['provenance']


def save_adapter(model, path, base_sha, provenance):
    if not hasattr(model, 'adapter_config') or len(base_sha) != 64:
        raise ValueError('Attached adapters and base hash required')
    state = {name: p.detach().cpu() for name, p in model.named_parameters() if p.requires_grad}
    torch.save({'config': asdict(model.config), 'adapter': model.adapter_config,
                'base_sha': base_sha, 'state': state, 'provenance': provenance}, path)


def restore_adapter(base_path, adapter_path):
    bundle = torch.load(adapter_path, map_location='cpu', weights_only=True)
    model, base_provenance = load_base(base_path, bundle['base_sha'])
    if asdict(model.config) != bundle['config']:
        raise ValueError('Architecture mismatch')
    attach_lora(model, **bundle['adapter'])
    parameters = dict(model.named_parameters())
    expected = {name for name, p in parameters.items() if p.requires_grad}
    if set(bundle['state']) != expected:
        raise ValueError('Missing or unexpected adapter weights')
    with torch.no_grad():
        for name, value in bundle['state'].items():
            if value.shape != parameters[name].shape or not torch.isfinite(value).all():
                raise ValueError('Invalid adapter tensor')
            parameters[name].copy_(value)
    return model, {'base': base_provenance, 'adapter': bundle['provenance']}
