import ast,hashlib,json,os
from pathlib import Path
from urllib.parse import quote
import requests
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'outputs/segade_source_audit_v1';out.mkdir(parents=True,exist_ok=True)
if (out/'source_metadata.json').exists():raise RuntimeError('Preserve previous audit')
api=requests.Session();api.headers.update({'Accept':'application/vnd.github+json'})
if os.environ.get('GITHUB_TOKEN'):api.headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
base='https://api.github.com/repos/chengstark/Segade'
def get(url):
    r=api.get(url,timeout=30);r.raise_for_status();return r.json()
meta=get(base);commit='f5b2ad6e180a1474bc47d6c5ec5d482edaed6797';tree=get(base+'/git/trees/'+commit+'?recursive=1');assert not tree.get('truncated')
blobs=[x for x in tree['tree'] if x['type']=='blob']
license_paths=[x['path'] for x in blobs if any(v in x['path'].lower() for v in ('license','licence','copying','notice'))]
datafiles=[x for x in blobs if x['path'].startswith('data/')]
identity_paths=[x['path'] for x in blobs if any(v in x['path'].lower() for v in ('subject','participant','metadata','mapping'))]
textfiles={}
for path in ['README.md','data_split.py','db2npy.py']+license_paths:
    url=f'https://raw.githubusercontent.com/chengstark/Segade/{commit}/{quote(path)}';r=requests.get(url,timeout=30);r.raise_for_status()
    (out/path.replace('/','__')).write_bytes(r.content)
    textfiles[path]={'sha256':hashlib.sha256(r.content).hexdigest(),'url':url,'license_keyword_lines':[i+1 for i,line in enumerate(r.text.splitlines()) if any(k in line.lower() for k in ('license','licence','copyright','permission','redistribut'))]}
headers=[]
for f in datafiles:
    if not f['path'].endswith(('/scaled_ppgs.npy','/seg_labels.npy')):continue
    url=f'https://raw.githubusercontent.com/chengstark/Segade/{commit}/{quote(f["path"])}'
    with requests.get(url,headers={'Range':'bytes=0-1023'},stream=True,timeout=30) as response:
        response.raise_for_status();prefix=response.raw.read(1024)
        entry={'path':f['path'],'git_blob_sha':f['sha'],'git_size':f['size'],'http_status':response.status_code,'prefix_sha256':hashlib.sha256(prefix).hexdigest(),'bytes_read':len(prefix)}
    if prefix[:6]==b'\x93NUMPY':
        version=tuple(prefix[6:8]);length_size=2 if version[0]==1 else 4;offset=8+length_size;length=int.from_bytes(prefix[8:offset],'little')
        assert offset+length<=len(prefix)
        header=ast.literal_eval(prefix[offset:offset+length].decode('latin1' if version[0]<3 else 'utf8').strip())
        entry.update(npy_version=list(version),header=header,header_bytes=offset+length)
        # Only persist header bytes, never waveform samples contained in the HTTP prefix.
        (out/(f['path'].replace('/','__')+'.header')).write_bytes(prefix[:offset+length])
    else:entry['format']='non-npy-or-lfs-pointer'
    headers.append(entry)
result={'repository':'https://github.com/chengstark/Segade','commit':commit,'github_license':meta['license'],'tree_truncated':False,'blob_count':len(blobs),'license_paths':license_paths,'identity_candidate_paths':identity_paths,'data_entries':[{'path':x['path'],'size':x['size'],'sha':x['sha']} for x in datafiles],'headers':headers,'text_files':textfiles}
(out/'source_metadata.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'commit':commit,'headers':len(headers),'license':meta['license']}))
