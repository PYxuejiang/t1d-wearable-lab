"""Optional ranged recovery for a slow/interrupted verified public raw download."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--file',required=True);p.add_argument('--workers',type=int,default=4)
    args=p.parse_args();folder=ROOT/'data/raw/physiocgm'
    metadata=json.loads((folder/'source_metadata.json').read_text())
    item=next(f for f in metadata['files'] if f['name']==args.file and f['name'].endswith('_raw.zip'))
    destination=folder/item['name'];temporary=destination.with_suffix('.zip.partial')
    if destination.exists():raise RuntimeError('Verified file already exists; use normal downloader to validate manifest')
    offset=temporary.stat().st_size if temporary.exists() else 0
    chunks=[(start,min(start+64*1024**2,item['size'])-1) for start in range(offset,item['size'],64*1024**2)]
    def fetch(bounds):
        a,b=bounds;part=folder/f'{item["name"]}.{a}-{b}.part'
        if part.exists() and part.stat().st_size==b-a+1:return part
        with requests.get(item['download_url'],headers={'Range':f'bytes={a}-{b}'},stream=True,timeout=(20,120)) as r:
            r.raise_for_status()
            if r.status_code!=206 or r.headers.get('Content-Range')!=f'bytes {a}-{b}/{item["size"]}':
                raise RuntimeError('Server did not honor exact requested range')
            with part.open('wb') as stream:
                for block in r.iter_content(2**20):stream.write(block)
        if part.stat().st_size!=b-a+1:raise RuntimeError('Incomplete range')
        print('Verified range size',a,b,flush=True);return part
    with ThreadPoolExecutor(max_workers=args.workers) as pool:parts=list(pool.map(fetch,chunks))
    with temporary.open('ab') as target:
        for part in parts:
            with part.open('rb') as source:
                while block:=source.read(2**20):target.write(block)
    if temporary.stat().st_size!=item['size']:raise RuntimeError('Size mismatch')
    with temporary.open('rb') as stream:actual=hashlib.file_digest(stream,'md5').hexdigest()
    if actual!=item['computed_md5']:raise RuntimeError('Full-source checksum mismatch')
    temporary.replace(destination)
    # Only successful temporary range fragments from this named file are removed.
    for part in parts:part.unlink()
    print('Source MD5 verified; recovered',destination.name,flush=True)


if __name__=='__main__':main()
