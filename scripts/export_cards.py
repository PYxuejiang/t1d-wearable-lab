"""Generate portable SVG/PNG cards from the exact public result artifact."""
import json
import hashlib
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]


def main():
    data=json.loads((ROOT/'showcase/public/demo/project_data.json').read_text(encoding='utf-8'))
    dest=ROOT/'showcase/public/cards';dest.mkdir(exist_ok=True,parents=True)
    font_paths=[Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font=next((p for p in font_paths if p.exists()),None)
    def card(filename,lines):
        image=Image.new('RGB',(1800,1200),'#f6f5ef');draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((45,45,1755,1155),radius=26,fill='#fffefa',outline='#dfe4dc',width=2)
        draw.rounded_rectangle((85,100,96,1100),radius=4,fill='#276c61')
        svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1200"><rect width="1800" height="1200" fill="#f6f5ef"/>']
        for i,line in enumerate(lines):
            size=54 if i==1 else 32 if i>=7 else 39
            face=ImageFont.truetype(str(font),size) if font else ImageFont.load_default(size=size)
            xy=(135,110+i*100);fill='#276c61' if i in [0,3] else '#1d373b'
            draw.text(xy,line,font=face,fill=fill)
            svg.append(f'<text x="135" y="{xy[1]+size}" font-family="Microsoft YaHei,Arial,sans-serif" font-size="{size}" fill="{fill}">{escape(line)}</text>')
        svg.append('</svg>');(dest/f'{filename}.svg').write_text(''.join(svg),encoding='utf-8');image.save(dest/f'{filename}.png')
    tail=[f"协议 {data['protocol']} / {data['run_id']}",'研究展示：回顾性公开队列，不构成医疗报警',data['repository']]
    gain=data['regression']['results']['loso']['comparisons'][0]['relative_mae_improvement_percent']
    included=data['acceptance']['S1b']['included_subjects']
    card('overview',['T1D / WEARABLE LAB','公开数据 · 两模块研究作品',f"BrisT1D：{data['audit']['subjects']} 人；PhysioCGM：纳入 {included} / 10 人",f'CGM 数值预测改善 {gain:.1f}%（LOSO，相对简单基线）','腕部附加信息与低血糖报警目标：未达标','已保留负结果、排除原因与逐阶段验收']+tail)
    for p in ['loso','temporal']:
        reg=data['regression']['results'][p];incident=data['incident'][p]['fusion']
        card('module1-'+p,['T1D / MODULE 01','协同预测与新发事件预警',f'BrisT1D-Open · 20 人 · {p.upper()} · 未来 30 分钟',f"CGM 模型 MAE：{reg['subject_equal_metrics']['cgm']['mae']:.4f} mmol/L",f"腕部附加信息增益：{reg['comparisons'][1]['relative_mae_improvement_percent']:.2f}%（未达目标）",f"事件召回：{incident['event_recall']*100:.1f}% / 误报：{incident['false_alerts_per_person_day']:.2f} 次/人日"]+tail)
        if data['detection']:
            r=data['detection'][p]['end_to_end']['wrist']
            card('module2-'+p,['T1D / MODULE 02','传感器当前状态检测',f'PhysioCGM · 7 人 · {p.upper()} · PPG + ACC',f"事件召回：{r['event_recall']*100:.1f}%（未达目标）",f"时间覆盖：{r['coverage']*100:.1f}% / 误报：{r['false_alerts_per_person_day']:.2f} 次/人日",'验证约束下工作点失效；不支持报警应用']+tail)
    manifest={'run_id':data['run_id'],'hash_format':'JSON canonical sorted compact; SVG UTF-8 with LF; PNG binary',
              'source_sha256':hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
              'cards':{p.name:hashlib.sha256(p.read_text(encoding='utf-8').encode() if p.suffix=='.svg' else p.read_bytes()).hexdigest() for p in sorted(dest.iterdir()) if p.suffix in ['.png','.svg'] and p.stem in ['overview','module1-loso','module1-temporal','module2-loso','module2-temporal']}}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Exported traceable PNG/SVG cards',data['run_id'])


if __name__=='__main__':main()
