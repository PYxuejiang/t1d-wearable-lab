"""Frozen, pinned Pulse-PPG encoder; a CNN feeding our temporal Transformer.

Only the reviewed upstream architecture file is imported. No upstream training
scripts, pickled datasets, optimizer checkpoints, or implicit downloads run here.
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
from scipy.signal import cheby2, filtfilt, resample_poly
import torch

ARCHITECTURE_SHA256 = '0b88a90b2a9c1a419090bbb7375a0643adba5b925db0215529b40074657b5c79'


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_segment(values, fs=64):
    """8 seconds already available at cutoff. No surrounding/future data read."""
    values = np.asarray(values, dtype=np.float64)
    if fs != 64 or values.shape != (512,) or not np.isfinite(values).all():
        raise ValueError('Expected finite 8-second, 64-Hz PPG segment')
    scale = values.std()
    if scale < 1e-8:
        raise ValueError('Flat PPG: abstain')
    normalized = (values - values.mean()) / scale
    b, a = cheby2(4, 20, [0.5, 12], btype='bandpass', fs=fs)
    filtered = filtfilt(b, a, normalized)
    return resample_poly(filtered, 25, 32).astype(np.float32)


def load_encoder(architecture_path, checkpoint_path, expected_checkpoint_sha256):
    architecture_path, checkpoint_path = Path(architecture_path), Path(checkpoint_path)
    if file_sha256(architecture_path) != ARCHITECTURE_SHA256:
        raise ValueError('Unreviewed Pulse-PPG architecture')
    if file_sha256(checkpoint_path) != expected_checkpoint_sha256:
        raise ValueError('Pulse-PPG checkpoint hash mismatch')
    spec = importlib.util.spec_from_file_location('_audited_pulseppg_resnet', architecture_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = module.Net(in_channels=1, base_filters=128, kernel_size=11,
                       stride=2, groups=1, n_block=12, finalpool='max')
    bundle = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    state = bundle['net'] if 'net' in bundle else bundle
    if not all(isinstance(v, torch.Tensor) and torch.isfinite(v).all() for v in state.values()):
        raise ValueError('Invalid encoder tensor')
    model.load_state_dict(state, strict=True)
    return model.eval().requires_grad_(False)


def encode_segments(model, segments, batch_size=8):
    if batch_size < 1 or not len(segments):
        raise ValueError('Positive batch size and nonempty segments required')
    if any(p.requires_grad for p in model.parameters()) or model.training:
        raise ValueError('Source encoder must be frozen and in evaluation mode')
    x = np.stack([prepare_segment(values) for values in segments])
    result = []
    with torch.inference_mode():
        for start in range(0, len(x), batch_size):
            result.append(model(torch.from_numpy(x[start:start + batch_size, None])).cpu().numpy())
    result = np.concatenate(result)
    if result.shape != (len(x), 512) or not np.isfinite(result).all():
        raise ValueError('Invalid Pulse-PPG representation')
    return result
