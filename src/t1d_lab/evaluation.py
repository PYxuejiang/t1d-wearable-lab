"""Frozen reference-event, alarm and split semantics (not clinical standards)."""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Event:
    start: pd.Timestamp
    end: pd.Timestamp
    left_censored: bool


def reference_events(glucose, nominal_minutes=5, threshold=3.9, minimum_minutes=15):
    """Observed low runs; no interpolation or bridging a normal point/gap."""
    series = glucose.dropna().sort_index()
    if series.index.has_duplicates:
        raise ValueError('Resolve duplicate reference timestamps before event generation')
    max_gap = pd.Timedelta(minutes=1.5 * nominal_minutes)
    events, start, end, left, previous_time, previous_value = [], None, None, True, None, None
    for timestamp, value in series.items():
        broken = previous_time is not None and timestamp - previous_time > max_gap
        if start is not None and (value >= threshold or broken):
            if (end - start).total_seconds() >= minimum_minutes * 60:
                events.append(Event(start, end, left))
            start = end = None
        if value < threshold:
            if start is None:
                start = timestamp
                left = previous_time is None or broken or previous_value < threshold
            end = timestamp
        previous_time, previous_value = timestamp, value
    if start is not None and (end - start).total_seconds() >= minimum_minutes * 60:
        events.append(Event(start, end, left))
    return events


def alarm_triggers(times, scores, threshold, cooldown_minutes=30):
    """Rising-edge alarms; no repeated alarms while score stays high."""
    active, cooldown_until, alarms = False, None, []
    for timestamp, score in zip(times, scores):
        if not np.isfinite(score) or score < threshold:
            if active:
                cooldown_until = timestamp + pd.Timedelta(minutes=cooldown_minutes)
            active = False
            continue
        if not active:
            if cooldown_until is None or timestamp >= cooldown_until:
                alarms.append(timestamp)
            active = True
    return alarms


def match_events(events, alarms, task, horizon_minutes=30):
    """One-to-one chronological matching. Unknown follow-up must be excluded upstream."""
    if task not in {'forecast', 'detection'}:
        raise ValueError(task)
    alarms = sorted(alarms)
    used, matches = set(), []
    for index, event in enumerate(events):
        if event.left_censored:
            continue
        candidates = [
            (j, time) for j, time in enumerate(alarms) if j not in used and (
                event.start - pd.Timedelta(minutes=horizon_minutes) <= time < event.start
                if task == 'forecast' else event.start <= time <= event.end
            )
        ]
        if candidates:
            j, time = candidates[0]
            used.add(j)
            matches.append({'event_index': index, 'alarm_time': time, 'event_start': event.start,
                            'offset_minutes': (event.start - time).total_seconds() / 60})
    return matches, [time for j, time in enumerate(alarms) if j not in used]


def reference_hours(index, nominal_minutes):
    gaps = np.diff(pd.DatetimeIndex(index).sort_values().unique().asi8) / 60e9
    return float(gaps[(gaps > 0) & (gaps <= 1.5 * nominal_minutes)].sum() / 60)


def split_masks(times, reference_start, reference_end, history_minutes=60, horizon_minutes=30, confirmation_minutes=15):
    """Chronological 60/20/20, purged by the full input/target support."""
    times = pd.DatetimeIndex(times)
    span = reference_end - reference_start
    first, second = reference_start + span * .6, reference_start + span * .8
    support_start = times - pd.Timedelta(minutes=history_minutes)
    support_end = times + pd.Timedelta(minutes=horizon_minutes + confirmation_minutes)
    return {
        'train': (support_start >= reference_start) & (support_end < first),
        'validation': (support_start >= first) & (support_end < second),
        'test': (support_start >= second) & (support_end <= reference_end),
    }


def nearest_future_reference(series, times, horizon_minutes=30, tolerance_minutes=2.5):
    """Future reference is a label, never an input. Ties choose earlier timestamp."""
    series = series.dropna().sort_index()
    if series.index.has_duplicates:
        raise ValueError('Duplicate reference timestamps')
    times = pd.DatetimeIndex(times)
    desired = times + pd.Timedelta(minutes=horizon_minutes)
    source = series.index.asi8
    insertion = np.searchsorted(source, desired.asi8)
    before = np.clip(insertion - 1, 0, len(source) - 1)
    after = np.clip(insertion, 0, len(source) - 1)
    indices = np.where(abs(source[before] - desired.asi8) <= abs(source[after] - desired.asi8), before, after)
    distances = abs(source[indices] - desired.asi8) / 60e9
    valid = distances <= tolerance_minutes
    values = series.to_numpy(dtype=float)[indices].copy()
    values[~valid] = np.nan
    target_times = pd.Series(series.index[indices], index=times).where(valid)
    return values, target_times

