import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip('torch')
from t1d_lab.pretrained_ppg import file_sha256

spec = importlib.util.spec_from_file_location('compare_pulse', Path(__file__).parents[1] / 'scripts/compare_pulse_lora.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_history_never_bridges_gap_or_uses_next_waveform(tmp_path):
    seconds = np.array([0, 300, 600, 900, 1500, 1800, 2100], dtype=np.int64)
    vectors = np.arange(len(seconds), dtype=np.float32)[:, None].repeat(512, 1)
    path = tmp_path / 'person.npz'
    np.savez(path, decision_ns=seconds * 10**9, embedding=vectors)
    (tmp_path / 'person.json').write_text(json.dumps({'embedding_sha256': file_sha256(path)}))
    frame = pd.DataFrame({'subject': 'person', 'decision_time': pd.to_datetime(seconds, unit='s'),
                          'glucose_mg_dl': [80, 80, 60, 80, 60, 60, 80]})
    x, y, counts, _, elapsed = runner.partition(['person'], tmp_path, frame)
    assert x[:, :, 0].tolist() == [[0, 1, 2], [1, 2, 3], [4, 5, 6]]
    assert y.tolist() == [1, 0, 0]
    assert counts[0]['incomplete_history'] == 4
    # A future reference cannot affect earlier labels or their historical inputs.
    frame.loc[6, 'glucose_mg_dl'] = 50
    xx, yy, _, _, _ = runner.partition(['person'], tmp_path, frame)
    np.testing.assert_array_equal(xx, x)
    assert yy.tolist() == [1, 0, 1]


def test_clock_jitter_uses_real_elapsed_time_without_bridging_missing_samples(tmp_path):
    seconds = np.array([0, 299, 600, 899, 1500, 1799, 2100], dtype=np.int64)
    path = tmp_path / 'person.npz'
    np.savez(path, decision_ns=seconds * 10**9, embedding=np.arange(7, dtype=np.float32)[:, None].repeat(512, 1))
    (tmp_path / 'person.json').write_text(json.dumps({'embedding_sha256': file_sha256(path)}))
    frame = pd.DataFrame({'subject': 'person', 'decision_time': pd.to_datetime(seconds, unit='s'),
                          'glucose_mg_dl': [80, 80, 60, 80, 60, 60, 80]})
    x, y, counts, _, elapsed = runner.partition(['person'], tmp_path, frame, tolerance_seconds=5)
    assert counts[0]['usable_history'] == 3
    np.testing.assert_allclose(elapsed[0, :, 0], [0, 299 / 600, 1])
    np.testing.assert_allclose(elapsed[1, :, 0], [0, 301 / 600, 1])
    assert x[-1, :, 0].tolist() == [4, 5, 6]
