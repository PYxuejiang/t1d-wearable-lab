import numpy as np
import pandas as pd
from t1d_lab.late_fusion import add_weight_groups,training_weights,mean_fusion,stack_design,available


def test_run_weights_balance_long_short_runs_without_losing_subjects():
    f=pd.DataFrame({'subject':['a']*8,'decision_time':pd.date_range('2024-01-01',periods=8,freq='5min'),
                    'label_low':[0,1,1,1,0,1,0,0]})
    f=add_weight_groups(f);w=training_weights(f,'run')
    assert np.isclose(w[1:4].sum(),w[5])
    assert np.isclose(w[f.label_low.eq(1)].sum(),w[f.label_low.eq(0)].sum())
    g=pd.concat([f,f.iloc[:4].assign(subject='b')],ignore_index=True)
    w=training_weights(g,'run');assert np.isclose(w[:8].sum(),w[8:].sum())


def test_run_groups_respect_missing_reference_gap_and_future_prefix():
    f=pd.DataFrame({'decision_time':pd.to_datetime(['2024-01-01 00:00','2024-01-01 00:05','2024-01-01 00:30']),
                    'label_low':[1,1,1],'subject':['a']*3})
    a=add_weight_groups(f);b=add_weight_groups(f.iloc[:2])
    assert list(a.low_run[:2])==list(b.low_run) and a.low_run.iloc[2]!=a.low_run.iloc[1]


def test_missing_specialist_is_not_zero_probability_and_cannot_enable_score():
    p={'ecg':np.array([.8,np.nan,np.nan]),'ppg':np.array([.2,.4,np.nan]),'eda':np.array([np.nan,.6,np.nan])}
    result=mean_fusion(p);assert np.allclose(result[:2],[.5,.5]) and np.isnan(result[2])
    frame=pd.DataFrame({'hour_sin':[0]*3,'hour_cos':[1]*3,'wrist_present':[1,1,0],'ecg_present':[1,0,0]})
    design=stack_design(frame,p);assert design.shape==(3,8)
    assert design[0,2]==0 and design[0,5]==0 and design[0,3]==1
    assert available(frame,'early').tolist()==[True,True,False]
    assert available(frame,'ecg').tolist()==[True,False,False]
