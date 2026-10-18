import importlib.util
import io
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
import pytest


def reader():
    path=Path(__file__).parents[1]/'scripts/audit_source_time.py'
    spec=importlib.util.spec_from_file_location('source_audit_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.RestrictedArrayReader


def test_processed_probe_accepts_only_expected_arrays_and_timestamps():
    value={'a':np.array([1.,2.,3.]),'t':pd.Timestamp('2024-01-01')}
    output=reader()(io.BytesIO(pickle.dumps(value))).load()
    assert np.array_equal(output['a'],value['a']) and output['t']==value['t']


def test_processed_probe_cannot_resolve_executable_globals():
    with pytest.raises(pickle.UnpicklingError,match='Disallowed global'):
        reader()(io.BytesIO(pickle.dumps(eval))).load()
