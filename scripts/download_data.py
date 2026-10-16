"""Download public source files without publishing participant records."""
import argparse
import hashlib
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
BRIS_PAGE = 'https://data.bris.ac.uk/data/dataset/8dfdea4e24c4b90e6f044cadf612c477'
FIGSHARE = 'https://api.figshare.com/v2/articles/28136294'


def download(item, folder):
    destination = folder / item['name']
    expected = item.get('md5')
    if destination.exists():
        actual = hashlib.file_digest(destination.open('rb'), 'md5').hexdigest()
        if (not expected or actual == expected) and (not item.get('size') or destination.stat().st_size == item['size']):
            return dict(item, sha256=hashlib.file_digest(destination.open('rb'), 'sha256').hexdigest(), local=str(destination.relative_to(ROOT)))
    temporary = destination.with_suffix(destination.suffix + '.partial')
    required = item.get('size', 0)
    if required and shutil.disk_usage(folder).free < required + 2_000_000_000:
        raise RuntimeError(f'Insufficient disk headroom for {item["name"]}')
    for attempt in range(3):
        try:
            with requests.get(item['url'], stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                md5, sha = hashlib.md5(), hashlib.sha256()
                with temporary.open('wb') as stream:
                    for chunk in response.iter_content(2**20):
                        if chunk:
                            stream.write(chunk)
                            md5.update(chunk)
                            sha.update(chunk)
            if expected and md5.hexdigest() != expected:
                raise ValueError(f'Checksum mismatch: {item["name"]}')
            if required and temporary.stat().st_size != required:
                raise ValueError(f'Size mismatch: {item["name"]}')
            temporary.replace(destination)
            print(f'Downloaded {item["name"]} ({destination.stat().st_size} bytes)', flush=True)
            return dict(item, sha256=sha.hexdigest(), local=str(destination.relative_to(ROOT)))
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=['brist1d', 'physiocgm', 'smartwatch_hypo'], required=True)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    folder = ROOT / 'data' / 'raw' / args.dataset
    folder.mkdir(parents=True, exist_ok=True)
    if args.dataset == 'brist1d':
        response = requests.get(BRIS_PAGE, timeout=45)
        response.raise_for_status()
        urls = sorted(set(urljoin(BRIS_PAGE, x) for x in re.findall(r'href=["\']([^"\']+P\d+\.csv)["\']', response.text)))
        items = [{'name': Path(urlparse(url).path).name, 'url': url} for url in urls if urlparse(url).hostname == 'data.bris.ac.uk']
        if len(items) != 20:
            raise ValueError(f'Expected 20 source CSV links; found {len(items)}. Audit source changes.')
    elif args.dataset == 'physiocgm':
        response = requests.get(FIGSHARE, timeout=45)
        response.raise_for_status()
        metadata = response.json()
        (folder / 'source_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        items = [{'name': f['name'], 'url': f['download_url'], 'size': f['size'], 'md5': f.get('computed_md5')} for f in metadata['files'] if f['name'].endswith('_raw.zip')]
        if len(items) != 10:
            raise ValueError(f'Expected 10 raw subject archives, found {len(items)}')
    else:
        response=requests.get('https://zenodo.org/api/records/15309060',timeout=45)
        response.raise_for_status();metadata=response.json()
        if metadata['metadata'].get('license',{}).get('id')!='cc-by-4.0':
            raise ValueError('Unexpected source license; re-audit source terms')
        (folder/'source_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        items=[{'name':f['key'],'url':f['links']['self'],'size':f['size'],'md5':f['checksum'].removeprefix('md5:')} for f in metadata['files'] if re.fullmatch(r'\d{2}\.csv',f['key'])]
        if len(items)!=11:raise ValueError(f'Expected 11 processed participant CSVs, found {len(items)}')
    if args.limit:
        items = items[:args.limit]
    manifest_path = folder / 'download_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else []
    records = {x['name']: x for x in previous}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for item in pool.map(lambda item: download(item, folder), items):
            records[item['name']] = item
            manifest_path.write_text(json.dumps(list(records.values()), indent=2), encoding='utf-8')
    print(f'{len(items)} files verified; raw files remain git-ignored.', flush=True)


if __name__ == '__main__':
    main()
