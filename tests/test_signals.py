import numpy as np
import pandas as pd
from t1d_lab.signals import source_windows, waveform_features


def test_multiaxis_completeness_counts_samples_not_axes():
    result=waveform_features(np.ones((1000,3)),32,'acc')
    assert result['acc_completeness'] == 1000/9600
    assert 'acc_mean' not in result


def test_future_waveform_perturbation_does_not_change_trailing_features():
    rate=64
    x=np.sin(2*np.pi*1.2*np.arange(400*rate)/rate)
    anchor=pd.DatetimeIndex([pd.Timestamp(300,unit='s')])
    before=source_windows(x,0,rate,anchor,'ppg')
    x[301*rate:]=999
    after=source_windows(x,0,rate,anchor,'ppg')
    assert before == after
    assert before[0]['ppg_input_end'] <= anchor[0]


def test_flat_waveform_is_not_a_valid_pulse():
    result=waveform_features(np.zeros(64*300),64,'ppg')
    assert result['ppg_valid'] == 0
    assert 'ppg_rate' not in result
