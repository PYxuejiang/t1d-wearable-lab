"""Independent interpolation/correlation feature reconstruction and pairwise AUC."""
import hashlib,json,math
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat
from verify_ppg_quality_dev import equal,direct_auc
ROOT=Path(__file__).resolve().parents[1]
FEATURES=('template','interval','one_minus_sqi')
def norm(v):
    v=np.asarray(v,float);z=v-sum(v)/len(v);length=math.sqrt(sum(z*z))
    return z/length if length>1e-12 else z*0
def reconstruct(x,times):
    p=[round(t*64) for t in times];beats=[]
    for j,t in enumerate(p):
        l=(p[j-1]+t+1)//2 if j else 0;r=(t+p[j+1])//2 if j+1<len(p) else len(x)-1
        points=[]
        for index in range(64):
            coordinate=l+(r-l)*index/63;lo=math.floor(coordinate);hi=min(lo+1,r);fraction=coordinate-lo
            points.append(x[lo]+fraction*(x[hi]-x[lo]))
        beats.append(norm(points))
    return np.asarray(beats)
def main():
    path=ROOT/'docs/acceptance/PPG_LOCAL_DEV1.json';pub=json.loads(path.read_text())
    for group in ('source_sha256','input_sha256'):
        for p,h in pub[group].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    rows=json.loads((ROOT/'outputs/ppg_upstroke_dev_v1/windows_local.json').read_text())
    qs={r['key']:r for r in json.loads((ROOT/'outputs/ppg_quality_dev_v1/records_local.json').read_text())}
    local=json.loads((ROOT/'outputs/ppg_local_dev_v1/records_local.json').read_text());data={}
    audit=json.loads((ROOT/'docs/acceptance/PPG_DALIA_AUDIT1.json').read_text())
    for entry in audit['files']:
        p=ROOT/'data/ppg_dalia_mat'/entry['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==pub['data_sha256'][entry['file']]
        for raw in loadmat(p,squeeze_me=True,struct_as_record=False)['data']:
            key=str(raw.fix.subj_name)+'/'+entry['activity']
            if key in qs:data[key]=signal.sosfilt(signal.butter(3,[.5,5],btype='bandpass',fs=64,output='sos'),np.asarray(raw.ppg.v,float))
    n=0
    for rec in local:
        rr=[r for r in rows if r['key']==rec['key']];beats={}
        for r in rr:beats[r['start']]=reconstruct(data[r['key']][r['start']*64:(r['start']+30)*64],r['detected']['v5_peaks'])
        template=norm(np.median(np.vstack([beats[r['start']] for r in rr if r['start']<120]),axis=0));equal(rec['template'],template.tolist())
        intervals=[b-a for r in rr if r['start']<120 for a,b in zip(r['upstroke'],r['upstroke'][1:]) if b>a];median=float(np.median(intervals));equal(rec['median_interval'],median)
        counts=dict(candidate_count=0,zero_shape=0,zero_template=int(np.linalg.norm(template)<1e-12),no_neighbor=0,one_side=0)
        assert len(rr)==len(rec['windows'])
        for row,w in zip(rr,rec['windows']):
            assert row['start']==w['start'];scores={k:[] for k in FEATURES};u=row['upstroke'];mat=beats[row['start']]
            for j,shape in enumerate(mat):
                zero=np.linalg.norm(shape)<1e-12;counts['zero_shape']+=int(zero)
                risk=2. if zero or counts['zero_template'] else float(np.clip(1-np.corrcoef(shape,template)[0,1],0,2))
                neighbors=[]
                if j:neighbors.append(u[j]-u[j-1])
                if j+1<len(u):neighbors.append(u[j+1]-u[j])
                good=[v for v in neighbors if math.isfinite(v) and v>0];counts['no_neighbor']+=int(not good);counts['one_side']+=int(len(good)==1)
                scores['template'].append(risk);scores['interval'].append(max(abs(math.log(v/median)) for v in good) if good else 2.);scores['one_minus_sqi'].append(1-row['sqi'])
            equal(w['scores'],scores);counts['candidate_count']+=len(mat);n+=len(mat)
        for k,v in counts.items():assert rec[k]==v
        by_start={w['start']:w for w in rec['windows']};q=qs[rec['key']];labels=[];features={k:[] for k in FEATURES}
        for w in q['windows']:
            labels+=w['unmatched']
            for k in FEATURES:features[k]+=[by_start[w['start']]['scores'][k][j] for j in w['indices']]
        assert rec['tail_candidates']==len(labels)
        equal(rec['auc'],{k:direct_auc(labels,features[k]) for k in FEATURES});equal(rec['auc']['one_minus_sqi'],q['auc']['one_minus_sqi'])
    assert n==7954 and sum(r['tail_candidates'] for r in local)==pub['tail_candidates']==5119
    for activity,group in pub['by_activity'].items():
        rr=[r for r in local if r['activity']==activity];assert group['records']==len(rr)==5
        for k in ('candidate_count','tail_candidates','zero_shape','zero_template','no_neighbor','one_side'):assert group[k]==sum(r[k] for r in rr)
        for k in FEATURES:
            v=[r['auc'][k] for r in rr if r['auc'][k] is not None];equal(group['auc'][k],{'mean':float(np.mean(v)) if v else None,'valid_records':len(v)})
    for group in ('subject_auc','difference_vs_sqi'):
        for k,result in pub[group].items():
            vals=[]
            for sub in sorted({r['subject'] for r in local}):
                rr=[r for r in local if r['subject']==sub]
                if all(r['auc'][k] is not None and (group=='subject_auc' or r['auc']['one_minus_sqi'] is not None) for r in rr):
                    vals.append(np.mean([r['auc'][k]-(r['auc']['one_minus_sqi'] if group=='difference_vs_sqi' else 0) for r in rr]))
            idx=np.random.default_rng(20261020).integers(len(vals),size=(10000,len(vals))) if vals else None
            ci=np.percentile(np.array(vals)[idx].mean(axis=1),[2.5,97.5]).tolist() if vals else None
            equal(result,{'mean':float(np.mean(vals)) if vals else None,'95_interval':ci,'subjects':len(vals)})
    from run_ppg_local_dev import controls
    equal(pub['synthetic'],controls())
    assert all(k not in json.dumps(pub) for k in ['S1/','"template": [','"scores":','"subject":'])
    pub['verification']={'status':'passed','source_windows':211,'candidate_features':7954,'tail_candidates':5119,'record_auc':30,'subject_intervals':5,'old_sqi_auc_reproduced':True,
      'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256((ROOT/'scripts/verify_ppg_quality_dev.py').read_bytes()).hexdigest(),
      'shared_kernels':'SciPy filter; synthetic controls rerun producer; interpolation, normalization, correlation and pairwise AUC independently reconstructed'}
    path.write_text(json.dumps(pub,indent=2,allow_nan=False));print(json.dumps(pub['verification'],indent=2))
if __name__=='__main__':main()
