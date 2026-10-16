"""Public long-table schema adapter; each channel is handled separately."""
from pathlib import Path

import numpy as np
import pandas as pd

from .evaluation import reference_events

FIELDS = ('bg', 'insulin', 'carbs', 'hr', 'dist', 'steps', 'cals')


def read_subject(path):
    frame = pd.read_csv(path, low_memory=False)
    if not {'timestamp', 'device', *FIELDS}.issubset(frame.columns):
        raise ValueError(f'Unexpected schema: {path}')
    frame['timestamp'] = pd.to_datetime(frame['timestamp'], errors='raise')
    channels, report = {}, {'subject': Path(path).stem, 'rows': len(frame), 'channels': {}}
    for key in FIELDS:
        observed = frame.loc[frame[key].notna(), ['timestamp', key, 'device']].copy()
        observed[key] = pd.to_numeric(observed[key], errors='coerce')
        invalid = int((~np.isfinite(observed[key])).sum())
        observed = observed[np.isfinite(observed[key])]
        counts = observed.groupby('timestamp')[key].nunique()
        conflicts = counts[counts > 1].index
        clean = observed[~observed['timestamp'].isin(conflicts)].drop_duplicates('timestamp').sort_values('timestamp')
        series = pd.Series(clean[key].to_numpy(dtype=float), index=pd.DatetimeIndex(clean['timestamp']), name=key)
        channels[key] = series
        report['channels'][key] = {'raw_nonempty': len(observed), 'invalid_numeric': invalid,
                                  'conflicting_timestamps_excluded': len(conflicts), 'clean_observations': len(series),
                                  'sources': observed['device'].value_counts().to_dict()}
    g = channels['bg']
    if len(g) < 100 or (g <= 0).any():
        raise ValueError(f'Insufficient or nonpositive glucose: {path}')
    training_end = g.index[0] + (g.index[-1] - g.index[0]) * .6
    gaps = np.diff(g.loc[:training_end].index.as_unit('ns').asi8) / 60e9
    nominal = float(np.median(gaps[(gaps > 0) & (gaps < 30)]))
    report.update(first_time=str(g.index[0]), last_time=str(g.index[-1]), nominal_cgm_minutes=nominal,
                  low_readings=int((g < 3.9).sum()), events=len(reference_events(g, nominal)),
                  cgm_training_end=str(training_end), timezone='not supplied; wall-clock retained')
    return channels, report


def backward_values(series, times, max_age_minutes):
    """Strictly past-only values, with per-field expiry."""
    times = pd.DatetimeIndex(times)
    if series.empty:
        return np.full(len(times), np.nan)
    positions = np.searchsorted(series.index.as_unit('ns').asi8, times.as_unit('ns').asi8, side='right') - 1
    safe = np.maximum(positions, 0)
    age = (times.as_unit('ns').asi8 - series.index.as_unit('ns').asi8[safe]) / 60e9
    valid = (positions >= 0) & (age >= 0) & (age <= max_age_minutes)
    return np.where(valid, series.to_numpy(dtype=float)[safe], np.nan)


def trailing_sum(series, times, minutes):
    times = pd.DatetimeIndex(times)
    if series.empty:
        return np.zeros(len(times))
    x = series.index.as_unit('ns').asi8
    cumulative = np.r_[0., np.cumsum(series.to_numpy(dtype=float))]
    end = np.searchsorted(x, times.as_unit('ns').asi8, side='right')
    start = np.searchsorted(x, times.as_unit('ns').asi8 - pd.Timedelta(minutes=minutes).value, side='right')
    return cumulative[end] - cumulative[start]

