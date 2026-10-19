"""Public aggregate card: expert-boundary offline localization, never disease claims."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT/'docs/acceptance/PPG_FIDUCIAL1.json').read_text())
    assert data['verification']['status'] == 'passed'
    digest = hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run = 'ppgfid-'+digest[:12]
    raw = data['results']['evaluation']['raw']['MG']
    selected = data['results']['evaluation'][data['selection']['selected']]['MG']
    lines = ['T1D / CONDITIONAL PPG LOCALIZATION', '从形态信号，找准峰与上升沿',
             '70条开发选择 · 149条评价 · 657组预测独立复算',
             '专家边界内 · 指端精选单搏 · MG参考 / MAE',
             f"峰：{raw['pk']['mae_ms']:.2f} → {selected['pk']['mae_ms']:.2f} ms",
             f"最大上升沿：{raw['u']['mae_ms']:.2f} → {selected['u']['mae_ms']:.2f} ms",
             '原提供信号 → 开发选中的 0.5–12Hz 双向滤波',
             'MG参考149/149 · PC参考148/149 · 全部条目保留',
             '差距：专家边界、未来采样；峰误差尾部并非全面改善',
             '下一步：分离滤波延迟，再验证连续腕部找搏',
             '探索性信号子任务 · 尚无新增低血糖检测效能结论', run]
    font = next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im = Image.new('RGB',(1800,1390),'#f7f4f2'); draw = ImageDraw.Draw(im)
    for i,line in enumerate(lines):
        draw.text((85,70+i*108), line, font=ImageFont.truetype(str(font),46 if i==1 else 32), fill='#725365' if i in (4,5) else '#302c33')
    path = ROOT/'showcase/public/cards/ppg-fiducial-v1.png'; im.save(path)
    (path.parent/'ppg-fiducial-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print(run)


if __name__ == '__main__': main()
