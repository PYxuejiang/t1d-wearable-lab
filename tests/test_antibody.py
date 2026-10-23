import gzip

import numpy as np
import pytest

from t1d_lab.antibody import read_gse45515


def sample(accession, title, label, table='1\t1.0\n2\tnull'):
    return (f'^SAMPLE = {accession}\n!Sample_title = {title}\n'
            f'!Sample_characteristics_ch1 = disease state: {label}\n'
            f'!sample_table_begin\nID_REF\tVALUE\n{table}\n!sample_table_end\n')


def source(tmp_path, text):
    path = tmp_path / 'source.gz'
    with gzip.open(path, 'wt') as f:
        f.write(text)
    return path


def test_title_family_blocks_even_different_disease_labels(tmp_path):
    path = source(tmp_path, sample('GSM1', 'Patient8a', 'T1D') + sample('GSM2', 'Control8b', 'Control'))
    x, y, groups, ids, features, titles = read_gse45515(path)
    assert groups.tolist() == ['8', '8']
    assert y.tolist() == [1, 0]
    assert np.isnan(x[:, 1]).all()
    assert features == ['1', '2']


@pytest.mark.parametrize('text,expected', [
    (sample('GSM1', 'Patient1a', 'Control'), 'disagree'),
    (sample('GSM1', 'Patient1a', 'T1D', '1\t0\n2\t1'), 'positive'),
    (sample('GSM1', 'Patient1a', 'T1D', '1\t1\n1\t2'), 'Repeated'),
    (sample('GSM1', 'Patient1a', 'T1D') * 2, 'duplicate'),
    (sample('GSM1', 'Patient1a', 'T1D') + sample('GSM2', 'Patient2a', 'T1D', '2\t1\n1\t2'), 'order'),
])
def test_invalid_array_metadata_cannot_silently_train(tmp_path, text, expected):
    with pytest.raises(ValueError, match=expected):
        read_gse45515(source(tmp_path, text))
