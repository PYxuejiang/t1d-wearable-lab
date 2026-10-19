"""Export aggregate candidate-risk ranking evidence."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    d=json.loads((ROOT/'docs/acceptance/PPG_LOCAL_DEV1.json').read_text());assert d['verification']['status']=='passed'
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='ppglocal-'+digest[:12]
    lines=['T1D / CANDIDATE PPG MORPHOLOGY','静坐有形态信息，步行仍是短板',
      '5名开发受试者 · 7954候选全部保留',
      '模板错误排序 AUC：静坐0.820 / 步行0.511',
      '间期错误排序 AUC：静坐0.766 / 步行0.563',
      '原SQI对照：静坐0.753 / 步行0.558',
      '模板较SQI按人差 +0.010 · 95%区间 [−0.005, 0.029]',
      '间期较SQI按人差 +0.009 · 95%区间 [−0.065, 0.070]',
      '未筛选数据 · 旧PPI、时间覆盖与疾病结果保持',
      '下一步：审计人工腕部质量标签及许可，不盲调参数',
      '已见开发探索 · 参考未匹配标签，非人工伪迹真值',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,4,5) else '#302c33')
    path=ROOT/'showcase/public/cards/ppg-local-dev-v1.png';im.save(path)
    (path.parent/'ppg-local-dev-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2));print(run)
if __name__=='__main__':main()
