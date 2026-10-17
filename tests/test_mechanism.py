import numpy as np
import pandas as pd
from t1d_lab.mechanism import alert_indices,event_metrics,NS_MINUTE,smooth_scores,fit_normalizer,transform,prepare,availability,RAW,ECG,DEVIATIONS
from t1d_lab.evaluation import alarm_triggers


def test_legacy_policy_matches_frozen_behavior_including_cooldown():
    t=pd.date_range('2026-01-01',periods=50,freq='5min');p=np.tile([.8,.1,.8,.8,.1],10);p[23]=np.nan
    old=alarm_triggers(t,p,.5)
    new=t[alert_indices(t.as_unit('ns').asi8,p,.5,'legacy_edge')].tolist()
    assert new==old


def test_confirmation_reminder_missing_and_gap():
    t=np.arange(12,dtype=np.int64)*5*NS_MINUTE;p=np.ones(12)
    assert alert_indices(t,p,.5,'confirm2').tolist()==[1]
    assert alert_indices(t,p,.5,'smooth_remind30').tolist()==[1,7]
    p[1]=np.nan
    assert alert_indices(t,p,.5,'confirm2').tolist()==[3]
    t[5:]+=60*NS_MINUTE
    assert alert_indices(t,p,.5,'confirm2').tolist()==[3,6]


def test_event_denominator_keeps_missing_input_and_current_matching():
    t=np.arange(20,dtype=np.int64)*5*NS_MINUTE;p=np.zeros(20);p[4:9]=1;p[12:17]=np.nan
    events=[(t[4],t[8]),(t[12],t[16])]
    r=event_metrics(t,p,events,.5,'confirm2')
    assert r['reference_events']==2 and r['matched_events']==1
    assert r['event_recall']==.5 and r['conditional_event_recall']==1
    assert r['delay_median_minutes']==5


def test_smoothing_is_causal_and_normalizer_uses_training_only():
    t=np.arange(20,dtype=np.int64)*5*NS_MINUTE;a=np.arange(20)/20;b=a.copy();b[10:]=999
    assert np.array_equal(smooth_scores(t,a,'smooth_confirm2')[:10],smooth_scores(t,b,'smooth_confirm2')[:10])
    f=pd.DataFrame({c:np.arange(50,dtype=float) for c in RAW+ECG+DEVIATIONS+['ecghr_dev']})
    f['hour_sin']=0.;f['hour_cos']=1.;f['wrist_present']=1.;f['ecg_present']=1.;f['label_low']=False
    state=fit_normalizer(f.iloc[:30]);x=transform(f,state)
    f.loc[30:,RAW+ECG]=99999
    assert transform(f,state).iloc[:30].equals(x.iloc[:30])
    assert state['training_rows']==30


def test_preparation_uses_only_past_and_masks_missing_modality():
    t=pd.date_range('2026-01-01',periods=50,freq='5min')
    f=pd.DataFrame({'decision_time':t,'available':True,'ecg_completeness':1.,'ecg_valid':1.,'hour_sin':0.,'hour_cos':1.,'label_low':False})
    sources=['ppg_rate','ppg_interval_rmssd','ppg_interval_std','eda_mean','eda_diff_std','temp_mean','acc_std',
             'ppg_spectral_concentration','ecg_rate','ecg_interval_rmssd','ecg_interval_std','ecg_spectral_concentration']
    for c in sources:f[c]=np.arange(50,dtype=float)+40
    a=prepare(f);f.loc[25:,sources]=9999;b=prepare(f)
    assert a.iloc[:25].equals(b.iloc[:25])
    f.loc[0,'available']=False;f.loc[1,'ecg_completeness']=0.;c=prepare(f)
    assert c.loc[0,RAW].isna().all() and c.loc[1,ECG].isna().all()
    assert not availability(c,'personal_raw')[0] and availability(c,'pooled_fallback')[0]
