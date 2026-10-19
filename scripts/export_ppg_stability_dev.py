"""Create a public aggregate-only calibration stability evidence card."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = json.loads((ROOT / 'docs/acceptance/PPG_STABILITY_DEV1.json').read_text())
    assert result['verification']['status'] == 'passed'
    digest = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    run = 'ppgstable-' + digest[:12]
    s, w = (result['by_activity'][a] for a in ['sitting', 'walking'])
    delta = result['tail_f1_sensitivity']
    lines = ['T1D / CALIBRATION STABILITY', '先验证对应关系，再判断算法进步',
             f"换校准段：尾段 F1 平均绝对变化 {delta['mean_absolute_difference']*100:.2f} pp",
             f"5人探索性95%区间 [{delta['95_interval'][0]*100:.2f}, {delta['95_interval'][1]*100:.2f}] pp",
             f"两段偏移相差 ≤100ms：静坐 {s['stable_records']}/5 · 步行 {w['stable_records']}/5",
             f"两分钟校准仍有周期歧义：步行 {w['arms']['first120']['ambiguous_records']}/5",
             f"评分时间覆盖：静坐 {s['core_time_coverage']:.2%} · 步行 {w['core_time_coverage']:.2%}",
             '已做到：30次校准与30组尾段计数、间期独立复核',
             '下一步：PPG峰与上升沿位置、平台与残差检查',
             '仅开发集参考辅助诊断；没有新增低血糖识别增益', run]
    font = next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im = Image.new('RGB', (1800, 1280), '#f7f4f2'); draw = ImageDraw.Draw(im)
    for i, text in enumerate(lines):
        draw.text((85, 70+i*108), text, font=ImageFont.truetype(str(font), 46 if i == 1 else 32), fill='#725365' if i in [2, 5] else '#302c33')
    path = ROOT / 'showcase/public/cards/ppg-stability-dev-v1.png'; im.save(path)
    (path.parent / 'ppg-stability-dev-manifest.json').write_text(json.dumps({'run_id': run, 'acceptance_sha256': digest, 'png_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2))
    print(run)


if __name__ == '__main__':
    main()
