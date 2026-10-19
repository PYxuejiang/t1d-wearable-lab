"""Publish aggregate-only beat benchmark report and evidence card."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]

def main():
    r=json.loads((ROOT/'docs/acceptance/PPG_CAPTURE1.json').read_text());digest=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='ppgcap-'+digest[:12]
    a=r['results']['heldout/calibrated/v5_peaks/raw'];b=r['results']['heldout/calibrated/dual_average/raw'];delta=r['paired_differences']['calibrated/f1'];hr=r['paired_differences']['calibrated/hr_mae_bpm']
    lines=['# PPG_CAPTURE1：心率误差与心搏对应能力分别评价','','2026-10-19。'+run+'。协议在成绩生成前提交32c7b1d；保留V5低血糖1/30失败。','',
    '## 本轮结果', '',f"新双移动平均方法未支持改善：留出宏F1 {a['f1']:.2%} → {b['f1']:.2%}；按人配对差{delta['mean']*100:+.3f}个百分点，探索性95%区间[{delta['95_interval'][0]*100:+.3f}, {delta['95_interval'][1]*100:+.3f}]个百分点。不是临床准确率。",'',
    '|方法|宏F1|心率MAE bpm|匹配相邻PPI MAE ms|相邻参考间期匹配比例|心率输出窗比例|','|---|---:|---:|---:|---:|---:|']
    for name,v in [('原V5峰值规则',a),('双移动平均改编',b)]:lines.append(f"|{name}|{v['f1']:.2%}|{v['hr_mae_bpm']:.3f}|{v['ppi_mae_ms']:.2f}|{v['ppi_pair_coverage']:.2%}|{v['hr_output_fraction']:.1%}|")
    lines += ['',f"心率MAE差（新−旧）{hr['mean']:+.3f} bpm，95%区间[{hr['95_interval'][0]:+.3f},{hr['95_interval'][1]:+.3f}]。PPI误差只针对参考与预测均相邻的匹配对；只有约30%间期可匹配，不能把约41ms写成全部间期的误差。",'',
    '先在每个受试者内等权活动，再在10人上等权汇总。S6只有静坐，其余9人两活动；不是按窗口数量加权。开发10份、留出19份，共607个完整30秒窗（含每记录4个校准窗），464组评价核对。', '',
    '|留出活动|旧方法F1|新方法F1|记录数|','|---|---:|---:|---:|']
    for act in ['sitting','walking']:lines.append(f"|{act}|{a['by_activity'][act]['f1']:.2%}|{b['by_activity'][act]['f1']:.2%}|{a['by_activity'][act]['records']}|")
    lines += ['', '## 对齐敏感性是重要限制', '', '|参考处理|旧方法F1|新方法F1|','|---|---:|---:|']
    for view in ['calibrated','fixed_200ms','unadjusted','index_origin_zero']:
        x=r['results']['heldout/'+view+'/v5_peaks/raw'];y=r['results']['heldout/'+view+'/dual_average/raw'];lines.append(f"|{view}|{x['f1']:.2%}|{y['f1']:.2%}|")
    lines += ['',f"主结果使用每记录首120秒ECG参考选出的共享偏移，限0–0.6秒；留出{r['lag_upper_boundary_records']['heldout']}/19记录触及上界。因此低F1可能同时包含峰值错误、剩余设备/滤波延迟或延迟变化，**不能仅凭本轮结果判定PPG峰值法本身只有约48%的能力**。没有扩展本轮偏移范围或看全测试段后优化对齐。",'',
    '一基/零基差1/700秒影响很小，不能解释固定200ms与校准主结果的明显差距。下一轮先在开发S1–S5核查原始/滤波峰时间与已知延迟，制定新的对齐协议；这批留出成绩现已查看，后续修改需标为同队列探索，不能再次宣称未触碰测试。', '',
    '## 质量拒绝与覆盖', '',f"开发候选0/0.3/0.5/0.7/0.9全部保留，选中阈值{r['sqi_threshold']}，即本轮不拒绝窗口。0.7阈值在开发步行只保留约22.9%窗口，0.9更少，未过两活动各70%的预设覆盖门槛；不能只展示被保留的干净片段。",'',
    f"两方法在核心窗的保留率均100%，可输出评分核心时间占校准后原始时间{a['covered_reference_time_fraction']:.2%}（每30秒只评分27秒，尾窗计时间损失）。这是PPG-DaLiA基准的分母，**不能声称PhysioCGM原72.8%覆盖提高到88%**。",'',
    '## 验收与复现', '',
    '工程检查通过：原文件SHA256、源R峰窗边界、全部29条记录和缺S6步行、每记录校准选择、5个SQI候选、464组计数与相邻间期、607窗。动态规划独立核对一对一最大匹配数量；另一时序扫描核对配对与PPI误差。初次复核在开发均值精确相等检查失败，核查为求和顺序产生5.55e-17差异，改为1e-12绝对容差；预测、参考、选择与方法均未改动，失败日志保留本地。', '',
    '运行`python scripts/run_ppg_capture.py`生成本地逐窗参考/预测和开发选择（拒绝覆盖）；`python scripts/verify_ppg_capture.py`核对并导出汇总；`python scripts/export_ppg_capture.py`生成本报告/卡。再次查看已完成结果只运行后两项，不重复提取。', '',
    '来源和许可：[PPG-DaLiA审计](PPG_DALIA_AUDIT.zh-CN.md)。方法：[预先冻结协议](METHOD_PPG_CAPTURE1.zh-CN.md)，参考[Elgendi等原始研究](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0076585)；没有复制外部实现，不借用原文指端PPG成绩。', '',
    '没有低血糖标签，没有自主神经/免疫机制因果结论，没有真实医疗报警。信号子任务和原两个疾病模块分开验收。公共仓库仅含汇总，逐窗峰/原始波形留在忽略目录。']
    (ROOT/'docs/PPG_CAPTURE_REPORT.zh-CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1200),'#f7f4f2');d=ImageDraw.Draw(im)
    card=['T1D / PPG BEAT VALIDATION','能估计心率，不等于已验证脉搏间期',f"参考辅助 F1：{a['f1']:.2%} → {b['f1']:.2%} · 未支持改善",f"配对差 {delta['mean']*100:+.3f} pp · 95%区间跨零",f"心率MAE {a['hr_mae_bpm']:.2f} → {b['hr_mae_bpm']:.2f} bpm",f"相邻间期匹配仅 {a['ppi_pair_coverage']:.1%} / {b['ppi_pair_coverage']:.1%}",'首120秒参考校准；5/19留出记录偏移触及上界','10人 · 19份留出记录 · 464组独立核对','信号基准；没有低血糖效能提升结论',run]
    for i,line in enumerate(card):d.text((85,80+i*105),line,font=ImageFont.truetype(str(font),44 if i==1 else 34),fill='#725365' if i==2 else '#302c33')
    path=ROOT/'showcase/public/cards/ppg-capture-v1.png';im.save(path)
    (path.parent/'ppg-capture-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print(run)
if __name__=='__main__':main()
