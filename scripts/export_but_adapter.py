"""Small-sample decode verification card, no patient signals."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    d=json.loads((ROOT/'docs/acceptance/BUT_ADAPTER1.json').read_text())
    assert d['verification']['status']=='passed_raw_layout_decode_only'
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='butadapter-'+digest[:12]
    lines=['T1D / CROSS-VERSION PPG READER','数值读取已核对，时间含义继续查证',
      '四条预设样本全部保留 · 8个原始文件哈希一致',
      '自写读取器 × WFDB 4.3.1：数字样本逐值一致',
      '物理值最大误差0 · 2400个值有限 · 不代表全库验收',
      '旧版保持1×300，新版保持300×RGB三通道',
      '未把旧版通道轴擅自当成时间轴，也未选最佳颜色',
      '发现单位解析差异：保留原始a.u.并记录WFDB截断',
      '7项合成测试覆盖交织、负增益、缺失与错误格式',
      '下一步：时间轴来源证据 + 全库导入覆盖审计',
      '手机质量方法对照 · 本轮没有新增疾病检测效果',run]
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1390),'#f7f4f2');draw=ImageDraw.Draw(im)
    for i,line in enumerate(lines):draw.text((85,70+i*108),line,font=ImageFont.truetype(str(font),46 if i==1 else 32),fill='#725365' if i in (3,4,7) else '#302c33')
    p=ROOT/'showcase/public/cards/but-adapter-v1.png';im.save(p)
    (p.parent/'but-adapter-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2));print(run)
if __name__=='__main__':main()
