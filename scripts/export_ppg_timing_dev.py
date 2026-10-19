"""Render a cohort-only timing diagnostic card from verified aggregates."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = json.loads((ROOT / 'docs/acceptance/PPG_TIMING_DEV1.json').read_text())
    assert result['verification']['status'] == 'passed'
    digest = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    run = 'ppgtime-' + digest[:12]
    sitting, walking = (result['by_activity'][key] for key in ['sitting', 'walking'])
    delta = result['development_paired_f1_difference']
    lines = [
        'T1D / PPG TIMING DIAGNOSTIC',
        '先核对时间，再评价心搏匹配',
        f"静坐 F1：{sitting['old_tail_f1']:.2%} → {sitting['expanded_tail_f1']:.2%}",
        f"步行 F1：{walking['old_tail_f1']:.2%} → {walking['expanded_tail_f1']:.2%}",
        f"按人配对差 {delta['mean']*100:+.2f} pp · 95%区间 [{delta['95_interval'][0]*100:+.2f}, {delta['95_interval'][1]*100:+.2f}] pp",
        '仅改变参考辅助校准范围；峰值检测器保持不变',
        '5名开发受试者 · 20个校准选择与20组尾段计数复核',
        f"评分时间覆盖：静坐 {sitting['core_time_coverage_after_calibration']:.2%} / 步行 {walking['core_time_coverage_after_calibration']:.2%}",
        '差距：2/5步行记录存在竞争偏移；尚不能确认物理同步',
        '对齐敏感性探索；不代表检测器或低血糖效能提升',
        run,
    ]
    font = next(path for path in [Path('C:/Windows/Fonts/msyh.ttc'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if path.exists())
    canvas = Image.new('RGB', (1800, 1280), '#f7f4f2')
    draw = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        draw.text((85, 70 + index * 108), line, font=ImageFont.truetype(str(font), 46 if index == 1 else 32), fill='#725365' if index in [2, 3] else '#302c33')
    path = ROOT / 'showcase/public/cards/ppg-timing-dev-v1.png'
    canvas.save(path)
    (path.parent / 'ppg-timing-dev-manifest.json').write_text(json.dumps({'run_id': run, 'acceptance_sha256': digest, 'png_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2))
    print(run)


if __name__ == '__main__':
    main()
