"""Offline metadata/header audit; never deserialize or score patient arrays.

Input: fixed-commit metadata and .header files in outputs/segade_source_audit_v1.
The corresponding remote URLs and Git blob IDs are published in the result.
"""
import ast,hashlib,io,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'outputs/segade_source_audit_v1';source=json.loads((folder/'source_metadata.json').read_text())
    assert source['commit']=='f5b2ad6e180a1474bc47d6c5ec5d482edaed6797' and not source['tree_truncated']
    assert source['github_license'] is None and source['license_paths']==[]
    groups={};verified=[]
    for entry in source['headers']:
        p=folder/(entry['path'].replace('/','__')+'.header');raw=p.read_bytes();stream=io.BytesIO(raw)
        assert np.lib.format.read_magic(stream)==(1,0)
        shape,fortran,dtype=np.lib.format.read_array_header_1_0(stream)
        assert list(shape)==entry['header']['shape'] and fortran==entry['header']['fortran_order']
        assert dtype.str==entry['header']['descr']=='<f8' and stream.tell()==len(raw)==128
        assert len(shape)==2 and shape[1]==1920 and not dtype.hasobject
        assert int(np.prod(shape))*dtype.itemsize+len(raw)==entry['git_size']
        group=entry['path'].split('/')[1];kind=Path(entry['path']).stem
        groups.setdefault(group,{})[kind]=shape[0]
        verified.append({'path':entry['path'],'shape':list(shape),'dtype':dtype.str,'bytes':entry['git_size'],'git_blob_sha':entry['git_blob_sha'],
                         'header_sha256':sha(p),'range_http_status':entry['http_status']})
    assert len(verified)==8 and len(groups)==4
    for group,items in groups.items():assert items['scaled_ppgs']==items['seg_labels']
    total=sum(items['scaled_ppgs'] for items in groups.values());assert total==7306
    for p,item in source['text_files'].items():assert sha(folder/p.replace('/','__'))==item['sha256']
    split=(folder/'data_split.py').read_text();conversion=(folder/'db2npy.py').read_text()
    assert 'KFold(n_splits=n_fold, shuffle=True, random_state=1)' in split and 'kf.split(X)' in split and 'GroupKFold' not in split
    saves=[ast.get_source_segment(conversion,node) for node in ast.parse(conversion).body if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name) and node.value.func.value.id=='np' and node.value.func.attr=='save']
    assert len(saves)==2 and all(any(k in line for k in ('scaled_ppgs.npy','seg_labels.npy')) for line in saves)
    public={'stage':'SEGADE_SOURCE1','scope':'Repository metadata and NPY headers only; no complete arrays, training or scoring',
      'repository':source['repository'],'commit':source['commit'],'declared_rows_verified_by_headers':total,'groups':{g:v['scaled_ppgs'] for g,v in groups.items()},
      'files':verified,'github_license':None,'license_filename_candidates':[],'text_license_keyword_hits':{k:v['license_keyword_lines'] for k,v in source['text_files'].items()},
      'identity_sidecar_in_data_directory':False,'data_directory_blob_count':len(source['data_entries']),
      'fold_code_observation':'Shuffled KFold on X rows; no subject grouping supplied in data_split.py',
      'conversion_exports':'Two arrays only; no row-to-subject/time mapping exported by db2npy.py',
      'training_readiness':'not_accepted_pending_license_and_subject_mapping',
      'not_verified':['complete_file_hashes','actual_label_values','missing_or_duplicate_rows','per_row_subject_and_time','source_alignment','permission_for_code_or_annotation_reuse'],
      'local_evidence_sha256':sha(folder/'source_metadata.json'),'inspected_text_sha256':{k:v['sha256'] for k,v in source['text_files'].items()},
      'verification':{'status':'passed_for_header_structure_only','independent_header_parser':'numpy.lib.format compared with initial ast literal parser','files_checked':8,'matching_pairs':4,'header_size_consistency':True,'verifier_sha256':sha(Path(__file__))}}
    (ROOT/'docs/acceptance/SEGADE_SOURCE1.json').write_text(json.dumps(public,indent=2));print(json.dumps({'groups':public['groups'],'rows':total,'training_readiness':public['training_readiness'],'verification':public['verification']},indent=2))
if __name__=='__main__':main()
