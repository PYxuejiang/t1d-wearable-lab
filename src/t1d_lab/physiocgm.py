"""Read source archives without expanding multi-gigabyte raw records."""
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


def read_cgm(archive):
    with ZipFile(archive) as z:
        name = next(n for n in z.namelist() if n.lower().endswith('cgm.csv'))
        raw = pd.read_csv(z.open(name), low_memory=False)
    raw = raw[raw['Event Type'].eq('EGV')].copy()
    time_col = next(c for c in raw if c.startswith('Timestamp'))
    raw['time'] = pd.to_datetime(raw[time_col], format='mixed', errors='raise')
    text = raw['Glucose Value (mg/dL)'].astype(str).str.strip()
    numeric = pd.to_numeric(text, errors='coerce')
    # Bounds are used for threshold labels only; not treated as measured numeric values.
    raw['censoring'] = np.select([text.str.lower().eq('low'), text.str.lower().eq('high')], ['low', 'high'], default='none')
    raw['glucose_mg_dl'] = numeric
    raw['label_proxy_mg_dl'] = np.where(raw['censoring'].eq('low'), 39., np.where(raw['censoring'].eq('high'), 401., numeric))
    raw = raw.drop_duplicates(['time', 'label_proxy_mg_dl']).sort_values('time')
    conflicts = raw.groupby('time')['label_proxy_mg_dl'].nunique()
    raw = raw[~raw['time'].isin(conflicts[conflicts > 1].index)].drop_duplicates('time')
    raw = raw.set_index('time')
    if raw['label_proxy_mg_dl'].isna().any():
        raise ValueError('Unknown glucose encoding; audit before use')
    return raw[['glucose_mg_dl', 'label_proxy_mg_dl', 'censoring']]


def e4_series(z, name, bin_minutes=1):
    with z.open(name) as stream:
        first = float(stream.readline().decode().split(',')[0])
        rate = float(stream.readline().decode().split(',')[0])
        try:
            values = pd.read_csv(stream, header=None).to_numpy(dtype=float)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=[0], index=pd.DatetimeIndex([]), dtype=float), rate
    count = len(values)
    index = pd.to_datetime(first + np.arange(count) / rate, unit='s', utc=True).tz_localize(None)
    frame = pd.DataFrame(values, index=index)
    return frame.resample(f'{bin_minutes}min').median(), rate


def audit_archive(path):
    path = Path(path)
    cgm = read_cgm(path)
    with ZipFile(path) as z:
        names = z.namelist()
        ecg_files = [n for n in names if n.endswith('_ECG.csv')]
        summary_files = [n for n in names if n.endswith('_SummaryEnhanced.csv')]
        ppg_files = [n for n in names if n.endswith('/BVP.csv')]
        hr_files = [n for n in names if n.endswith('/HR.csv')]
        e4 = pd.concat([e4_series(z, n)[0].iloc[:, 0] for n in hr_files]).groupby(level=0).median().sort_index()
        zephyr_parts = []
        for n in summary_files:
            d = pd.read_csv(z.open(n), usecols=['Time', 'HR', 'HRConfidence'])
            d['time'] = pd.to_datetime(d['Time'], format='%d/%m/%Y %H:%M:%S.%f', errors='raise')
            d = d[d['HRConfidence'].ge(80) & d['HR'].gt(0)].set_index('time')
            if len(d):
                zephyr_parts.append(d['HR'].resample('min').median())
        if not zephyr_parts:
            raise ValueError('No usable independent HR for clock audit')
        zephyr = pd.concat(zephyr_parts).groupby(level=0).median().sort_index()
        # Unlabelled sensor-to-sensor clock audit: only initial 60% of wall-clock span.
        train_end = zephyr.index[0] + (zephyr.index[-1] - zephyr.index[0]) * .6
        train = zephyr.loc[:train_end]
        candidates = []
        for hours in range(-12, 15):
            shifted = e4.copy()
            shifted.index = shifted.index + pd.Timedelta(hours=hours)
            pairs = pd.concat([train.rename('chest'), shifted.rename('wrist')], axis=1).loc[:train_end].dropna()
            pairs = pairs[pairs['wrist'].gt(0)]
            if len(pairs) >= 300:
                candidates.append({'shift_hours': hours, 'paired_minutes': len(pairs),
                                   'median_hr_absolute_difference': float((pairs.chest - pairs.wrist).abs().median()),
                                   'hr_correlation': float(pairs.chest.corr(pairs.wrist))})
        candidates.sort(key=lambda x: x['median_hr_absolute_difference'])
        if not candidates:
            raise ValueError('No clock candidate with >=300 training-only paired minutes')
        best = candidates[0]
        margin = candidates[1]['median_hr_absolute_difference'] - best['median_hr_absolute_difference'] if len(candidates) > 1 else None
        resolved = best['hr_correlation'] >= .5 and best['median_hr_absolute_difference'] <= 10 and margin is not None and margin >= 1
        return {
            'subject': path.name.removesuffix('_raw.zip'), 'archive_members': len(names),
            'expanded_bytes_not_extracted': sum(x.file_size for x in z.infolist()),
            'ecg_files': len(ecg_files), 'ppg_files': len(ppg_files),
            'cgm_observations': len(cgm), 'censored_low': int(cgm.censoring.eq('low').sum()),
            'low_observations': int(cgm.label_proxy_mg_dl.lt(70).sum()),
            'best_clock_candidate': best, 'clock_margin_bpm': margin, 'clock_resolved_by_sensor_check': bool(resolved),
            'clock_candidates': candidates,
            'time_assumption': 'CGM and Zephyr naive wall clocks treated as same local clock; E4 shift checked using training-only HR, without glucose labels.',
            'clock_training_end': str(train_end),
            'cgm_first': str(cgm.index[0]), 'cgm_last': str(cgm.index[-1]),
            'zephyr_first': str(zephyr.index[0]), 'zephyr_last': str(zephyr.index[-1]),
        }

