"""Aggregate fixed quality-retention tradeoff evidence."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    d=json.loads((ROOT/'docs/acceptance/PPG_RETENTION_DEV1.json').read_text());assert d['verification']['status']=='passed'
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='ppgretention-'+digest[:12]
    lines=['T1D / PPG RETENTION COST','精度的提高，伴随着有效信息损失',
      '5名开发受试者 · 171尾窗 · 4路固定对照全部公开',
      '预设q50：输出PPV +7.71 pp；全参考敏感度 −23.58 pp',
      '按人95%区间：[3.52, 12.47] / [−31.44, −13.76] pp',
      '核心时间覆盖 −28.26 pp；PPI覆盖 −18.57 pp',
      '步行：去掉418个原FP，也失去580个原TP',
      '步行条件PPI误差 48.35 → 48.68 ms，未改善',
      '原参考分母完整保留 · 未按尾段选阈值',
      '决策：不启用当前SQI整窗筛选，改进候选级信息',
      '已见开发集探索 · 非疾病报警结果',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,4,5) else '#302c33')
    path=ROOT/'showcase/public/cards/ppg-retention-dev-v1.png';im.save(path)
    (path.parent/'ppg-retention-dev-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2));print(run)
if __name__=='__main__':main()
