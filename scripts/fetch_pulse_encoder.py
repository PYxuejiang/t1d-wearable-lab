"""Fetch pinned public MIT sources and weights; never execute downloaded code."""
import hashlib
from pathlib import Path
from zipfile import ZipFile

import requests

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '716eaf9cf966e8f76436f2263872ef38b1f90166'
ARCH = 'pulseppg/nets/ResNet1D/ResNet1D_Net.py'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    folder = ROOT / 'outputs/multimodal_source_v1'
    folder.mkdir(parents=True, exist_ok=True)
    arch = ROOT / 'outputs/pulseppg_source' / ARCH
    arch.parent.mkdir(parents=True, exist_ok=True)
    if not arch.exists():
        response = requests.get(f'https://raw.githubusercontent.com/maxxu05/pulseppg/{COMMIT}/{ARCH}', timeout=90)
        response.raise_for_status()
        canonical = response.content.replace(b'\r\n', b'\n')
        if hashlib.sha256(canonical).hexdigest() != '53ec9d38c0017f2bbea09cf121c7432fd9933d3ba69e721eabad1d6962166e81':
            raise ValueError('Unreviewed upstream architecture')
        # Reproduce the audited Windows checkout bytes on every OS; semantics unchanged.
        arch.write_bytes(canonical.replace(b'\n', b'\r\n'))
    if digest(arch) != '0b88a90b2a9c1a419090bbb7375a0643adba5b925db0215529b40074657b5c79':
        raise ValueError('Existing architecture differs; do not overwrite it')
    license_path = folder / 'pulse_license.txt'
    if not license_path.exists():
        response = requests.get(f'https://raw.githubusercontent.com/maxxu05/pulseppg/{COMMIT}/LICENSE', timeout=90)
        response.raise_for_status()
        license_path.write_bytes(response.content)
    archive = folder / 'pulseppg_model_weights.zip'
    expected = '5685093114036e9ceb720b98342d68188c8786ed4e48466aa608a325cd890918'
    if not archive.exists():
        partial = folder / 'pulseppg_model_weights.zip.part'
        with requests.get('https://zenodo.org/api/records/17345536/files/pulseppg_model_weights.zip/content',
                          stream=True, timeout=(30, 120)) as response:
            response.raise_for_status()
            with partial.open('wb') as output:
                for chunk in response.iter_content(1024 * 1024):
                    output.write(chunk)
        if digest(partial) != expected:
            raise ValueError('Archive checksum failed; partial retained for inspection')
        partial.replace(archive)
    if digest(archive) != expected:
        raise ValueError('Existing archive checksum failed; do not overwrite it')
    checkpoint = folder / 'pulseppg_checkpoint.pt'
    if not checkpoint.exists():
        with ZipFile(archive) as z, checkpoint.open('xb') as output:
            with z.open('pulseppg/experiments/out/pulseppg/checkpoint_best.pkl') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    output.write(chunk)
    if digest(checkpoint) != '485ade5033b3baa9b82e252fc131042dda897d7bdfc0d1a030d9746a1e98857c':
        raise ValueError('Checkpoint checksum failed')
    print('Pinned archive, architecture and checkpoint verified; no model code executed.')


if __name__ == '__main__':
    main()
