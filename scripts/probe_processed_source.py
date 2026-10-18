"""Bounded remote ZIP-member probe. Downloads bytes; does not execute pickle code."""
import argparse
import hashlib
import io
import json
import struct
import sys
import zlib
from pathlib import Path
from zipfile import ZipFile
import requests

ROOT = Path(__file__).resolve().parents[1]


class RemoteZip(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.session = requests.Session()
        self.cache = []
        self.downloaded = 0

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        if self.pos < 0: raise ValueError('Negative seek')
        return self.pos

    def tell(self): return self.pos
    def seekable(self): return True

    def read(self, n=-1):
        end = self.size if n < 0 else min(self.size, self.pos+n)
        if end <= self.pos: return b''
        if end-self.pos > 16*1024**2: raise ValueError('Unexpected large range')
        for start, stop, payload in self.cache:
            if start <= self.pos and end <= stop:
                data = payload[self.pos-start:end-start]; self.pos=end; return data
        start, stop = self.pos, min(self.size, max(end, self.pos+65536))
        r = self.session.get(self.url, headers={'Range':f'bytes={start}-{stop-1}'}, timeout=(20,45), stream=True)
        try:
            r.raise_for_status()
            if r.status_code != 206 or r.headers.get('Content-Range') != f'bytes {start}-{stop-1}/{self.size}':
                raise ValueError('Exact bounded range not honored')
            data = r.content
        finally: r.close()
        if len(data) != stop-start: raise ValueError('Incomplete range')
        self.downloaded += len(data)
        self.cache.append((start,stop,data)); self.pos=end
        return data[:end-start]


def main(subject):
    dest=ROOT/'outputs/source_audit_v1';dest.mkdir(exist_ok=True)
    metadata=json.loads((ROOT/'data/raw/physiocgm/source_metadata.json').read_text())
    item=next(x for x in metadata['files'] if x['name']==subject+'_processed.zip')
    if (dest/f'{subject}_probe.json').exists():
        print(subject,'already probed'); return
    stream=RemoteZip(item['download_url'],item['size'])
    with ZipFile(stream) as z:
        members=[x for x in z.infolist() if x.filename.endswith('.pkl') and Path(x.filename).stem.isdigit()]
        member=min(members,key=lambda x:(int(Path(x.filename).stem),x.filename))
        if member.file_size>16*1024**2: raise ValueError('Unexpected large member')
        payload=z.read(member)  # zipfile verifies the member CRC
    (dest/f'{subject}_probe.pkl').write_bytes(payload)
    record={'subject':subject,'source_url':item['download_url'],'archive_expected_md5':item['computed_md5'],
            'full_archive_verified':False,'member':member.filename,'member_count':len(members),
            'member_crc32':member.CRC,'member_sha256':hashlib.sha256(payload).hexdigest(),
            'http_bytes_downloaded':stream.downloaded,'selection':'first numeric member, no glucose selection'}
    (dest/f'{subject}_probe.json').write_text(json.dumps(record,indent=2))
    print(subject,'range/CRC verified',stream.downloaded,'bytes',len(payload),'uncompressed',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('subject');main(p.parse_args().subject)
