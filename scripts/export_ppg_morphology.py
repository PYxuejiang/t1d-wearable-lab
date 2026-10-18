"""Render verified aggregate morphology results without patient traces."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
NAMES={'coarse':'旧PPG粗特征','quality_time':'质量＋时间控制','morphology':'粗特征＋新增形态'}

def main():
    r=json.loads((ROOT/'docs/acceptance/V5_PPG_MORPH1.json').read_text(encoding='utf-8'));p=r['primary'];before=r['results']['coarse/b1']
    digest=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='ppgmorph-'+digest[:12]
    rows=[]
    for budget in [1,2]:
        for arm,label in NAMES.items():
            a=r['results'][f'{arm}/b{budget}'];ppv=f"{a['micro_event_precision']:.1%}" if a['micro_event_precision'] is not None else 'NA'
            rows.append(f"|{label}|{budget}|{a['ap']:.4f}|{a['matched_events']}/30|{a['event_recall']:.1%}|{a['events_hit_within15min']}/30|{a['false_alerts_per_person_day']:.3f}|{ppv}|{a['coverage']:.1%}|")
    contrasts=[]
    for arm in ['coarse','quality_time']:
        for metric in ['ap','event_recall']:
            a=r['paired_differences'][arm][metric];ci=a['95_interval']
            contrasts.append(f"|新增形态 − {NAMES[arm]}|{metric}|{a['mean']:+.4f}|[{ci[0]:+.4f}, {ci[1]:+.4f}]|{a['n']}|")
    people=[]
    for a in r['metrics_by_subject']:
        if a['arm']=='morphology' and a['budget']==1:
            people.append(f"|{a['subject']}|{a['matched_events']}/{a['reference_events']}|{a['events_hit_within15min']}|{a['false_alerts_per_person_day']:.3f}|{a['coverage']:.1%}|")
    misses={k:sum(x['miss_reasons'][k] for x in r['failure_diagnostics']) for k in r['failure_diagnostics'][0]['miss_reasons']}
    text=f'''# 第五轮：PPG短窗形态、脉搏间期和质量

日期2026-10-18，运行`{run}`。本轮只沿用户指定的PPG方向增加信息。42组指标、9个内层候选和6个选中验证工作点独立复算。**原整体报警目标：{r['effect_status']}**。

预设主方案命中 **{p['matched_events']}/30**，旧PPG对照 **{before['matched_events']}/30**；实际误报 **{p['false_alerts_per_person_day']:.3f}/参考人日**，覆盖 **{p['coverage']:.1%}**。所有7人、30事件保留。工程通过不代表临床效用。

## 方法与隔离

原始64Hz BVP的过去300秒，因果0.5–5Hz三阶滤波，分成10个30秒窗口，分别计算脉搏间期、形态和质量，再汇总中位数/IQR。新增31个数值特征及其缺失标记：间期SD/RMSSD、脉宽、上升比例、归一化面积、幅度变异、偏度、模板相似、频带集中、自相关与有效脉搏支持。无未来样本。坏间期两侧不拼接计算RMSSD。

PPG给出的是PPI/脉率变异描述，不是真实ECG RR；合成波形测试通过不等于自由生活脉搏准确率已证实。模板相似、有效脉搏支持也不能单独证明信号正确。幅度归一化和滤波会丢失部分细节，是本轮局限。

新特征每人仅用训练期、不依赖血糖标签的中位数/IQR归一化，缺失值经归一化后填零并另给标记。旧粗特征继续沿用训练正常期归一化以精确复现基线；推理无CGM输入。全部三路保留同一旧腕部可用掩码；本轮没有因质量剔除难例，也不能提高固定72.8%的覆盖。

外层60/20/20时间划分与60分钟输入/15分钟参考边界清除不变；训练内75/25选三种固定模型（LR C0.1、HGB7叶、ExtraTrees深度5），外层验证选择四种报警规则和101分位阈值。1次误报预算是主工作点，2次是次工作点，均先写入选择清单再评分。旧对照与V4的预测最大绝对差 **{r['coarse_v4_maximum_score_difference']:.3g}**，策略及阈值一致。

源会话重叠时选第一个完整的字典序会话；与旧特征的重叠选择可能不同。保持已有独立审计偏移，无按疾病分数调时间；CGM/胸带物理时钟局限仍存在。

## 全部结果

|路线|验证预算|宏AP|全部事件命中|宏事件召回|前15分钟命中|误报/参考人日|事件总体PPV|宏覆盖|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

预算不保证未来测试满足同样负担。总体命中率=命中数/30，不能与按人等权宏召回混用。零报警的PPV为NA。前15分钟命中是评分前登记的次要描述，不改变事件定义或选模。

## 同掩码配对差

|比较|指标|按人均值差|探索性95%区间|人数|
|---|---|---:|---|---:|
{chr(10).join(contrasts)}

2,000次按人bootstrap，区间未作多重校正。相同已见7人队列，不是独立外部确认。AP增加与事件收益分别解释；仅有一个点估计改善不能宣布稳定有效。

## 主方案逐人结果

|受试者|命中/事件|前15分钟命中|误报/参考人日|覆盖|
|---|---:|---:|---:|---:|
{chr(10).join(people)}

漏检分解：无输入{misses['no_input']}次、有输入但分数未达阈值{misses['score_never_above_threshold']}次、分数达阈值但事件期未报警{misses['above_threshold_without_event_alert']}次。没有删除这些失败或重新认领发作前报警。

## 目标复核与后续

原80%宏召回/≤1误报/80%覆盖是内部愿景，不是临床标准。固定72.8%覆盖的本轮实验不可能通过第三项，因此新增信息验收与整体报警分开。详见[目标合理性与论文/产品对照](GOAL_REVIEW.zh-CN.md)。其中未来“宏召回+10个百分点”等提案不用于追认本轮成功。

若新增信息不能支持稳定事件收益，下一阶段仍限于有标注公开PPG基准的峰值与质量验证，不继续扩大同一批粗特征模型搜索；不擅自切换CGM融合或夜间终点。全部失败记录保留。

```powershell
python scripts/extract_ppg_morphology.py
python scripts/run_ppg_morphology.py
python scripts/verify_ppg_morphology.py
python scripts/export_ppg_morphology.py
```

提取只复用有哈希验证的完整受试者文件；训练拒绝覆盖已有运行目录。复核既有结果只需运行后两条。原始波形、个体特征和逐点分数留在忽略目录；公开自写代码、配置、逐人汇总及[V5验收](acceptance/V5_PPG_MORPH1.json)。
'''
    (ROOT/'docs/PPG_MORPHOLOGY_REPORT.zh-CN.md').write_text(text,encoding='utf-8')
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1200),'#f6f5ef');d=ImageDraw.Draw(im)
    lines=['T1D / PPG MORPHOLOGY','先增加信号信息，再评价报警目标',
           f"旧PPG {before['matched_events']}/30 → 新增形态 {p['matched_events']}/30",
           f"误报 {p['false_alerts_per_person_day']:.3f}/参考人日 · 覆盖 {p['coverage']:.1%}",
           f"前15分钟命中 {p['events_hit_within15min']}/30 · 整体目标 {r['effect_status']}",
           '42组独立复算 · 同一掩码 · 全部7人30事件保留',
           '脉搏可计算不等于准确；PPI不等于ECG RR',
           '已见队列探索性实验；目标调整不能追认成功',run,'github.com/PYxuejiang/t1d-wearable-lab']
    for i,line in enumerate(lines):d.text((85,85+i*100),line,font=ImageFont.truetype(str(font),46 if i==1 else 34),fill='#276c61' if i==2 else '#1d373b')
    path=ROOT/'showcase/public/cards/ppg-morphology-v5.png';im.save(path)
    (path.parent/'ppg-morphology-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print('Exported',run)

if __name__=='__main__':main()
