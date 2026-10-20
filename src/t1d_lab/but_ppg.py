"""Strict subset reader for BUT PPG WFDB format 16, preserving source layout.

Never infer time from a flattened legacy 1x300 array. No quality labels used.
"""
from pathlib import Path
import re
import numpy as np

def read_but_raw(header_path):
    path=Path(header_path)
    lines=[s.strip() for s in path.read_text().splitlines() if s.strip() and not s.startswith('#')]
    first=lines[0].split()
    if len(first)!=4:raise ValueError('Unsupported record header')
    name,n_sig,fs,n_samples=first
    n_sig,n_samples,fs=int(n_sig),int(n_samples),float(fs)
    if fs!=30 or (n_samples,n_sig) not in [(1,300),(300,3)]:raise ValueError('Unsupported BUT layout')
    if len(lines)!=n_sig+1:raise ValueError('Wrong signal header count')
    gains=[];baselines=[];units=[];names=[];files=[]
    for line in lines[1:]:
        fields=line.split()
        if len(fields)<8 or fields[1]!='16':raise ValueError('Only plain format 16 supported')
        match=re.fullmatch(r'([-+\d.eE]+)\((-?\d+)\)/(.+)',fields[2])
        if not match:raise ValueError('Explicit gain and baseline required')
        gain,baseline,unit=match.groups();gain=float(gain)
        if not np.isfinite(gain) or gain==0:raise ValueError('Invalid gain')
        if Path(fields[0]).name!=fields[0]:raise ValueError('Signal path must be local basename')
        gains.append(gain);baselines.append(int(baseline));units.append(unit)
        names.append(fields[8] if len(fields)>8 else '')
        files.append(fields[0])
    if len(set(files))!=1:raise ValueError('Split signal files unsupported')
    raw=(path.parent/files[0]).read_bytes()
    if len(raw)!=2*n_samples*n_sig:raise ValueError('Unexpected signal file length')
    digital=np.frombuffer(raw,dtype='<i2').reshape(n_samples,n_sig).copy()
    physical=(digital.astype(float)-np.array(baselines))/np.array(gains)
    physical[digital==-32768]=np.nan
    return {'digital':digital,'physical':physical,'fs':fs,'units':units,'names':names,
            'layout':'legacy_header' if n_samples==1 else 'rgb_time_series',
            'record_name':name}
