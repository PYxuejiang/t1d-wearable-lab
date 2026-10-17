import numpy as np
from t1d_lab.beat_capture import core_peaks, match_beats, median_rate, existing_energy_peaks
from t1d_lab.signals import waveform_features


def test_one_to_one_and_tolerance():
    assert match_beats([100, 200], [95, 105, 215], 10) == [(0, 0)]
    assert match_beats([100, 200], [110, 190], 10) == [(0, 0), (1, 1)]
    assert len(match_beats([10, 20], [1, 11], 10)) == 2


def test_common_edges_and_rate():
    assert core_peaks([0, 199, 200, 999, 1000, 1199], 1200, 100).tolist() == [200, 999]
    assert median_rate(np.arange(0, 1000, 100), 100) == 60
    assert median_rate([0, 100], 100) is None


def test_baseline_matches_existing_rate():
    rate = 250
    t = np.arange(rate * 300) / rate
    values = np.sin(2 * np.pi * 1.2 * t) + .3 * np.sin(2 * np.pi * 9.6 * t)
    peaks = existing_energy_peaks(values, rate)
    assert median_rate(peaks, rate) == waveform_features(values, rate, 'ecg')['ecg_rate']
