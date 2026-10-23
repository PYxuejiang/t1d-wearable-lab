import numpy as np
import pytest

pytest.importorskip('torch')
from t1d_lab.pretrained_ppg import prepare_segment, load_encoder


def test_ppg_adapter_preserves_time_extent_and_has_finite_output():
    t = np.arange(512) / 64
    x = np.sin(2 * np.pi * 1.2 * t)
    y = prepare_segment(x)
    assert y.shape == (400,)
    assert np.isfinite(y).all()
    np.testing.assert_allclose(y, prepare_segment(x * 2 + 20), rtol=1e-4, atol=1e-5)


@pytest.mark.parametrize('x', [np.zeros(512), np.ones(511), np.full(512, np.nan)])
def test_bad_ppg_must_abstain(x):
    with pytest.raises(ValueError):
        prepare_segment(x)


def test_unreviewed_architecture_never_executes(tmp_path):
    path = tmp_path / 'code.py'
    path.write_text('raise RuntimeError("MUST NOT EXECUTE")')
    with pytest.raises(ValueError, match='Unreviewed'):
        load_encoder(path, tmp_path / 'missing.pt', '0' * 64)
