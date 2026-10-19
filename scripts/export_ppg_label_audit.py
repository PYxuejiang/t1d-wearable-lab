"""Render label provenance findings, never detector accuracy claims."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'docs/acceptance/PPG_LABEL_AUDIT1.json').read_text())
    assert data['verification']['status']=='passed'
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run='ppglabel-'+digest[:12]
    lines=['T1D / PPG LABEL AUDIT','先选对目标心搏，再评价定位',
           '219条信号 · 两套标注 · 1752个字段独立复核',
           '关键发现：多值pk通常包含邻近心搏的峰',
           '专家边界内唯一峰：MG 219/219 · PC 218/219',
           f"u标签配对覆盖 {data['agreement']['u']['pair_coverage']:.2%} · 标签平均差 {data['agreement']['u']['mae_ms']:.3f} ms",
           '标注差异是参考信息，不是本项目算法误差',
           '已知限制：指端、高质量单搏、经过讨论的最终标签',
           '下一步：冻结专家边界内的峰 / 上升沿条件定位',
           '尚无新增腕部或低血糖检测效能结论',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1280),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in [3,4] else '#302c33')
    p=ROOT/'showcase/public/cards/ppg-label-audit-v1.png';im.save(p)
    (p.parent/'ppg-label-audit-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2))
    print(run)

if __name__=='__main__':main()
