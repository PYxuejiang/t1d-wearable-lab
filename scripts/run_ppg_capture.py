"""Freeze development SQI before producing held-out PPG beat scores."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t1d_lab.ppg_capture import detect_window,quality,select_lag,score_window,summarize


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def candidates(rows,lags,cfg):
    result=[]
    for threshold in cfg['sqi_thresholds']:
        records=[]
        for key in sorted(lags):
            rr=[r for r in rows if r['key']==key and r['start']>=120]
            accepted=[r for r in rr if r['sqi']>=threshold]
            metrics=summarize([score_window(r,'dual_average',lags[key]) for r in accepted])
            records.append({'key':key,'activity':rr[0]['activity'],'coverage':len(accepted)/len(rr),'f1':metrics['f1']})
        coverage={a:float(np.mean([r['coverage'] for r in records if r['activity']==a])) for a in ['sitting','walking']}
        feasible=min(coverage.values())>=.7 and all(r['f1'] is not None for r in records)
        score=float(np.mean([r['f1'] for r in records])) if feasible else None
        result.append({'threshold':threshold,'feasible':feasible,'macro_f1':score,'coverage_by_activity':coverage,'records':records})
    chosen=max([r for r in result if r['feasible']],key=lambda r:(r['macro_f1'],sum(r['coverage_by_activity'].values()),-r['threshold']))
    return result,chosen['threshold']


def main():
    cfg=json.loads((ROOT/'configs/ppg_capture_v1.json').read_text());audit=json.loads((ROOT/cfg['source_audit']).read_text())
    dest=ROOT/cfg['output'];dest.mkdir(parents=True,exist_ok=True)
    if any(dest.iterdir()):raise RuntimeError('Output not empty: preserve previous attempts')
    sources={name:sha(ROOT/name) for name in ['configs/ppg_capture_v1.json','src/t1d_lab/ppg_capture.py','src/t1d_lab/ppg_morphology.py','scripts/run_ppg_capture.py']}
    source_data=[]
    for entry in audit['files']:
        path=ROOT/'data/ppg_dalia_mat'/entry['file'];assert sha(path)==entry['sha256']
        for raw in loadmat(path,simplify_cells=True)['data']:source_data.append((entry['activity'],raw))
    rows=[];lags={};record_meta=[]
    for phase,subjects in [('development',cfg['development_subjects']),('heldout',cfg['heldout_subjects'])]:
        for activity,raw in source_data:
            subject=str(raw['fix']['subj_name'])
            if subject not in subjects:continue
            key=subject+'/'+activity;rate=float(raw['ppg']['fs']);assert rate==64 and raw['ecg']['fs']==700
            ppg=np.asarray(raw['ppg']['v'],float);ref=(np.asarray(raw['ecg']['rpeaks'],float)-1)/700
            duration=min(len(ppg)/rate,len(raw['ecg']['v'])/700)
            filtered=signal.sosfilt(signal.butter(3,[.5,5],btype='bandpass',fs=rate,output='sos'),ppg)
            rr=[]
            for start in range(0,int(duration//30)*30,30):
                segment=filtered[int(start*rate):int((start+30)*rate)]
                rr.append({'key':key,'subject':subject,'activity':activity,'phase':phase,'start':start,'input_end':start+30,'sqi':quality(segment,rate),'reference':(ref[(ref>=start)&(ref<start+30)]-start).tolist(),'detected':{m:detect_window(segment,rate,m).tolist() for m in cfg['algorithms']}})
            lag=select_lag([r for r in rr if r['start']<120],cfg['lag_grid_seconds']);lags[key]=lag;rows.extend(rr)
            record_meta.append({'key':key,'subject':subject,'activity':activity,'phase':phase,'duration':duration,'lag_seconds':lag,'calibration_windows':4,'score_windows':sum(r['start']>=120 for r in rr)})
            print(phase,key,'extracted',len(rr),'windows',flush=True)
        if phase=='development':
            choices,threshold=candidates(rows,lags,cfg)
            selection={'protocol':cfg['id'],'sqi_threshold':threshold,'candidates':choices,'development_lags':dict(lags),'source_sha256':sources}
            (dest/'selection.json').write_text(json.dumps(selection,indent=2,allow_nan=False))
            print('Development selection frozen before heldout:',threshold,flush=True)
    (dest/'windows.json').write_text(json.dumps(rows,allow_nan=False))
    (dest/'records.json').write_text(json.dumps(record_meta,indent=2))
    done={'protocol':cfg['id'],'source_sha256':sources,'selection_sha256':sha(dest/'selection.json'),'windows_sha256':sha(dest/'windows.json'),'records_sha256':sha(dest/'records.json'),'data_sha256':{f['file']:f['sha256'] for f in audit['files']}}
    (dest/'complete.json').write_text(json.dumps(done,indent=2));print('Extraction complete; independent verification required',flush=True)
if __name__=='__main__':main()
