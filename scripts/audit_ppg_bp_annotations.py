"""Audit the pinned author annotation archive without publishing individual records."""
import collections
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/ppg_bp_annot/PPG-BP_annot.zip'
    raw = path.read_bytes()
    assert hashlib.md5(raw).hexdigest() == '1b03371ca9cfad39ab7209425673b351'
    groups = collections.Counter(); annotations = []; signals = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = [f for f in archive.infolist() if not f.is_dir()]
        for file in files:
            if not file.filename.endswith('.mat'): continue
            content = loadmat(io.BytesIO(archive.read(file.filename)), simplify_cells=True)
            groups[','.join(sorted(k for k in content if not k.startswith('__')))] += 1
            if 'fiducial_annot' in content: annotations.append(content['fiducial_annot'])
            if 'ppg_data' in content: signals = content['ppg_data']
    assert len(signals) == 219 and len(annotations) == 2
    names = {r['name'] for r in signals}
    assert len(names) == 219
    assert all(len(a) == 219 and {r['name'] for r in a} == names for a in annotations)
    assert all(np.isfinite(r['sig']).all() for r in signals)
    durations = [len(r['sig']) / r['fs'] for r in signals]
    public = {'stage': 'PPG_BP_ANNOT_SOURCE1', 'scope': 'Acquisition and schema audit only; no algorithm scoring',
              'record_url': 'https://zenodo.org/records/10523285', 'pinned_version': 'v1',
              'file': path.name, 'bytes': len(raw), 'md5': hashlib.md5(raw).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest(),
              'record_license': 'CC-BY-4.0', 'license_source': 'https://zenodo.org/api/records/10523285',
              'archive_files': len(files), 'mat_schema_counts': dict(groups), 'signal_entries': len(signals),
              'annotation_collections': len(annotations), 'entries_per_collection': [len(a) for a in annotations],
              'unique_names_and_cross_collection_join': True,
              'sampling_rates_hz': sorted({int(r['fs']) for r in signals}),
              'duration_seconds_min_max': [min(durations), max(durations)],
              'all_signal_samples_finite': True,
              'annotation_fields': sorted(set.intersection(*[set(r['annot']) for a in annotations for r in a])),
              'pending': ['Annotation index/time conventions and manual preprocessing', 'Label completeness and inter-annotator disagreement', 'Short-segment protocol; current 30-second detector is not directly applicable', 'Origin and acquisition-site applicability to wrist PPG'],
              'audit_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT / 'docs/acceptance/PPG_BP_ANNOT_SOURCE1.json').write_text(json.dumps(public, indent=2))
    print(json.dumps(public, indent=2))


if __name__ == '__main__':
    main()
