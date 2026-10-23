"""Checks used before either supervised fitting or unsupervised pretraining."""
import numpy as np


def validate_subject_split(train, validation, test):
    groups = [set(map(str, group)) for group in (train, validation, test)]
    if any(not group or '' in group for group in groups):
        raise ValueError('All three subject partitions must be nonempty')
    if any(groups[i] & groups[j] for i, j in ((0, 1), (0, 2), (1, 2))):
        raise ValueError('Subject leakage across partitions')


def fit_normalization(values, observed):
    """Call on training subjects only. Preserve missing channels as missing."""
    values, observed = np.asarray(values), np.asarray(observed)
    if values.ndim != 3 or observed.shape != values.shape or observed.dtype != bool:
        raise ValueError('Expected [window, time, channel] and boolean mask')
    if not np.isfinite(values[observed]).all():
        raise ValueError('Observed training values must be finite')
    count = observed.sum(axis=(0, 1))
    if (count == 0).any():
        raise ValueError('Unobserved training channel needs an explicit schema change')
    mean = np.where(observed, values, 0).sum(axis=(0, 1)) / count
    variance = np.where(observed, (values - mean) ** 2, 0).sum(axis=(0, 1)) / count
    return {'mean': mean.tolist(), 'scale': np.maximum(np.sqrt(variance), 1e-6).tolist()}


def apply_normalization(values, observed, statistics):
    mean, scale = np.asarray(statistics['mean']), np.asarray(statistics['scale'])
    if mean.shape != (values.shape[-1],) or scale.shape != mean.shape or not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale <= 0).any():
        raise ValueError('Invalid frozen normalization')
    return np.where(observed, (values - mean) / scale, 0).astype(np.float32)
