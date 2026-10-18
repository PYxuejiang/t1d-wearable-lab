"""Publish aggregate v4 evidence, including both ranking gain and failed alarms."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
LABELS={'mask_clock':'缺失+时间','early':'早期特征融合','ecg':'ECG专家','ppg':'PPG专家','eda':'EDA专家','late_mean':'专家平均','late_stack':'后期逻辑融合'}


def main():
    r=json.loads((ROOT/'docs/acceptance/V4_LATE_FUSION1.json').read_text());s=json.loads((ROOT/'docs/acceptance/SOURCE_TIME1.json').read_text())
    digest=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='fusion-'+digest[:12]
    results=r['results'];primary=r['primary'];before=results['late_stack/point/b1/end_to_end'];gain=r['paired_differences']['late_stack/point']['ap'];ci=gain['95_interval']
    ppg=results['ppg/point/b1/end_to_end'];misses={k:sum(x['miss_reasons'][k] for x in r['failure_diagnostics']) for k in r['failure_diagnostics'][0]['miss_reasons']}
    tables={}
    for budget in [1,2]:
        rows=[]
        for weight,label in [('point','点权重'),('run','片段权重')]:
            for arm,name in LABELS.items():
                a=results[f'{arm}/{weight}/b{budget}/end_to_end']
                rows.append(f"|{name} / {label}|{a['ap']:.4f}|{a['matched_events']}/{a['reference_events']}|{a['event_recall']:.1%}|{a['false_alerts_per_person_day']:.3f}|{a['coverage']:.1%}|")
        tables[budget]='\n'.join(rows)
    pcontrast=r['posthoc_modality_contrasts']['comparisons']['ppg/point']
    report=f'''# 第四轮：后期融合与低值片段权重

日期2026-10-18，运行`{run}`。392组独立复算通过，**主要事件检测仍失败**。方法与来源详见[METHOD_CHANGE_V4](METHOD_CHANGE_V4.zh-CN.md)，所有对照与次预算均保留。

## 可复核的排序改善

同一批测试点、同一联合可用掩码，后期融合的点权重方案AP **{before['ap']:.4f}**，片段权重方案 **{primary['ap']:.4f}**。按7人配对AP差 **+{gain['mean']:.4f}**，2,000次按人bootstrap的未校正探索性95%区间 **[{ci[0]:.4f}, {ci[1]:.4f}]**。这是已看过队列的整个训练方案比较，基础模型选择也随权重变化，不是对片段权重机制的独立因果证明。

AP改善没有转成事件检测改善：点权重方案命中{before['matched_events']}/30、误报{before['false_alerts_per_person_day']:.3f}；预设片段权重主方案命中 **{primary['matched_events']}/30**、误报 **{primary['false_alerts_per_person_day']:.3f}/参考人日**。相对同权重早期融合及缺失+时间控制，AP差区间仍跨零。没有宣布可靠生理增益或临床可用。

![排序与报警结果](figures/late-fusion-v4.png)

## 全部主预算结果

预算1是验证期约束，不保证测试误报≤1。事件宏召回按人等权，与命中数/30不同；所有30次参考事件均保留。

|路线 / 权重|宏AP|命中/事件|宏事件召回|实际误报/参考人日|宏时间覆盖|
|---|---:|---:|---:|---:|---:|
{tables[1]}

单模态有效点可能不同，不应把表内所有AP直接相减。主要配对比较使用相同联合可用掩码；共同腕部视图与全部逐人汇总在验收JSON。

## PPG专用模型：一个有限的后续线索

预先列出的PPG/点权重对照命中 **{ppg['matched_events']}/30**（总体10.0%，宏召回{ppg['event_recall']:.2%}），误报 **{ppg['false_alerts_per_person_day']:.3f}/参考人日**，覆盖 **{ppg['coverage']:.2%}**。验证期选中逻辑回归C=0.1和连续两点确认。命中只来自c2s02的1次、c2s05的2次；其他5人没有命中。它未达到80%召回/80%覆盖，且不是本轮预设主方案。

看完结果后，对冻结分数补做了PPG/EDA与同权重时间+缺失控制的共同腕部掩码配对分析，明确记为事后描述，未重训练或修改阈值。PPG点权重AP差为{pcontrast['ap']['mean']:+.4f}，区间[{pcontrast['ap']['95_interval'][0]:.4f}, {pcontrast['ap']['95_interval'][1]:.4f}]；不作为确认性成功。旧v2静态主预算1/30、本轮PPG3/30也不能单靠两次增加就证明泛化改善。

## 主方案漏检分解

{misses['no_input']}次无输入；{misses['score_never_above_threshold']}次有输入但未达阈值；{misses['above_threshold_without_event_alert']}次有高分但事件期没有报警。没有修改时钟、事件终点或冷却来重新认领漏检。胸带后备的82.84%覆盖属于上一轮已有策略，本轮未再声称覆盖增加。

## 次要预算2：全部报告

|路线 / 权重|宏AP|命中/事件|宏事件召回|实际误报/参考人日|宏时间覆盖|
|---|---:|---:|---:|---:|---:|
{tables[2]}

## 来源、验收与复现边界

- 原始34,218个特征参考标签全部一致。10人各1个固定作者加工片段的CGM索引、时间和值与原始记录一致；三个可匹配腕部片段均对应UTC−5。其余7个首片段没有可用非恒定腕部序列，不能推断偏移。原始CGM/胸带物理时钟仍缺独立校准。来源验收见[SOURCE_TIME1](acceptance/SOURCE_TIME1.json)。
- 30个基础候选内部AP和选择排序、28个选中验证工作点、训练片段/类别/按人权重及全部392组测试独立检查；最大指标差{r['maximum_metric_difference']:.3g}。
- 独立从内层未参与基础拟合的分数重建融合输入并重拟合融合器；验证/测试分数最大差{r['stack_refit_maximum_score_difference']:.3g}。没有把训练内预测用于融合训练。基础选参与融合拟合共用内层留出，重拟合专家也可能造成分数分布变化，局限保留。
- 仍为7人早期个体数据参与训练、未来时间留出，不是新人LOSO或外部验证。所有原始数据、加工片段与逐点预测仅本地保存，公开汇总与自写代码。

本次新增训练全部完成，不能反复调这一测试集。下一优先级是验证PPG/RR与原始短窗形态是否提供新增信息，并把表现差的5人保留；先冻结质量与特征协议，再做模型比较。全项目事件验收仍未通过。

```powershell
python scripts/run_late_fusion.py
python scripts/verify_late_fusion.py
python scripts/export_late_fusion.py
```

已有输出目录时训练程序拒绝覆盖；复核既有结果只运行验证和导出。完整验收：[V4_LATE_FUSION1.json](acceptance/V4_LATE_FUSION1.json)。
'''
    (ROOT/'docs/LATE_FUSION_REPORT.zh-CN.md').write_text(report,encoding='utf-8')
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),facecolor='#fffefa')
    axes[0].bar(['Point weights','Low-run weights'],[before['ap'],primary['ap']],color=['#9baba5','#377b68'])
    axes[0].set_ylabel('Subject-macro average precision');axes[0].set_ylim(0,.14);axes[0].set_title('Exploratory ranking gain, same score mask')
    axes[1].bar(['Primary stack','PPG comparator'],[primary['matched_events'],ppg['matched_events']],color=['#bc977b','#577b70'])
    axes[1].set_ylim(0,30);axes[1].set_ylabel('Matched events / all30');axes[1].set_title('Overall alarm goal still failed')
    fig.text(.02,.01,run+' | Seen7-person cohort; no clinical efficacy claim',fontsize=8);fig.tight_layout(rect=[0,.04,1,1])
    fig.savefig(ROOT/'docs/figures/late-fusion-v4.png',dpi=170);plt.close(fig)
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1200),'#f6f5ef');draw=ImageDraw.Draw(im)
    lines=['T1D / MODALITY SPECIALISTS','排序有改善，事件检测仍未达标',f"后期融合 AP：{before['ap']:.4f} → {primary['ap']:.4f}",
           f"配对差 +{gain['mean']:.4f}  ·  探索性区间 [{ci[0]:.4f}, {ci[1]:.4f}]",
           f"预设主方案 {primary['matched_events']}/30；误报 {primary['false_alerts_per_person_day']:.3f}/参考人日",
           f"PPG 对照 {ppg['matched_events']}/30；误报 {ppg['false_alerts_per_person_day']:.3f}；覆盖 {ppg['coverage']:.1%}",
           '392 组独立复算 · 7 人已见队列 · 不能替代主要验收',
           '来源标签核对通过；物理时钟仍缺独立校准',run,'github.com/PYxuejiang/t1d-wearable-lab']
    for i,line in enumerate(lines):draw.text((90,90+i*100),line,font=ImageFont.truetype(str(font),48 if i==1 else 34),fill='#276c61' if i==2 else '#1d373b')
    path=ROOT/'showcase/public/cards/late-fusion-v4.png';im.save(path)
    (path.parent/'fusion-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print('Exported',run)

if __name__=='__main__':main()
