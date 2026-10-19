"""Render aggregate evidence for filter/bias diagnosis, not wearable efficacy."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'docs/acceptance/PPG_FILTER1.json').read_text())
    assert data['verification']['status']=='passed'
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run='ppgfilter-'+digest[:12]
    result=data['results']['evaluation']
    lines=['T1D / PPG FILTER AUDIT','先分清时间偏差，再评价形态收益',
           '70条开发估计偏差 · 149条评价 · 7路固定对照',
           '5Hz因果上升沿：仅做全局时间戳校正',
           f"MAE {result['causal5']['MG']['u']['mae_ms']:.2f} → {result['causal5_centered']['MG']['u']['mae_ms']:.2f} ms",
           '固定偏移不改变相邻间期，不能称为找搏能力改善',
           '双向5Hz → 12Hz：峰 / 上升沿平均MAE差 −3.77 ms',
           '探索性95%区间 [−4.63, −2.87] ms · MG参考',
           '因果两路校正后：12Hz平均MAE仍比5Hz高1.04 ms',
           '全部条目保留 · 12Hz校正后1/149出界未删除',
           '专家边界内指端离线研究 · 非腕部或低血糖验证',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,4) else '#302c33')
    path=ROOT/'showcase/public/cards/ppg-filter-v1.png';im.save(path)
    (path.parent/'ppg-filter-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print(run)

if __name__=='__main__':main()
