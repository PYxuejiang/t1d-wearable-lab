import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('verify_module2',Path(__file__).parents[1]/'scripts/verify_module2.py')
verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)


def test_missing_reference_time_does_not_count_as_coverage():
    times=pd.to_datetime(['2026-01-01 00:00','2026-01-01 00:05','2026-01-01 00:10','2026-01-01 01:00','2026-01-01 01:05'])
    frame=pd.DataFrame({'decision_time':times,'score':[.1,.1,np.nan,.1,.1],'threshold':.5})
    metric=verifier.evaluate(frame,[])
    assert metric['observation_hours']==15/60
    assert metric['coverage']==10/15
    assert metric['anchor_coverage']==4/5


def test_detection_never_matches_alarm_before_low_onset():
    t=pd.date_range('2026-01-01',periods=9,freq='5min')
    reference=pd.Series([100,69,68,67,66,100,100,100,100],index=t)
    events=verifier.event_runs(reference)
    assert events==[(t[1],t[4])]
    frame=pd.DataFrame({'decision_time':t,'score':[.9]*9,'threshold':.5})
    metrics=verifier.evaluate(frame,events)
    assert metrics['matched_events']==0
    assert metrics['unmatched_alarms']==1
