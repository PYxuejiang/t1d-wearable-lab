"""Causal tabular forecasting features and frozen held-out comparisons."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from threadpoolctl import threadpool_limits

from .brist1d import backward_values, read_subject, trailing_sum
from .evaluation import nearest_future_reference, split_masks

CGM_FEATURES = [f'bg_lag_{lag}' for lag in (0, 5, 15, 30, 45, 60)] + ['bg_mean_60', 'bg_std_60', 'hour_sin', 'hour_cos']
CONTEXT_FEATURES = CGM_FEATURES + [f'{key}_sum_{minutes}' for key in ('insulin', 'carbs') for minutes in (15, 30, 60)]
FUSION_FEATURES = CONTEXT_FEATURES + [f'{key}_current' for key in ('hr', 'steps', 'dist', 'cals')]
GROUPS = {'cgm': CGM_FEATURES, 'context': CONTEXT_FEATURES, 'fusion': FUSION_FEATURES}


def subject_features(path):
    channels, report = read_subject(path)
    glucose = channels['bg']
    times = glucose.index
    frame = pd.DataFrame(index=times)
    for lag in (0, 5, 15, 30, 45, 60):
        # No lag observation can precede the declared 60-minute history boundary.
        frame[f'bg_lag_{lag}'] = backward_values(glucose, times - pd.Timedelta(minutes=lag), min(20, 60 - lag))
    frame['bg_mean_60'] = glucose.rolling('60min', closed='both').mean()
    frame['bg_std_60'] = glucose.rolling('60min', closed='both').std()
    hour = times.hour + times.minute / 60
    frame['hour_sin'], frame['hour_cos'] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    for key in ('insulin', 'carbs'):
        for minutes in (15, 30, 60):
            frame[f'{key}_sum_{minutes}'] = trailing_sum(channels[key], times, minutes)
    for key in ('hr', 'steps', 'dist', 'cals'):
        frame[f'{key}_current'] = backward_values(channels[key], times, 10)
    frame['target'], target_times = nearest_future_reference(glucose, times)
    frame['target_time'] = target_times
    frame['subject'] = report['subject']
    frame['decision_time'] = times
    frame['input_max_time'] = times
    frame['history_start'] = times - pd.Timedelta(minutes=60)
    frame['split'] = 'purged'
    for split, mask in split_masks(times, times[0], times[-1]).items():
        frame.loc[mask, 'split'] = split
    frame['nominal_minutes'] = report['nominal_cgm_minutes']
    frame['wearable_available'] = frame['hr_current'].notna()
    return frame.reset_index(drop=True), report


def build_features(root):
    frames, audit = [], []
    for path in sorted((root / 'data/raw/brist1d').glob('P*.csv')):
        frame, report = subject_features(path)
        frames.append(frame)
        audit.append({'subject': report['subject'], 'anchors': len(frame), 'observed_targets': int(frame.target.notna().sum()),
                      'purged': int(frame.split.eq('purged').sum()), 'targets_with_wearable': int((frame.target.notna() & frame.wearable_available).sum())})
    result = pd.concat(frames, ignore_index=True)
    if (result.input_max_time > result.decision_time).any():
        raise AssertionError('Future input')
    if (result.loc[result.target.notna(), 'target_time'] <= result.loc[result.target.notna(), 'decision_time']).any():
        raise AssertionError('Nonfuture forecasting target')
    destination = root / 'data/processed'
    destination.mkdir(exist_ok=True, parents=True)
    result.to_parquet(destination / 'brist1d_features.parquet', index=False)
    (root / 'outputs/audit/brist1d_feature_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    return result


def metric_rows(predictions):
    rows = []
    for (protocol, subject, model), g in predictions.groupby(['protocol', 'subject', 'model']):
        error = g.prediction - g.target
        low = g.target < 3.9
        rows.append({'protocol': protocol, 'subject': subject, 'model': model, 'n': len(g),
                     'mae': float(np.mean(abs(error))), 'rmse': float(np.sqrt(np.mean(error ** 2))),
                     'bias': float(np.mean(error)), 'p90_absolute_error': float(np.quantile(abs(error), .9)),
                     'low_target_n': int(low.sum()), 'low_target_mae': float(abs(error[low]).mean()) if low.any() else None})
    return pd.DataFrame(rows)


def paired_bootstrap(rows, base, other, seed=20261016, repetitions=2000):
    table = rows.pivot(index='subject', columns='model', values='mae')[[base, other]].dropna()
    difference = table[base].to_numpy() - table[other].to_numpy()
    rng = np.random.default_rng(seed)
    boot = difference[rng.integers(0, len(difference), size=(repetitions, len(difference)))].mean(axis=1)
    gain = float(100 * difference.mean() / table[base].mean())
    interval = [float(np.quantile(boot, q)) for q in (.025, .975)]
    return {'baseline': base, 'comparison': other, 'paired_subjects': len(table),
            'mae_difference_mmol_l': float(difference.mean()), 'relative_mae_improvement_percent': gain,
            'mae_difference_95_interval': interval, 'subjects_improved': int((difference > 0).sum()),
            'effect_status': 'passed' if gain >= 5 and interval[0] > 0 else 'inconclusive' if interval[0] <= 0 <= interval[1] else 'failed'}


def run_forecast(root, protocols=('temporal', 'loso'), max_subjects=None):
    destination = root / 'outputs/module1_forecasting'
    destination.mkdir(parents=True, exist_ok=True)
    features_path = root / 'data/processed/brist1d_features.parquet'
    data = pd.read_parquet(features_path) if features_path.exists() else build_features(root)
    all_subjects = sorted(data.subject.unique())
    subjects = all_subjects[:max_subjects] if max_subjects else all_subjects
    output = []
    with threadpool_limits(limits=2):
        for protocol in protocols:
            for subject in subjects:
                # Outer held-out predictions only. Inner chronological validation is reserved.
                train_mask = data.split.eq('train') & (data.subject.eq(subject) if protocol == 'temporal' else data.subject.ne(subject))
                test_mask = data.subject.eq(subject) & (data.split.eq('test') if protocol == 'temporal' else data.split.ne('purged'))
                train = data[train_mask & data.target.notna()]
                test = data[test_mask & data.target.notna()].copy()
                if len(train) < 100 or len(test) < 100:
                    raise ValueError(f'Insufficient eligible samples {protocol}/{subject}')
                test['anchor_id'] = subject + ':' + test.decision_time.astype(str)
                essential = ['subject', 'decision_time', 'input_max_time', 'history_start', 'target_time', 'target', 'anchor_id', 'wearable_available']
                for name in ('persistence', 'trend', *GROUPS):
                    if name == 'persistence':
                        predicted = test.bg_lag_0.to_numpy()
                    elif name == 'trend':
                        previous = test.bg_lag_15.fillna(test.bg_lag_0)
                        predicted = np.clip(test.bg_lag_0 + (test.bg_lag_0 - previous) * 2, 0, 40).to_numpy()
                    else:
                        columns = GROUPS[name]
                        model = HistGradientBoostingRegressor(max_iter=80, max_leaf_nodes=15, learning_rate=.08,
                                                              l2_regularization=1, early_stopping=False, random_state=20261016)
                        model.fit(train[columns], train.target)
                        predicted = model.predict(test[columns])
                    result = test[essential].copy()
                    result['prediction'], result['model'], result['protocol'] = predicted, name, protocol
                    output.append(result)
                print(protocol, subject, f'train={len(train)} test={len(test)}', flush=True)
                # Persist progress; repeated invocations create a fresh deterministic run.
                pd.concat(output, ignore_index=True).to_parquet(destination / 'predictions.parquet', index=False)
    predictions = pd.concat(output, ignore_index=True)
    rows = metric_rows(predictions)
    rows.to_csv(destination / 'metrics_by_subject.csv', index=False)
    summary = {'task': '30-minute observed-reference glucose forecasting', 'unit': 'mmol/L',
               'model': 'fixed HistGradientBoostingRegressor; 80 iterations, 15 leaves, no test tuning',
               'predictive_effect_is_not_clinical_acceptance': True, 'results': {}}
    for protocol, g in rows.groupby('protocol'):
        means = g.groupby('model')[['mae', 'rmse', 'bias']].mean().to_dict(orient='index')
        # Source baseline preference is declared before inspecting test values; both are reported.
        comparisons = [paired_bootstrap(g, base, other) for base, other in [('persistence', 'cgm'), ('context', 'fusion')]]
        summary['results'][protocol] = {'subject_equal_metrics': means, 'comparisons': comparisons}
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary

