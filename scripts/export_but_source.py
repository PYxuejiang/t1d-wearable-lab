"""Aggregate source-audit card, no raw records or model performance claims."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    d=json.loads((ROOT/'docs/acceptance/BUT_SOURCE1.json').read_text())
    assert d['verification']['status']=='passed_metadata_only'
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run='butsource-'+digest[:12]
    lines=['T1D / PPG QUALITY DATA READINESS','明确了数据入口，也提前发现了读取陷阱',
      '3888条记录 · 50名受试者 · 标签与索引一一对应',
      '好质量830 / 差质量3058 · CC BY 4.0 · 9个文件哈希通过',
      '始终预测差质量也有78.65%准确率：不能只看accuracy',
      '每人4–108条；按人划分与按人区间不可省略',
      '四头抽查：旧版300信号×1点，新版RGB×300点',
      '先验证布局转换、增益与通道策略，再进入模型评分',
      '手机耳部/指部数据 · 不能代表腕部运动表现',
      '下一步：跨版本波形适配 → 冻结分组 → 质量基线',
      '仅元数据验收通过 · 原疾病指标与覆盖保持',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):
        draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,4,6) else '#302c33')
    p=ROOT/'showcase/public/cards/but-source-v1.png';im.save(p)
    (p.parent/'but-source-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2))
    print(run)
if __name__=='__main__':main()
