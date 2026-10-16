"""Pandas 3 commonly defaults to microseconds; mixed resolution must be harmless."""
import numpy as np
import pandas as pd
from t1d_lab.brist1d import backward_values,trailing_sum
from t1d_lab.evaluation import nearest_future_reference,reference_hours
from t1d_lab.risk import incident_labels


def test_microsecond_source_and_nanosecond_queries_have_identical_semantics():
    t=pd.date_range('2026-01-01',periods=40,freq='5min').as_unit('us')
    s=pd.Series(5.,index=t);s.iloc[12:17]=3.
    query=t.as_unit('ns')
    assert reference_hours(t,5)==195/60
    assert np.array_equal(backward_values(s,query,1),s.to_numpy())
    assert trailing_sum(s,query[3:4],10)[0]==10
    v,observed=nearest_future_reference(s,query)
    assert v[6]==3. and observed.iloc[6]==t[12]
    labels,_=incident_labels(s,5)
    assert labels.iloc[6].incident_y==1
