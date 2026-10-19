"""Source audit card; no clinical or model performance claim."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    d=json.loads((ROOT/'docs/acceptance/SEGADE_SOURCE1.json').read_text());assert d['verification']['status']=='passed_for_header_structure_only'
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='segadesource-'+digest[:12]
    lines=['T1D / ANNOTATED PPG SOURCE AUDIT','找到了标签入口，也查清了使用缺口',
      '8个NPY入口可达 · 4组信号与标签头尺寸一致',
      '头部声明：7306段 × 1920采样点；未做完整数据验收',
      'DaLiA 3436 / 869 · WESAD 2888 · TROIKA 113',
      '缺口一：未找到明确代码与新增标签许可',
      '缺口二：数组旁没有逐行受试者和时间映射',
      '示例内层KFold按行分折，不能直接用于按人验证',
      '结构审计通过 · 训练准入未通过 · 未运行第三方模型',
      '下一步审计明确许可的质量标签，区分手机与腕部域',
      '本轮没有新增模型性能 · 原疾病指标与覆盖保持',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,5,6) else '#302c33')
    p=ROOT/'showcase/public/cards/segade-source-v1.png';im.save(p)
    (p.parent/'segade-source-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2));print(run)
if __name__=='__main__':main()
