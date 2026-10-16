import numpy as np
import pandas as pd

from t1d_lab.brist1d import backward_values
from t1d_lab.forecasting import metric_rows, paired_bootstrap


def test_lag_cannot_reach_before_history_start():
    t = pd.to_datetime(['2023-01-01 00:00', '2023-01-01 01:01'])
    s = pd.Series([5., 8.], index=t)
    assert np.isnan(backward_values(s, t[1:] - pd.Timedelta(minutes=60), 0)[0])


def test_subject_equal_metrics_and_paired_gain():
    rows = []
    for subject, n in [('A', 2), ('B', 20)]:
        for name, value in [('baseline', 3.), ('fusion', 2.)]:
            rows += [dict(protocol='test', subject=subject, model=name, prediction=value,target=1.)] * n
    metrics = metric_rows(pd.DataFrame(rows))
    result = paired_bootstrap(metrics, 'baseline', 'fusion', repetitions=100)
    assert result['paired_subjects'] == 2
    assert result['relative_mae_improvement_percent'] == 50
    assert result['mae_difference_95_interval'] == [1.,1.]
