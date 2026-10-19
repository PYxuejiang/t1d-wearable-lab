"""Development-only timing diagnostics; no detector or clinical outcome changes."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t1d_lab.ppg_capture import match_seconds, metrics, summarize, detect_window


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def score(rows, lag):
    items = []
    for row in rows:
        a = np.asarray(row['reference'])
        b = np.asarray(row['detected']['v5_peaks']) - lag
        items.append(metrics(a[(a >= 4) & (a < 26)], b[(b >= 4) & (b < 26)]))
    return summarize(items)


def choose(rows, grid):
    values = [(score(rows, float(lag))['tp'], float(lag)) for lag in grid]
    tp, lag = max(values, key=lambda v: (v[0], -abs(v[1]-.2), -v[1]))
    distant = [n for n, x in values if abs(x-lag) >= .3-1e-9]
    return lag, tp, max(distant) / tp if tp and distant else None


def independent_count(a, b, tolerance=.1):
    # Dynamic programming verifies maximum one-to-one count independently.
    prev = [0]*(len(b)+1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(max(prev[j+1], cur[-1], prev[j]+int(abs(x-y) <= tolerance+1e-12)))
        prev = cur
    return prev[-1]


def synthetic_checks():
    rng = np.random.default_rng(20261019)
    ref = np.cumsum(rng.uniform(.55, 1.3, 100))
    grid = np.round(np.arange(-1.5, 1.501, .01), 2)
    recovered = []
    for delay in [-.9, -.25, .2, .85]:
        pred = ref+delay
        lag = max(grid, key=lambda x: (len(match_seconds(ref, pred-x, .005)), -abs(x-delay)))
        assert abs(lag-delay) < 1e-10
        assert independent_count(ref, pred-lag, .005) == len(ref)
        recovered.append({'injected_seconds': delay, 'recovered_seconds': float(lag)})
    fs = 64
    t = np.arange(120*fs)/fs
    peaks = ref[(ref > 5) & (ref < 110)]
    shifts = []
    for width in [.04, .08, .12]:
        raw = sum(np.exp(-.5*((t-p)/width)**2) for p in peaks)
        filt = signal.sosfilt(signal.butter(3, [.5, 5], btype='bandpass', fs=fs, output='sos'), raw)
        delta = []
        for p in peaks:
            mask = (t >= p-.2) & (t <= p+.2)
            local_t = t[mask]
            delta.append(float(local_t[np.argmax(filt[mask])]-local_t[np.argmax(raw[mask])]))
        shifts.append({'gaussian_width_seconds': width, 'median_shift_ms': float(np.median(delta)*1000)})
    return {'known_delays': recovered, 'filter_pulse_shapes': shifts}


def main():
    out = ROOT/'outputs/ppg_timing_dev_v1'
    out.mkdir(exist_ok=True, parents=True)
    if any(out.iterdir()):
        raise RuntimeError('Preserve completed or partial attempt; output must be empty')
    cached = ROOT/'outputs/ppg_capture_v1'
    complete = json.loads((cached/'complete.json').read_text())
    assert sha(cached/'windows.json') == complete['windows_sha256']
    rows = [r for r in json.loads((cached/'windows.json').read_text()) if r['phase']=='development']
    assert {r['subject'] for r in rows} == {'S1','S2','S3','S4','S5'}
    grid = np.round(np.arange(-1.5, 1.501, .01), 2)
    oldgrid = np.round(np.arange(0, .601, .01), 2)
    local = []
    for key in sorted({r['key'] for r in rows}):
        rr = [r for r in rows if r['key']==key]
        cal = [r for r in rr if r['start'] < 120]
        tail = [r for r in rr if r['start'] >= 120]
        old, _, _ = choose(cal, oldgrid)
        new, _, rival = choose(cal, grid)
        blocks = []
        for block in sorted({r['start']//120 for r in tail}):
            chunk = [r for r in tail if r['start']//120==block]
            if len(chunk)==4:
                blocks.append(choose(chunk, grid)[0])
        for row in rr:
            a=np.asarray(row['reference']); b=np.asarray(row['detected']['v5_peaks'])-new
            a=a[(a>=4)&(a<26)]; b=b[(b>=4)&(b<26)]
            assert independent_count(a,b)==len(match_seconds(a,b))
        local.append({'key':key, 'activity':rr[0]['activity'], 'old_lag':old, 'new_lag':new,
                      'rival_fraction':rival, 'block_lags':blocks,
                      'old_tail':score(tail,old), 'new_tail':score(tail,new)})
        print('Completed development record', len(local), flush=True)
    audit=json.loads((ROOT/'docs/acceptance/PPG_DALIA_AUDIT1.json').read_text())
    filter_rows=[]
    for entry in audit['files']:
        path=ROOT/'data/ppg_dalia_mat'/entry['file']; assert sha(path)==entry['sha256']
        for raw in loadmat(path,simplify_cells=True)['data']:
            if str(raw['fix']['subj_name']) not in {'S1','S2','S3','S4','S5'}: continue
            x=np.asarray(raw['ppg']['v'],float); fs=64
            filt=signal.sosfilt(signal.butter(3,[.5,5],btype='bandpass',fs=fs,output='sos'),x)
            delta=[]; total=matched=0
            for start in range(0,len(x)//(30*fs)*30,30):
                a=detect_window(x[start*fs:(start+30)*fs],fs,'v5_peaks')
                b=detect_window(filt[start*fs:(start+30)*fs],fs,'v5_peaks')
                pairs=match_seconds(a,b,.25); total+=len(a);matched+=len(pairs)
                delta.extend((b[j]-a[i])*1000 for i,j in pairs)
            filter_rows.append({'activity':entry['activity'],'match_fraction':matched/total if total else 0,
                                'median_shift_ms':float(np.median(delta)) if delta else None})
    public={'stage':'PPG_TIMING_DEV1','scope':'Development-only diagnostic; no detector gain or clinical outcome claim',
            'records':len(local),'windows':len(rows),'reference_count_verified':True,'synthetic':synthetic_checks(),
            'by_activity':{},'source_sha256':{p:sha(ROOT/p) for p in ['scripts/audit_ppg_timing_dev.py','docs/METHOD_PPG_TIMING_DEV1.zh-CN.md','src/t1d_lab/ppg_capture.py']},
            'cache_sha256':complete['windows_sha256']}
    for act in ['sitting','walking']:
        rr=[r for r in local if r['activity']==act]; ff=[r for r in filter_rows if r['activity']==act]
        public['by_activity'][act]={'records':len(rr),'old_tail_f1':float(np.mean([r['old_tail']['f1'] for r in rr])),
          'expanded_tail_f1':float(np.mean([r['new_tail']['f1'] for r in rr])),
          'outside_old_range':sum(r['new_lag']<0 or r['new_lag']>.6 for r in rr),
          'near_equal_distant_peak':sum(r['rival_fraction']>=.95 for r in rr),
          'median_block_lag_change_seconds':float(np.median([abs(x-r['new_lag']) for r in rr for x in r['block_lags']])),
          'filter_median_shift_ms':float(np.median([r['median_shift_ms'] for r in ff if r['median_shift_ms'] is not None])),
          'filter_macro_match_fraction':float(np.mean([r['match_fraction'] for r in ff]))}
    (out/'records_local.json').write_text(json.dumps(local,indent=2,allow_nan=False))
    (out/'filter_local.json').write_text(json.dumps(filter_rows,indent=2,allow_nan=False))
    (ROOT/'docs/acceptance/PPG_TIMING_DEV1.json').write_text(json.dumps(public,indent=2,allow_nan=False))
    print(json.dumps(public,indent=2))


if __name__=='__main__':
    main()
