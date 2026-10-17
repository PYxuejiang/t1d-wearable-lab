"""Fixed ECG capture pilot utilities; does not change v1 physiological features."""
import numpy as np
from scipy import signal


def existing_energy_peaks(values, rate):
    """Exact peak calculation used by signals.waveform_features(kind='ecg')."""
    values = np.asarray(values, dtype=float)
    filtered = signal.sosfilt(signal.butter(3, [5, 20], btype='bandpass',
                                          fs=rate, output='sos'), values)
    width = max(1, int(.08 * rate))
    processed = signal.lfilter(np.ones(width) / width, [1], filtered ** 2)
    return signal.find_peaks(processed, distance=max(1, int(.3 * rate)),
                             prominence=max(1e-9, float(np.std(processed)) * .5))[0]


def core_peaks(peaks, length, rate, margin_seconds=2):
    peaks = np.asarray(peaks, dtype=int)
    margin = int(round(margin_seconds * rate))
    return peaks[(peaks >= margin) & (peaks < length - margin)]


def match_beats(reference, predicted, tolerance):
    """Chronological one-to-one matching; maximum count within fixed tolerance.

    Match the earliest feasible pair, then move both pointers. Timing errors refer
    to these pairs, not to a secondary timing-optimised assignment.
    """
    reference, predicted = np.asarray(reference), np.asarray(predicted)
    if np.any(np.diff(reference) <= 0) or np.any(np.diff(predicted) <= 0):
        raise ValueError('Peaks must be unique and sorted')
    i = j = 0
    pairs = []
    while i < len(reference) and j < len(predicted):
        delta = int(predicted[j] - reference[i])
        if delta < -tolerance:
            j += 1
        elif delta > tolerance:
            i += 1
        else:
            pairs.append((i, j))
            i += 1
            j += 1
    return pairs


def median_rate(peaks, rate):
    intervals = np.diff(peaks) / rate
    intervals = intervals[(intervals >= .3) & (intervals <= 2)]
    return float(60 / np.median(intervals)) if len(intervals) >= 5 else None


def beat_metrics(reference, predicted, rate, tolerance):
    pairs = match_beats(reference, predicted, tolerance)
    tp = len(pairs)
    fn, fp = len(reference) - tp, len(predicted) - tp
    errors = [abs(int(predicted[j]) - int(reference[i])) / rate * 1000 for i, j in pairs]
    return {'tp': tp, 'fn': fn, 'fp': fp,
            'sensitivity': tp / (tp + fn) if tp + fn else None,
            'ppv': tp / (tp + fp) if tp + fp else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            'matched_timing_median_ms': float(np.median(errors)) if errors else None,
            'reference_hr': median_rate(reference, rate),
            'predicted_hr': median_rate(predicted, rate)}
