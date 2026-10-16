import importlib.util
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score

spec=importlib.util.spec_from_file_location('verify_smartwatch',Path(__file__).parents[1]/'scripts/verify_smartwatch_replication.py')
verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)


def test_tied_probabilities_are_grouped_in_independent_ap():
    truth=np.array([0,1,0,1,1,0,1]);scores=np.array([.2,.2,.9,.4,.4,.9,.2])
    r=verifier.independent_metrics(truth,scores,.4)
    assert abs(r['ap']-average_precision_score(truth,scores))<1e-12
    assert abs(r['roc_auc']-roc_auc_score(truth,scores))<1e-12
    assert (r['tp'],r['fn'],r['fp'],r['tn'])==(2,2,2,1)
