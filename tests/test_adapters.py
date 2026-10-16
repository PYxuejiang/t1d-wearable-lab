import numpy as np
import pandas as pd
from t1d_lab.brist1d import backward_values, trailing_sum


def test_asof_never_uses_future_and_expires_old_values():
    t = pd.to_datetime(['2023-01-01 00:10', '2023-01-01 00:20'])
    s = pd.Series([100., 200.], index=t)
    requested = pd.to_datetime(['2023-01-01 00:09', '2023-01-01 00:19', '2023-01-01 00:40'])
    actual = backward_values(s, requested, 10)
    assert np.isnan(actual[0]) and actual[1] == 100 and np.isnan(actual[2])


def test_event_sums_exclude_future_and_left_boundary():
    t = pd.date_range('2023-01-01', periods=4, freq='5min')
    s = pd.Series([1., 2., 3., 99.], index=t)
    assert trailing_sum(s, t[2:3], 10)[0] == 5
