import numpy as np
import pandas as pd
import pytest

from t1d_lab.evaluation import (Event, alarm_triggers, match_events,
                                nearest_future_reference, reference_events,
                                reference_hours, split_masks)


def times(minutes):
    return pd.Timestamp('2023-01-01') + pd.to_timedelta(minutes, unit='m')


def test_threshold_equality_and_elapsed_duration():
    s = pd.Series([3.9, 3.8, 3.7, 3.6, 3.5, 4], index=times([0, 5, 10, 15, 20, 25]))
    events = reference_events(s)
    assert len(events) == 1 and events[0].start == times([5])[0]
    assert not events[0].left_censored


def test_fifteen_minute_sampling_is_not_three_point_rule():
    s = pd.Series([5, 3.8, 3.7, 5], index=times([0, 15, 30, 45]))
    assert len(reference_events(s, nominal_minutes=15)) == 1


def test_long_gap_does_not_create_event():
    s = pd.Series([5, 3.8, 3.7, 3.6], index=times([0, 5, 40, 45]))
    assert reference_events(s) == []


def test_left_censoring_and_normal_point_break():
    s = pd.Series([3, 3, 3, 3, 5, 3, 3], index=times([0, 5, 10, 15, 20, 25, 30]))
    events = reference_events(s)
    assert len(events) == 1 and events[0].left_censored


def test_duplicate_reference_rejected():
    with pytest.raises(ValueError):
        reference_events(pd.Series([3, 3], index=times([0, 0])))


def test_alarm_does_not_retrigger_during_high_state_or_cooldown():
    t = times([0, 5, 10, 15, 30, 50, 55, 90])
    assert alarm_triggers(t, [.9, .9, .1, .9, .9, .1, .9, .9], .5) == [t[0]]


def test_alarm_after_cooldown_requires_new_rising_edge():
    t = times([0, 5, 40])
    assert alarm_triggers(t, [.9, .1, .9], .5) == [t[0], t[2]]


def test_forecast_and_detection_are_different_and_one_to_one():
    event = Event(times([30])[0], times([50])[0], False)
    alarms = list(times([10, 20, 30, 40]))
    hits, unmatched = match_events([event], alarms, 'forecast')
    assert len(hits) == 1 and hits[0]['offset_minutes'] == 20
    assert len(unmatched) == 3
    hits, _ = match_events([event], alarms, 'detection')
    assert hits[0]['offset_minutes'] == 0


def test_observation_time_excludes_large_gaps():
    assert reference_hours(times([0, 5, 10, 120, 125]), 5) == .25


def test_split_purges_input_and_confirmation_support():
    t = pd.date_range('2023-01-01', periods=2881, freq='min')
    masks = split_masks(t, t[0], t[-1])
    assert np.max(sum(x.astype(int) for x in masks.values())) == 1
    first = t[0] + (t[-1] - t[0]) * .6
    assert (t[masks['train']] + pd.Timedelta(minutes=45) < first).all()
    assert (t[masks['validation']] - pd.Timedelta(minutes=60) >= first).all()


def test_future_target_tolerance_does_not_fill_missing_reference():
    s = pd.Series([4., 5., 6.], index=times([0, 30, 75]))
    target, observed = nearest_future_reference(s, times([0, 10]))
    assert target[0] == 5 and np.isnan(target[1])
    assert pd.isna(observed.iloc[1])

