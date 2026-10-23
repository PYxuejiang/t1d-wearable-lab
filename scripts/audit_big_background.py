"""Verify downloaded BIG IDEAs metadata; do not claim full waveform pairing."""
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

root = Path(__file__).resolve().parents[1]
cache = root / 'outputs/multimodal_source_v1'
expected = {'big_demographics.csv': '995ece21fd29be689c67aee8fd22659dea6755a28c4f84e07c28605fef80b9ac',
            'big_license.txt': '86c0ad300f6d380591298bc03652e30b81f65954bbf22435812bcfd46812ab06'}
for name, digest in expected.items():
    if hashlib.sha256((cache / name).read_bytes()).hexdigest() != digest:
        raise ValueError('Official metadata checksum mismatch')
data = pd.read_csv(cache / 'big_demographics.csv')
ids = {int(value) for value in re.findall(r'href="(\d{3})/(?:#files-panel)?"', (cache / 'bigideas_index.html').read_text(encoding='utf-8'))}
if data.ID.duplicated().any() or set(data.ID) != ids:
    raise ValueError('Demographic and directory IDs do not match')
sample_files = re.findall(r'href="([^"/]+\.csv)"', (cache / 'big_001_index.html').read_text(encoding='utf-8'))
result = {'dataset': 'BIG IDEAs glycemic wearable 1.1.2',
          'url': 'https://physionet.org/content/big-ideas-glycemic-wearable/1.1.2/',
          'license': 'ODC-By', 'metadata_sha256': expected,
          'demographic_rows': len(data), 'matching_subject_directories': len(ids),
          'columns': list(data.columns), 'age_column_present': False,
          'sample_directory_channels': sorted(name.split('_')[0] for name in sample_files),
          'waveform_content_audited': False, 'background_available_at_verified': False,
          'training_admitted': False,
          'limits': ['Metadata IDs match directories; full BVP/CGM time alignment remains unverified.',
                     'No per-person age in this file.', 'Population is not this T1D cohort.',
                     'HbA1c must not become target leakage; observation time needs verification.']}
destination = root / 'docs/acceptance/BIG_BACKGROUND_SOURCE1.json'
destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
