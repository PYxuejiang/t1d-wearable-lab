"""Download the fixed pilot only; verify files against source SHA256SUMS.txt."""
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
MIRROR = 'https://physionet-open.s3.amazonaws.com/mitdb/1.0.0/'


def main():
    config = json.loads((ROOT / 'configs/ecg_capture_pilot_v1.json').read_text())
    dest = ROOT / 'data/raw/mitdb_pilot'
    dest.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    response = session.get(config['source'] + 'SHA256SUMS.txt', timeout=90)
    response.raise_for_status()
    sums = {line.split()[1].lstrip('*'): line.split()[0] for line in response.text.splitlines() if len(line.split()) == 2}
    (dest / 'SHA256SUMS.txt').write_text(response.text, encoding='utf-8')
    manifest = []
    for record in config['records']:
        for ext in ['hea', 'dat', 'atr']:
            name = record + '.' + ext
            expected = sums[name]
            path = dest / name
            if not path.exists():
                # Public S3 mirror documented by PhysioNet; official main-site
                # checksums remain authoritative. No cloud credentials required.
                item = session.get(MIRROR + name, timeout=90)
                item.raise_for_status()
                path.write_bytes(item.content)
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError('Source checksum mismatch: ' + name)
            manifest.append({'file': name, 'bytes': path.stat().st_size, 'sha256': actual,
                             'source_sha256_verified': True})
            print(name, path.stat().st_size, 'verified', flush=True)
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
