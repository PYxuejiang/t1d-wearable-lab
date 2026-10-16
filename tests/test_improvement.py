import numpy as np
import pandas as pd
from t1d_lab.improvement import features,past_smooth


def test_temporal_features_do_not_change_after_future_signal_perturbation():
    t=pd.date_range('2026-01-01',periods=50,freq='5min')
    raw=pd.DataFrame({'decision_time':t,'ppg_rate':np.arange(50,dtype=float),'ppg_valid':1,'label_low':False})
    for k in ['ppg','acc','eda','temp']:raw[k+'_completeness']=1.
    a,sets=features(raw)
    raw.loc[25:,'ppg_rate']=9999
    b,_=features(raw)
    assert a.loc[:24,sets['dynamic_time']].equals(b.loc[:24,sets['dynamic_time']])
    assert not any(c.startswith('label') for v in sets.values() for c in v)


def test_smoothing_resets_after_missing_or_large_gap():
    t=pd.to_datetime(['2026-01-01 00:00','2026-01-01 00:05','2026-01-01 00:10','2026-01-01 00:15','2026-01-01 01:00'])
    result=past_smooth(t,[1,0,np.nan,0,1],3)
    assert result[1]==.5 and np.isnan(result[2]) and result[3]==0 and result[4]==1
