"""Offline metadata admission audit; exports aggregates, not subject records."""
import csv, hashlib, json, re
from collections import Counter
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'outputs/but_source_v1'
    manifest=json.loads((folder/'download_manifest.json').read_text())
    checksums={}
    for line in (folder/'SHA256SUMS.txt').read_text().splitlines():
        digest,name=line.split(maxsplit=1);checksums[name.strip().lstrip('*')]=digest
    checked=[]
    for name,item in manifest.items():
        assert sha(folder/name)==item['sha256']
        if name!='SHA256SUMS.txt':
            assert checksums[name]==item['sha256'],name
            checked.append(name)
    assert (folder/'LICENSE.txt').read_text().startswith('Creative Commons Attribution 4.0')
    q=pd.read_csv(folder/'quality-hr-ann.csv',dtype={'ID':str})
    context=pd.read_csv(folder/'subject-info.csv',dtype={'ID':str,'Motion':str})
    assert list(q.columns)==['ID','Quality','HR']
    assert len(q)==3888 and len(context)==len(q)
    assert not q.ID.duplicated().any() and not context.ID.duplicated().any()
    assert q.ID.str.fullmatch(r'\d{6}').all()
    assert not q.isna().any().any() and set(q.Quality)=={0,1} and (q.HR>0).all()
    assert set(q.ID)==set(context.ID)
    record_ids=[s.split('/')[0] for s in (folder/'RECORDS.txt').read_text().splitlines() if s.endswith('_PPG')]
    assert len(record_ids)==len(set(record_ids))==len(q) and set(record_ids)==set(q.ID)
    q['subject']=q.ID.str[:3]
    assert q.subject.nunique()==50
    joined=q.merge(context[['ID','Ear/finger','Motion']],on='ID',validate='one_to_one')
    assert not joined.isna().any().any() and set(joined['Ear/finger'])=={0,1}
    assert all(all(int(v) in range(8) for v in value.split(';')) for value in joined.Motion)
    # Independent BOM-aware standard-library CSV pass, no pandas helpers.
    with (folder/'quality-hr-ann.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    raw_ids=[r['ID'] for r in rows];counts=Counter(int(r['Quality']) for r in rows)
    assert len(rows)==len(q) and set(raw_ids)==set(q.ID)
    assert counts==Counter(q.Quality) and len({i[:3] for i in raw_ids})==50
    headers=[]
    for name in sorted(n for n in manifest if n.endswith('.hea')):
        lines=(folder/name).read_text().splitlines();tokens=lines[0].split()
        match=re.fullmatch(r'(\S+) (\d+) (\d+) (\d+)',lines[0])
        assert match and list(match.groups())==tokens
        n_sig,fs,length=map(int,tokens[1:])
        assert len([s for s in lines[1:] if s and not s.startswith('#')])==n_sig
        headers.append({'path':name,'n_sig':n_sig,'fs':fs,'sig_len':length,'sha256':sha(folder/name)})
    assert len(headers)==4
    assert Counter((h['n_sig'],h['fs'],h['sig_len']) for h in headers)=={(300,30,1):2,(3,30,300):2}
    phases={}
    for phase,mask in [('initial',q.ID.astype(int)<112000),('extension',q.ID.astype(int)>=112000)]:
        part=q[mask]
        phases[phase]={'records':len(part),'subjects':part.subject.nunique(),'quality_counts':{str(k):int(v) for k,v in part.Quality.value_counts().items()}}
    nclasses=q.groupby('subject').Quality.nunique()
    public={'stage':'BUT_SOURCE1','source':'https://physionet.org/content/butppg/2.0.0/','doi':'10.13026/tn53-8153','license':'CC-BY-4.0',
      'scope':'Metadata tables plus four deterministic PPG headers; no waveform samples or model scores',
      'records':len(q),'subjects':q.subject.nunique(),'quality_counts':{str(k):int(v) for k,v in counts.items()},
      'always_poor_accuracy':counts[0]/len(q),'subjects_with_both_classes':int((nclasses==2).sum()),'subjects_with_one_class':int((nclasses==1).sum()),
      'records_per_subject_range':[int(q.groupby('subject').size().min()),int(q.groupby('subject').size().max())],
      'phase_counts':phases,'measurement_spot_counts':{str(k):int(v) for k,v in joined['Ear/finger'].value_counts().items()},
      'motion_code_counts':{str(k):int(v) for k,v in joined.Motion.value_counts().items()},
      'missing_quality_or_hr':0,'duplicate_record_ids':0,'unmatched_ids_between_tables_and_index':0,'header_sample':headers,'metadata_hashes':manifest,
      'verification':{'status':'passed_metadata_only','official_checksums_matched':len(checked),'csv_count_crosscheck':'pandas versus csv.DictReader','verifier_sha256':sha(Path(__file__))},
      'training_admission':'pending_waveform_adapter_and_subject_split_protocol',
      'not_verified':['full_waveforms','all_record_headers','RGB_channel_policy','initial_release_transposed_layout_conversion','sample_level_artifact_labels','wrist_domain_transfer'],
      'clinical_effect_changed':False}
    (ROOT/'docs/acceptance/BUT_SOURCE1.json').write_text(json.dumps(public,indent=2))
    print(json.dumps({k:public[k] for k in ['records','subjects','quality_counts','phase_counts','verification','training_admission']},indent=2))
if __name__=='__main__':main()
