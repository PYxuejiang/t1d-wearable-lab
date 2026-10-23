"""GEO antibody arrays are a separate assay branch, never wearable pseudo-features."""
import gzip
import hashlib
import io
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


def read_gse45515(path):
    text = gzip.open(path, 'rt', encoding='utf-8').read()
    arrays, labels, ids, families, features = [], [], [], [], None
    titles = []
    for block in text.split('^SAMPLE = ')[1:]:
        accession = block.splitlines()[0].strip()
        meta, body = block.split('!sample_table_begin\n', 1)
        title = re.search(r'^!Sample_title = (.+)$', meta, re.M).group(1).strip()
        state = re.search(r'disease state: ([^\r\n]+)', meta).group(1).strip()
        match = re.fullmatch(r'(Patient|Control)(\d+)[ab]?', title)
        if not match or state not in ('T1D', 'Control'):
            raise ValueError('Unknown sample title or disease label')
        label = int(state == 'T1D')
        if label != int(match[1] == 'Patient'):
            raise ValueError('Title and sample label disagree')
        table = pd.read_csv(io.StringIO(body.split('!sample_table_end')[0]),
                            sep='\t', na_values=['null'], dtype={'ID_REF': str})
        if table.ID_REF.duplicated().any():
            raise ValueError('Repeated features within an array')
        current = table.ID_REF.tolist()
        if features is not None and current != features:
            raise ValueError('Array feature order mismatch')
        features = current
        arrays.append(pd.to_numeric(table.VALUE, errors='raise').to_numpy(float))
        labels.append(label)
        ids.append(accession)
        titles.append(title)
        # Conservative title-family blocking, NOT a verified donor identity.
        families.append(match[2])
    if not arrays or len(set(ids)) != len(ids):
        raise ValueError('Empty or duplicate sample accession')
    x = np.stack(arrays)
    if np.isinf(x).any() or (x[np.isfinite(x)] <= 0).any():
        raise ValueError('Expected positive median-normalized assay intensities')
    return x, np.array(labels), np.array(families), ids, features, titles


def audit_gse45515(path):
    x, y, groups, ids, features, titles = read_gse45515(path)
    multiplicity = Counter(Counter(groups).values())
    mixed = sum(len(set(y[groups == g])) > 1 for g in set(groups))
    return {
        'dataset': 'GSE45515', 'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'arrays': len(y), 'features': x.shape[1],
        'sample_labels': {'T1D': int(y.sum()), 'Control': int((y == 0).sum())},
        'overview_labels': {'T1D': 74, 'Control': 75},
        'overview_count_discrepancy': True,
        'missing_values': int(np.isnan(x).sum()),
        'exact_duplicate_array_rows': int(pd.DataFrame(x).duplicated().sum()),
        'title_family_groups': len(set(groups)),
        'group_sizes': {str(k): v for k, v in sorted(multiplicity.items())},
        'mixed_label_title_families': mixed,
        'donor_identity_verified': False, 'wearable_pairing': False,
        'scope': 'exploratory-array-classification-only',
        'limitations': ['Title families are conservative blocks, not confirmed donors.',
                        'Series overview and sample label counts disagree.',
                        'T1D vs control is not current hypoglycemia.',
                        'Source-normalized intensities; upstream batch handling is not independently reproduced.'],
    }


def antigen_names(path, feature_ids):
    text = gzip.open(path, 'rt', encoding='utf-8').read()
    table = pd.read_csv(io.StringIO(text.split('!platform_table_begin\n')[1]
                                   .split('!platform_table_end')[0]), sep='\t', dtype=str)
    if table.ID.duplicated().any():
        raise ValueError('Duplicate platform feature ID')
    mapping = table.set_index('ID').ORF.to_dict()
    if set(feature_ids) != set(mapping):
        raise ValueError('Platform and array feature IDs differ')
    return np.array([mapping[key] for key in feature_ids])
