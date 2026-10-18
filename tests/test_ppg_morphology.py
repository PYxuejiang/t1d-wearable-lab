import numpy as np
from t1d_lab.ppg_morphology import interval_stats,window_features,sample_bounds


def test_invalid_pulse_gap_does_not_create_fake_successive_intervals():
    rr=np.array([1,1,1,1,1,3,.5,.5,.5,.5,.5])
    r=interval_stats(np.r_[0,np.cumsum(rr)]*64,64)
    assert r['ppi_rmssd']==0 and r['valid_pair_fraction']==.8


def test_regular_pulse_and_flat_signal_have_distinct_support():
    t=np.arange(300*64)/64;x=np.sin(2*np.pi*1.2*t)
    r=window_features(x);assert abs(r['pm_pulse_rate_median']-72)<1 and r['pm_short_valid_fraction']==1
    assert r['pm_ppi_rmssd_median']<.025 and r['pm_template_correlation_median']>.95
    flat=window_features(np.zeros(300*64));assert flat['pm_short_valid_fraction']==0 and np.isnan(flat['pm_pulse_rate_median'])


def test_trailing_sample_window_excludes_future_and_includes_anchor():
    a,b=sample_bounds(1000,1600,64);assert b-a==19200 and b-1==38400
    source=np.sin(np.arange(50000)*.12);old=window_features(source[a:b]);source[b:]=100000
    assert old==window_features(source[a:b])
