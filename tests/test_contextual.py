import numpy as np
import pandas as pd
import pytest
from t1d_lab.contextual import WEARABLE,SETS,prepare,fit_calibration,calibrated_scores,threshold_on_validation,validate_protocol


def test_missing_context_is_not_a_normal_value_or_future_cgm_feature():
    raw=pd.DataFrame({c:[1.,2.] for c in WEARABLE});raw['sin_hour']=0.;raw['cos_hour']=1.;raw['hour']=0;raw['hypoglycemia']=[0,1];raw['cgm']=[10.,2.]
    f,missing=prepare(raw)
    assert missing==['IOB','time_since_lastmeal_ord']
    assert f.IOB.isna().all() and f.time_since_lastmeal_ord.isna().all()
    assert all('cgm' not in cols and 'hypoglycemia' not in cols for cols in SETS.values())


def test_sigmoid_calibration_preserves_order_and_missingness():
    p=np.linspace(.01,.99,100);y=np.r_[np.zeros(50),np.ones(50)]
    fit=fit_calibration(p,y);q=calibrated_scores(np.r_[p,np.nan],fit)
    assert fit['type']=='sigmoid' and np.all(np.diff(q[:-1])>0) and np.isnan(q[-1])


def test_nonpositive_calibration_does_not_reverse_a_bad_model():
    p=np.linspace(.01,.99,100);y=np.r_[np.ones(50),np.zeros(50)]
    fit=fit_calibration(p,y)
    assert fit['type']=='constant' and fit['reason']=='nonpositive_validation_slope_no_ranking_flip'
    assert np.allclose(calibrated_scores(p,fit),.5)
    assert threshold_on_validation([0,0],[.1,.9])==1.001


def test_older_short_purge_cannot_run_with_four_hour_context():
    with pytest.raises(ValueError,match='Insufficient row separation'):
        validate_protocol({'purge_rows':120,'feature_sets':['combined']})
    validate_protocol({'purge_rows':150,'feature_sets':['combined']})
