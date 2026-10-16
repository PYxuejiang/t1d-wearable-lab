import numpy as np
import pandas as pd

from t1d_lab.risk import incident_labels,point_metrics


def test_incident_target_is_future_onset_not_current_low():
    t=pd.date_range('2023-01-01',periods=40,freq='5min')
    g=pd.Series(5.,index=t)
    g.iloc[12:17]=3.
    labels,events=incident_labels(g,5)
    assert labels.loc[t[6],'incident_y']==1
    assert np.isnan(labels.loc[t[13],'incident_y'])
    assert np.isnan(labels.iloc[-1].incident_y)
    assert len(events)==1


def test_unknown_future_is_not_negative():
    t=pd.date_range('2023-01-01',periods=40,freq='5min')
    g=pd.Series(5.,index=t).drop(t[10:14])
    labels,_=incident_labels(g,5)
    assert np.isnan(labels.loc[t[6],'incident_y'])


def test_single_class_metrics_are_not_perfect_scores():
    result=point_metrics([0,0],[.1,.2])
    assert result['ap'] is None and result['roc_auc'] is None
