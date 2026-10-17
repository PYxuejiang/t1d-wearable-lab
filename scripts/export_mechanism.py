"""Export complete v3 findings, including failed detection and gained coverage."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
LABELS={'clock':'纯时间','personal_raw':'个人精简特征','personal_residual':'个人活动残差','pooled_residual':'共享活动残差','pooled_fallback':'共享模型+ECG后备','pooled_mask_clock':'仅缺失模式+时间'}


def main():
    record=json.loads((ROOT/'docs/acceptance/V3_MECHANISM1.json').read_text());results=record['results'];primary=record['primary']
    digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest();run='mechanism-'+digest[:12]
    old=record['same_opportunity_v2']['static_selected'];gain=record['paired_differences']['pooled_residual__to__pooled_fallback/end_to_end']['coverage']
    diagnostic=[x for x in record['failure_diagnostics'] if x['arm']=='pooled_fallback' and x['budget']==1]
    misses={k:sum(x['miss_reasons'][k] for x in diagnostic) for k in diagnostic[0]['miss_reasons']}
    timing={k:sum(x['unmatched_alert_timing'][k] for x in diagnostic) for k in diagnostic[0]['unmatched_alert_timing']}
    oracle=sum(x['fixed_policy_perfect_point_oracle_matched_events'] for x in diagnostic)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),facecolor='#fffefa')
    axes[0].bar(['Original wrist','ECG failover'],[old['coverage']*100,primary['coverage']*100],color=['#929f9b','#377b68'])
    axes[0].axhline(80,color='#b57b45',linestyle='--',label='Internal80% target');axes[0].legend(frameon=False)
    axes[0].set_ylabel('Subject-macro supported time (%)');axes[0].set_ylim(0,100);axes[0].set_title('Availability improves; detection still fails')
    axes[1].barh(['No input','Never above threshold','High score, no event alert'],list(misses.values()),color=['#9aa4a0','#c39367','#577b70'])
    axes[1].invert_yaxis();axes[1].set_xlabel('Missed reference events (primary budget1/day)');axes[1].set_title('All30 missed events remain in the denominator')
    fig.text(.02,.01,run+' | Seen7-person cohort; chest sensor added; retrospective exploratory results',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(ROOT/'docs/figures/mechanism-v3.png',dpi=170);plt.close(fig)
    def line(label,r):return f"|{label}|{r['matched_events']}/{r['reference_events']}|{r['event_recall']:.1%}|{r['false_alerts_per_person_day']:.3f}|{r['coverage']:.1%}|"
    table=[line('旧v2静态：个人验证、预算1',old)]
    for arm,label in LABELS.items():table.append(line(label+'：共同验证、预算1',results[f'{arm}/pooled_validation/b1/end_to_end']))
    secondary=[line(label+'：共同验证、预算2',results[f'{arm}/pooled_validation/b2/end_to_end']) for arm,label in LABELS.items()]
    calibration=[]
    for arm,label in LABELS.items():
        for mode,mlabel in [('personal_validation','个人验证'),('pooled_validation','共同验证')]:
            calibration.append(line(label+' / '+mlabel,results[f'{arm}/{mode}/b1/end_to_end']))
    chosen=[s for s in record['selections'] if s['arm']=='pooled_fallback' and s['calibration_mode']=='pooled_validation' and s['budget']==1][0]
    selected_model=next(p['parameters'] for p in record['selected_parameters'] if p['arm']=='pooled_fallback')
    text=f'''# 指标改进第三轮：先修复可用性，检测效果仍未达标

运行标识`{run}`；固定协议`configs/mechanism_v3_1.json`，方法解释见[METHOD_CHANGE_V3](METHOD_CHANGE_V3.zh-CN.md)。**336组独立复算通过；预设主要低血糖检测目标失败。**

## 本轮真正改善了什么

旧腕部完整输入的宏时间覆盖 **{old['coverage']:.2%}**，腕部或ECG后备策略 **{primary['coverage']:.2%}**，按人配对增加 **{gain['mean']*100:.2f}个百分点**，探索性95%区间 **[{gain['95_interval'][0]*100:.2f}, {gain['95_interval'][1]*100:.2f}]个百分点**。全30次测试事件中，至少一次有输入的事件由25次增加为27次；这些事件的总分母始终不变。

这是可用性策略改善，来自**增加胸带ECG后备**。不是纯手表升级、真实设备在线率、临床有效性或单独传感器精度验证。完整流程训练机会也变化，不能只将成绩差归因于新增某一特征；共同腕部视图与缺失模式控制另列验收JSON。

![覆盖与漏检分解](figures/mechanism-v3.png)

## 主预算：没有藏掉失败

下表所有新版均按预先固定的共同验证参数选择、测试预算标签1展示；**预算是验证期约束，测试实际误报必须另看**。30次事件全部保留，宏召回按7人等权，不等于命中总数/30。

|路线与验证选参|命中/总事件|宏事件召回|测试误报/参考人日|宏时间覆盖|
|---|---:|---:|---:|---:|
{chr(10).join(table)}

预设主方案`pooled_fallback/pooled_validation/b1/end_to_end`的阈值为 **{chosen['threshold']:.4f}**，策略 **{chosen['policy']}**；验证期宏召回{chosen['validation']['event_recall']:.1%}，测试期 **{primary['matched_events']}/30**。不能看到更好的副方案后替换主方案。

训练内部留出选出的主方案模型参数为`{json.dumps(selected_model,ensure_ascii=False)}`。这次选择了逻辑回归C=1、均衡类别权重；确认/平滑策略没有在主预算验证准则下胜出，因此保留原上升沿，而不是强制新策略获胜。

## 漏检到底发生在哪

- {misses['no_input']}次：事件内完全没有可用输入。
- {misses['score_never_above_threshold']}次：事件内有输入，但分数从未达到已锁定阈值。
- {misses['above_threshold_without_event_alert']}次：事件内有高于阈值的分数，但当前报警状态/冷却没有在事件内发出报警。

同样可用机会、假设每个可用点的真实标签可完美识别，再经过本次固定报警策略，只能命中{oracle}/30次；这是**反事实诊断**，不是真实模型指标，也不证明任何学习算法能达到。它说明“有一次输入”的上限仍忽略了报警策略对相邻事件的限制。

主方案唯一未匹配报警发生在记录事件前30分钟内（{timing['within30min_before_onset']}次）。这个时序分解只作描述，**该报警仍保留为当前检测任务的误报**；没有移动CGM时钟或将它重命名为有效预警。来源时钟与参考延迟尚不能支持这种结论。其他预设路线的重复/提前/滞后报警分类与验证/测试正负分数分布在验收JSON中完整保留。

主要瓶颈不是仅由报警状态机造成：26次漏检连阈值都未越过。下一步必须核对分数与参考标签的关系、源对齐和信号信息量，而不是只延长冷却来压低误报。

## 次要预算2：有命中，但不能替代主目标

|预设次要路线|命中/总事件|宏事件召回|测试误报/参考人日|宏时间覆盖|
|---|---:|---:|---:|---:|
{chr(10).join(secondary)}

后备方案在此工作点命中2/30次，宏召回17.1%，测试误报1.858次/参考人日。宏召回由各人事件数决定，不能把17.1%写成总体事件命中比例；2/30为6.7%。它未达到主要1次误报预算或80%召回要求，也没有建立稳定传感器检测收益。

## 个人与共同验证：全部固定对照

|路线 / 报警选参来源（预算1）|命中/总事件|宏事件召回|测试误报/参考人日|宏时间覆盖|
|---|---:|---:|---:|---:|
{chr(10).join(calibration)}

共同模型会使用这7人的早期训练期与既往CGM标签；共同报警参数使用其较早验证期。不是无标签个体校准，也不是新人的LOSO。只用缺失模式+时间的路线也可能命中事件，因此不能将后备组的任何命中都解释为ECG生理信息。

## 方法、参数和验收

冻结六条路线、每条10种超参数，嵌套训练时间留出选择模型；240条内部候选记录全部保留。外层验证选择阈值/4种报警策略，个人/共同选参分别保留，1/2次预算分开，完整流程/共同腕部两个视图形成336组测试结果。确认/EMA/提醒策略在验证期无优势时仍可能选回原上升沿，不强制新方法获胜。

独立核对来源标签、输入时间、外层与内部边界、内部AP及全部候选选择排序、特征白名单、输入机会掩码、选中验证策略{record['selected_validation_configurations_verified']}个不同配置、全部测试的事件/报警/误报/延迟与时间覆盖。最大数值差为{record['maximum_metric_difference']:.3g}。所有路线完整结果在[V3_MECHANISM1.json](acceptance/V3_MECHANISM1.json)，未发布患者波形或逐点预测。

AP/AUC只在可评分参考点上评价，不同可用掩码不能相减当作传感器增益。后备对腕部的AP配对差只在共同腕部视图解释；后备与缺失模式控制可在相同联合输入机会比较。覆盖和全部事件召回始终报告完整分母。

本轮修复了覆盖不足的一项限制，但还保留7人、30事件、曾见队列、稀少/单类内部留出、源时钟未证实等限制。既有ECG四记录捕获通过也不能证明目标波形、HRV或血糖标注正确。

```powershell
python scripts/run_mechanism.py
python scripts/verify_mechanism.py
python scripts/export_mechanism.py
python scripts/export_improvement.py
python -m pytest -q
```

本机实验已经完成；运行器拒绝覆盖`outputs/mechanism_v3_1`。不要重复训练以挑测试成绩。下一轮应先核对原始加工对齐与既有加工版本的配对时间证据，再验证更可靠RR/形态特征；不得按识别高分选时钟偏移。
'''
    (ROOT/'docs/MECHANISM_REPORT.zh-CN.md').write_text(text,encoding='utf-8')
    from PIL import Image,ImageDraw,ImageFont
    font=next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    im=Image.new('RGB',(1800,1200),'#f6f5ef');draw=ImageDraw.Draw(im)
    lines=['T1D / METHOD & PARAMETER AUDIT','覆盖改善，检测仍未达标','6条路线；嵌套时间调参；336组独立复算',
        f"宏时间覆盖：{old['coverage']:.1%} → {primary['coverage']:.1%}（增加胸带后备）",
        '主要1次误报预算：事件命中0/30；不是有效检测器','漏检：3次无输入；26次低于阈值；1次未触发',
        '7人既有队列；探索性；不是纯腕部或临床结果',run,'https://github.com/PYxuejiang/t1d-wearable-lab']
    for i,line in enumerate(lines):draw.text((100,110+i*105),line,font=ImageFont.truetype(str(font),52 if i==1 else 35),fill='#276c61' if i==3 else '#1d373b')
    card=ROOT/'showcase/public/cards/mechanism-v3.png';im.save(card)
    (ROOT/'showcase/public/cards/mechanism-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':digest,'png_sha256':hashlib.sha256(card.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
    print('Exported',run)


if __name__=='__main__':main()
