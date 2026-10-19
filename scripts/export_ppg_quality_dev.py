"""Render aggregate quality evidence; unmatched is not artifact ground truth."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    d=json.loads((ROOT/'docs/acceptance/PPG_QUALITY_DEV1.json').read_text());assert d['verification']['status']=='passed'
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='ppgquality-'+digest[:12]
    lines=['T1D / WRIST PPG QUALITY','找到了问题范围，尚未解决运动干扰',
      '5名开发受试者 · 尾段5119候选 · 全部保留',
      '步行：次序异常只覆盖91/1718个未匹配候选（5.30%）',
      '现有SQI的错误排序 AUC：静坐0.753 / 步行0.558',
      '位移偏差 AUC：静坐0.720 / 步行0.508',
      'SQI按人总体 AUC 0.655 · 95%区间 [0.620, 0.696]',
      '不能仅凭总体AUC声称步行质量控制有效',
      '未选阈值、未拒绝数据 · 时间与PPI覆盖保持',
      '参考辅助未匹配标签，不是人工伪迹真值',
      '已见开发集探索 · 低血糖检测结果保持原记录',run]
    font=Path('C:/Windows/Fonts/msyh.ttc');im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,4,5) else '#302c33')
    path=ROOT/'showcase/public/cards/ppg-quality-dev-v1.png';im.save(path)
    (path.parent/'ppg-quality-dev-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print(run)
if __name__=='__main__':main()
