"""Nested grouped baseline. Only aggregates leave outputs/; no personal-risk endpoint."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from t1d_lab.antibody import audit_gse45515, read_gse45515, antigen_names


def metrics(y, p):
    return dict(average_precision=float(average_precision_score(y, p)),
                roc_auc=float(roc_auc_score(y, p)), brier=float(brier_score_loss(y, p)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=Path('configs/antibody_branch_v1.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(args.protocol.read_text())
    audit = audit_gse45515(args.source)
    if audit['source_sha256'] != protocol['source_sha256']:
        raise ValueError('Source hash differs from frozen protocol')
    x, y, groups, ids, features, titles = read_gse45515(args.source)
    names = antigen_names(args.source, features)
    feature_mode = protocol.get('feature_mode', 'all')
    if feature_mode not in ('all', 'annotated', 'pNA_only'):
        raise ValueError('Unknown feature scope')
    keep = np.ones(len(names), dtype=bool) if feature_mode == 'all' else (names != 'pNA' if feature_mode == 'annotated' else names == 'pNA')
    x = x[:, keep]
    audit.update(selected_features=int(keep.sum()), pNA_features=int((names == 'pNA').sum()), feature_mode=feature_mode)
    x = np.log2(x)
    outer = StratifiedGroupKFold(protocol['outer_folds'], shuffle=True, random_state=protocol['seed'])
    predictions = np.full(len(y), np.nan)
    constant = predictions.copy()
    fold_results = []
    for fold, (train, test) in enumerate(outer.split(x, y, groups)):
        assert not set(groups[train]) & set(groups[test])
        inner = list(StratifiedGroupKFold(protocol['inner_folds'], shuffle=True,
                        random_state=protocol['seed'] + fold).split(x[train], y[train], groups[train]))
        candidates = []
        def model(c):
            return make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True),
                                 StandardScaler(), LogisticRegression(C=c, max_iter=3000,
                                 solver='liblinear', random_state=protocol['seed']))
        for c in protocol['logistic_C']:
            scores = []
            for a, b in inner:
                assert not set(groups[train[a]]) & set(groups[train[b]])
                fitted = model(c).fit(x[train[a]], y[train[a]])
                scores.append(float(average_precision_score(y[train[b]], fitted.predict_proba(x[train[b]])[:, 1])))
            candidates.append({'C': c, 'inner_AP': scores, 'mean_AP': float(np.mean(scores))})
        best = max(candidates, key=lambda row: row['mean_AP'])
        predictions[test] = model(best['C']).fit(x[train], y[train]).predict_proba(x[test])[:, 1]
        constant[test] = y[train].mean()
        fold_results.append({'fold': fold, 'train_arrays': len(train), 'heldout_arrays': len(test),
                             'candidates': candidates, 'selected_C': best['C'],
                             'heldout': metrics(y[test], predictions[test])})
    if not np.isfinite(predictions).all():
        raise ValueError('Missing OOF prediction')
    rng = np.random.default_rng(protocol['seed'])
    unique = np.unique(groups)
    intervals = {key: [] for key in metrics(y, predictions)}
    differences = {key: [] for key in intervals}
    for _ in range(protocol['bootstrap_replicates']):
        idx = np.concatenate([np.flatnonzero(groups == g) for g in rng.choice(unique, len(unique), replace=True)])
        if len(set(y[idx])) < 2:
            continue
        current, base = metrics(y[idx], predictions[idx]), metrics(y[idx], constant[idx])
        for key in intervals:
            intervals[key].append(current[key])
            differences[key].append(current[key] - base[key])
    result = {'protocol': protocol, 'protocol_sha256': hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
              'audit': audit, 'oof': metrics(y, predictions), 'constant_oof': metrics(y, constant),
              'interval_95': {k: np.percentile(v, [2.5, 97.5]).tolist() for k, v in intervals.items()},
              'paired_difference_95': {k: np.percentile(v, [2.5, 97.5]).tolist() for k, v in differences.items()},
              'folds': fold_results, 'clinical_validation': False, 'patient_predictions_supported': False}
    np.savez_compressed(args.output / 'private_oof.npz', label=y, prediction=predictions,
                        constant=constant, family=groups, accession=np.array(ids))
    (args.output / 'aggregate.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'oof': result['oof'], 'constant': result['constant_oof'], 'audit': audit}, ensure_ascii=False))


if __name__ == '__main__':
    main()
