"""Export activity aggregate evidence; no individual predictions."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'docs/acceptance/PPG_UPSTROKE_DEV1.json').read_text())
    assert data['verification']['status']=='passed'
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run='ppgupstroke-'+digest[:12]
    sit=data['by_activity']['sitting']['landmarks']
    walk=data['by_activity']['walking']['landmarks']
    lines=['T1D / WRIST PPG DEVELOPMENT','静坐有收益，步行仍需解决',
           '5名开发受试者 · 211窗 · 7954候选全部保留',
           '无人工搏动边界：候选峰 → 峰前最大上升沿',
           f"静坐 F1：{sit['peak']['first120']['f1']*100:.2f}% → {sit['upstroke']['first120']['f1']*100:.2f}%",
           f"步行 F1：{walk['peak']['first120']['f1']*100:.2f}% → {walk['upstroke']['first120']['f1']*100:.2f}%",
           '按人总体 F1 差 +3.81 pp · 95%区间 [−2.18, 10.21]',
           'PPI覆盖：静坐46.00 → 60.49%；步行27.54 → 25.02%',
           '固定核心评分时间：静坐73.08%，步行70.73%',
           'ECG参考辅助对齐 · 243个次序异常候选未删除',
           '已见开发集探索 · 非临床验证 · 疾病指标保持原结果',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):
        draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,4,5) else '#302c33')
    path=ROOT/'showcase/public/cards/ppg-upstroke-dev-v1.png';im.save(path)
    (path.parent/'ppg-upstroke-dev-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print(run)

if __name__=='__main__':main()
