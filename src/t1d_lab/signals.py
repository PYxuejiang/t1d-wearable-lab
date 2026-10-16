"""Trailing five-minute raw-signal features, extracted directly from ZIPs."""
from datetime import datetime
from zipfile import ZipFile

import numpy as np
import pandas as pd
from scipy import signal, stats

from .physiocgm import read_cgm


def waveform_features(values, rate, kind):
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    present_rows = finite.all(axis=1) if finite.ndim == 2 else finite
    completeness = float(present_rows.sum() / (rate * 300))
    result = {f'{kind}_completeness': min(1., completeness)}
    if completeness < .9 or not finite.all() or len(values) < rate * 30:
        return result
    if values.ndim == 2:
        values = np.linalg.norm(values, axis=1)
    sd = float(np.std(values))
    result.update({f'{kind}_mean': float(np.mean(values)), f'{kind}_std': sd,
                   f'{kind}_iqr': float(np.quantile(values,.75) - np.quantile(values,.25)),
                   f'{kind}_diff_std': float(np.std(np.diff(values)))})
    if kind not in {'ppg', 'ecg'}:
        return result
    if sd < 1e-6:
        result[f'{kind}_valid'] = 0.
        return result
    result[f'{kind}_valid'] = 1.
    result[f'{kind}_skew'] = float(stats.skew(values))
    low, high = (.5, 5) if kind == 'ppg' else (5, 20)
    filtered = signal.sosfilt(signal.butter(3, [low, high], btype='bandpass', fs=rate, output='sos'), values)
    if kind == 'ecg':
        processed = signal.lfilter(np.ones(max(1,int(.08*rate))) / max(1,int(.08*rate)), [1], filtered ** 2)
    else:
        processed = filtered
    peaks, _ = signal.find_peaks(processed, distance=max(1,int(.3*rate)), prominence=max(1e-9,float(np.std(processed))*.5))
    intervals = np.diff(peaks) / rate
    intervals = intervals[(intervals >= .3) & (intervals <= 2)]
    if len(intervals) >= 5:
        result[f'{kind}_rate'] = float(60 / np.median(intervals))
        result[f'{kind}_interval_std'] = float(np.std(intervals))
        result[f'{kind}_interval_rmssd'] = float(np.sqrt(np.mean(np.diff(intervals) ** 2)))
    f, power = signal.welch(filtered, fs=rate, nperseg=min(len(filtered), int(rate*20)))
    band = (f >= .5) & (f <= 3.5)
    if band.any() and np.sum(power[band]) > 0:
        result[f'{kind}_spectral_rate'] = float(f[band][np.argmax(power[band])] * 60)
        result[f'{kind}_spectral_concentration'] = float(np.max(power[band]) / np.sum(power[band]))
    return result


def source_windows(values, start_epoch, rate, anchors, kind, offset=0):
    """Array samples have exact header-derived time; only samples <= anchor are used."""
    duration = len(values) / rate
    start = pd.Timestamp(start_epoch, unit='s') + pd.Timedelta(hours=offset)
    end = start + pd.Timedelta(seconds=duration)
    eligible = anchors[(anchors >= start + pd.Timedelta(minutes=5)) & (anchors < end)]
    rows = []
    for time in eligible:
        right = min(len(values), int(np.floor((time-start).total_seconds()*rate)) + 1)
        left = max(0, int(np.floor((time-start-pd.Timedelta(minutes=5)).total_seconds()*rate)) + 1)
        row = waveform_features(values[left:right], rate, kind)
        row.update(time=time, **{f'{kind}_input_end': min(time, end)})
        rows.append(row)
    return rows


def extract_e4(z, anchors, kind, suffix, offset):
    rows = []
    for name in sorted(n for n in z.namelist() if n.endswith('/'+suffix)):
        with z.open(name) as stream:
            first = float(stream.readline().decode().split(',')[0])
            rate = float(stream.readline().decode().split(',')[0])
            try:
                values = pd.read_csv(stream, header=None).to_numpy(dtype=float)
            except pd.errors.EmptyDataError:
                continue
        if values.shape[1] == 1:
            values = values[:,0]
        rows.extend(source_windows(values, first, rate, anchors, kind, offset))
    return feature_frame(rows, kind)


def feature_frame(rows, kind):
    if not rows:
        return pd.DataFrame(index=pd.DatetimeIndex([], name='time'))
    frame = pd.DataFrame(rows).set_index('time')
    # Overlapping source sessions are resolved by sample completeness, never by labels.
    frame = frame.sort_values(f'{kind}_completeness',ascending=False)
    return frame[~frame.index.duplicated(keep='first')].sort_index()


def extract_ecg(z, anchors):
    rows, audit = [], []
    rate = 250.
    for name in sorted(n for n in z.namelist() if n.endswith('_ECG.csv')):
        retained, retained_start, source_start, source_count = np.empty(0), None, None, 0
        next_anchor = 0
        candidates = None
        file_ok = True
        file_rows = []
        for chunk in pd.read_csv(z.open(name), usecols=['Time','EcgWaveform'], chunksize=250000):
            first = pd.Timestamp(datetime.strptime(str(chunk.Time.iloc[0]), '%d/%m/%Y %H:%M:%S.%f'))
            last = pd.Timestamp(datetime.strptime(str(chunk.Time.iloc[-1]), '%d/%m/%Y %H:%M:%S.%f'))
            if source_start is None:
                source_start = first
                candidates = anchors[anchors >= first + pd.Timedelta(minutes=5)]
            expected_first = source_start + pd.Timedelta(seconds=source_count/rate)
            expected_last = first + pd.Timedelta(seconds=(len(chunk)-1)/rate)
            if abs((first-expected_first).total_seconds()) > .006 or abs((last-expected_last).total_seconds()) > .006:
                file_ok = False
                break
            raw = chunk.EcgWaveform.to_numpy(dtype=float)
            start = retained_start if len(retained) else first
            values = np.concatenate([retained,raw])
            while next_anchor < len(candidates) and candidates[next_anchor] <= last:
                time = candidates[next_anchor]
                left = max(0,int(np.floor((time-start-pd.Timedelta(minutes=5)).total_seconds()*rate))+1)
                right = min(len(values),int(np.floor((time-start).total_seconds()*rate))+1)
                row = waveform_features(values[left:right],rate,'ecg')
                row.update(time=time,ecg_input_end=time)
                file_rows.append(row)
                next_anchor += 1
            keep = min(len(values),int(rate*301))
            retained = values[-keep:]
            retained_start = start + pd.Timedelta(seconds=(len(values)-keep)/rate)
            source_count += len(chunk)
        audit.append({'member':name,'sample_clock_check':file_ok,'samples_checked':source_count})
        if file_ok:
            rows.extend(file_rows)
        print('ECG source',name.split('/')[-1], 'clock_ok',file_ok,flush=True)
    return feature_frame(rows,'ecg'), audit


def extract_subject(path, clock_report):
    if not clock_report['clock_resolved_by_sensor_check']:
        raise ValueError('Unresolved source clock; do not fuse signals')
    cgm = read_cgm(path)
    first = pd.Timestamp(clock_report['zephyr_first']) + pd.Timedelta(minutes=5)
    last = pd.Timestamp(clock_report['zephyr_last'])
    frame = cgm.loc[first:last].copy()
    anchors = frame.index
    offset = clock_report['best_clock_candidate']['shift_hours']
    with ZipFile(path) as z:
        for kind,suffix in [('ppg','BVP.csv'),('acc','ACC.csv'),('eda','EDA.csv'),('temp','TEMP.csv')]:
            result = extract_e4(z,anchors,kind,suffix,offset)
            frame = frame.join(result)
            print(path.stem,kind,'windows',len(result),flush=True)
        ecg, clock = extract_ecg(z,anchors)
        frame = frame.join(ecg)
    frame['subject'] = path.name.removesuffix('_raw.zip')
    frame['label_low'] = frame.label_proxy_mg_dl < 70
    frame['label_very_low'] = frame.label_proxy_mg_dl < 54
    frame['decision_time'] = frame.index
    for col in [c for c in frame if c.endswith('_input_end')]:
        if (frame[col].dropna() > frame.loc[frame[col].notna(),'decision_time']).any():
            raise AssertionError('Future signal input')
    return frame.reset_index(), clock

