import numpy as np
import pytest
from t1d_lab.ppg_capture import match_seconds,metrics,detect_window,score_window,select_lag
from t1d_lab.ppg_morphology import short_features


def test_subsecond_matching_does_not_truncate_to_integer():
    assert match_seconds([1.0],[1.101],.1)==[]
    assert match_seconds([1.0],[1.1],.1)==[(0,0)]
    assert match_seconds([.1,.2],[.01,.11],.1)==[(0,0),(1,1)]
    with pytest.raises(ValueError):match_seconds([1,1],[1])


def test_missing_beats_do_not_make_false_adjacent_ppi_pairs():
    r=metrics([1,2,3,4],[1,3,4])
    assert r['tp']==3 and r['fn']==1 and r['ppi_pairs']==1
    assert r['reference_pairs']==3 and r['ppi_abs_sum_ms']==0
    r=metrics([1,2],[])
    assert r['tp']==0 and r['fn']==2 and r['hr_windows']==0


def test_shared_reference_core_and_quality_rejection():
    r={'reference':[1.9,2.1,28.9,29.1],'detected':{'v5_peaks':[2.3,29.1]}}
    a=score_window(r,'v5_peaks',.2);b=score_window(r,'v5_peaks',0)
    assert a['tp']+a['fn']==b['tp']+b['fn']==2
    assert score_window(r,'v5_peaks',.2,accepted=False)['fn']==2


def test_baseline_matches_v5_short_window_rate_and_flat_rejection():
    fs=64;t=np.arange(fs*30)/fs;x=np.sin(2*np.pi*1.2*t)
    peaks=detect_window(x,fs,'v5_peaks')
    assert 60/np.median(np.diff(peaks))==pytest.approx(short_features(x,fs)['pulse_rate'])
    for method in ['v5_peaks','dual_average']:
        assert len(detect_window(np.zeros(fs*30),fs,method))==0
        assert 31<=len(detect_window(x,fs,method))<=35


def test_lag_selection_uses_provided_calibration_only_and_tie_rule():
    r={'reference':[3,4,5],'detected':{'v5_peaks':[3.2,4.2,5.2]}}
    assert select_lag([r],[0,.1,.2,.3,.4])==.2
    assert select_lag([{'reference':[],'detected':{'v5_peaks':[]}}],[0,.1,.2,.3])==.2


def test_independent_dynamic_programming_matches_greedy_on_random_short_sequences():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'scripts/verify_ppg_capture.py'
    spec=importlib.util.spec_from_file_location('verify_capture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rng=np.random.default_rng(13)
    for _ in range(100):
        a=np.unique(rng.uniform(0,3,15));b=np.unique(rng.uniform(0,3,18))
        assert module.dp_count(a,b)==len(match_seconds(a,b))
