"""Aggregate contextual/correction report; no per-anchor patient records published."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    record=json.loads((ROOT/'docs/acceptance/CONTEXT_V1_1.json').read_text())
    run='context-'+hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:12]
    summary=record['summary'];primary=record['paired_gain']['wearable_time__to__combined'];gain=primary['ap']
    names=['clock','context_time','wearable_time','combined'];labels=['Clock','Context + clock','Wearable + clock','Combined']
    palette=['#183d40','#619a8b','#d69a68','#909ca3']
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),facecolor='#fffefa')
    axes[0].barh(labels,[summary[k]['raw']['ap']['mean'] for k in names],color=palette);axes[0].invert_yaxis();axes[0].set_xlabel('Mean AP (8 positive-test subjects)');axes[0].set_title('Context does not give stable AP gain')
    axes[1].bar(['Raw','Calibrated','Training prior'],[summary['wearable_time'][v]['brier']['mean'] for v in ['raw','calibrated','training_prior']],color=palette[:3]);axes[1].set_ylabel('Mean Brier (11 subjects; lower is better)');axes[1].set_title('Calibration vs a necessary simple baseline')
    fig.text(.02,.01,run+' | Exploratory source-row holdout; no event-alarm efficacy claim',fontsize=8);fig.tight_layout(rect=[0,.04,1,1])
    dest=ROOT/'docs/figures';dest.mkdir(exist_ok=True,parents=True);fig.savefig(dest/'context-calibration.png',dpi=170);plt.close(fig)
    body='\n'.join(f"|{label}|{summary[k]['raw']['ap']['mean']:.4f}|{summary[k]['raw']['roc_auc']['mean']:.4f}|{summary[k]['raw']['sensitivity']['mean']:.1%}|{summary[k]['raw']['specificity']['mean']:.1%}|" for k,label in zip(names,['纯时间','情境+时间','穿戴+时间','穿戴+情境+时间']))
    report=f'''# 情境信息与个体分数校准：本轮验证报告

运行标识：`{run}`；协议 `configs/smartwatch_context_v1_1.json`。11名受试者全部保留，8名测试期含正类。工程与评价验收通过，新增情境的主要AP增益未获支持；不替代事件报警目标。

## 同样测试范围下的主要结果

|输入|原始分数AP|AUC|点敏感度|点特异度|
|---|---:|---:|---:|---:|
{body}

主要配对对照为“穿戴+时间”到“穿戴+情境+时间”：AP差值 **{gain['mean']:.4f}**，按人2,000次bootstrap的探索性95%区间 **[{gain['95_interval'][0]:.4f}, {gain['95_interval'][1]:.4f}]**。敏感度增加并没有建立无代价的改进，平均特异度下降；两项必须同时解释。

本轮边界每侧删除150行，和上轮120行范围不同，**不能拿本轮0.1561与上轮0.1887直接推断算法退步或收益**。上轮正向AP证据保留；本轮只做相同测试行之间的配对比较，已独立核对。

![同范围AP与校准对照](figures/context-calibration.png)

## 校准为什么没有自动变成检测能力提升

穿戴+时间分数的平均Brier：原始 **{summary['wearable_time']['raw']['brier']['mean']:.4f}**、验证期sigmoid/常数退路校准后 **{summary['wearable_time']['calibrated']['brier']['mean']:.4f}**、训练期正类比例的固定概率基线 **{summary['wearable_time']['training_prior']['brier']['mean']:.4f}**。校准明显修正了原始加权分类器的过高分数，但未稳定超过简单概率基线；不能单凭Brier下降宣称能可靠报警。

校准只读取验证期标签，不改模型训练或用测试标签拟合。正斜率sigmoid保持非递减次序；截断极端logit可能产生并列分数。非正斜率退回验证期正类比例，不把坏模型反向排列以制造排序收益。穿戴+时间组7人使用sigmoid，4人常数退路，其中2人验证期单类。相关测试期漏识别、NA和分母均保留。

## 数据和信息边界

- 输入只有腕部汇总、时间以及新增的 `IOB`、`time_since_lastmeal_ord`。CGM及源低血糖标签从不进入输入列。
- 作者`IOB`是每次既往注射在其后4小时按1/0.75/0.5/0.25构造的无量纲活动指数；它不是体内剩余剂量，不能用于给药建议。
- 用餐字段有缺失：受试者13整列缺失、注射活动指数全为0。保留该人并显式记录；源零值不证明实际没有注射或进食。
- 本轮需要手工/源日记情境，不能称为纯传感器升级，也没有新增硬件收益结论。
- 源CSV仍缺完整时间戳。源行顺序留出只是探索性替代；150行边界是在名义分钟行假设下覆盖240分钟情境与15分钟标签确认的保守设置，不证明真实时间完整。
- 初始120行边界版本已隔离：运行在尝试中断前已完成，但未纳入效果分析、未用于选择高分。登记于 `docs/acceptance/CONTEXT_V1_ABORTED.json`，本地输出保留。

## 验收证据与复现

132组（11人×4组输入×原始/校准/概率基线）独立复算通过，最大数值差异为 `{record['maximum_metric_difference']:.3g}`，校准映射复算差异 `{record['maximum_calibration_difference']:.3g}`。核对了源标签、同测试行、特征白名单、模型候选选择、验证阈值、校准训练来源和行边界。

```powershell
python scripts/run_contextual.py --config smartwatch_context_v1_1.json
python scripts/verify_contextual.py
python scripts/export_improvement.py
python scripts/export_context_report.py
python -m pytest -q
```

运行器对已存在实验目录停止，避免静默覆盖；同机已完成本轮，不要重复运行以挑选成绩。原始数据与逐点预测继续被Git忽略。完整汇总见 `docs/acceptance/CONTEXT_V1_1.json`。

## 下一步

这轮没有支持继续无界叠加日记特征或学习器。下一优先级是PhysioCGM心搏形态与伪影质量、源时钟证据，及更可信的原始带时间数据。后续需要在新协议下判断改善来自真实生理信息、个体适应还是生活时间规律；既有测试已查看，所有再利用仍标探索性。
'''
    (ROOT/'docs/CONTEXT_REPORT.zh-CN.md').write_text(report,encoding='utf-8')
    from PIL import Image,ImageDraw,ImageFont
    fonts=[Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')];font=next(p for p in fonts if p.exists())
    im=Image.new('RGB',(1800,1200),'#f6f5ef');draw=ImageDraw.Draw(im)
    lines=['T1D / CONTEXT & CALIBRATION','情境信息：本轮未确认稳定增益','11人；源行顺序留出；新增情境需日记记录',f"同范围AP：穿戴+时间 {summary['wearable_time']['raw']['ap']['mean']:.3f} → 合并情境 {summary['combined']['raw']['ap']['mean']:.3f}",f"Brier：原始 {summary['wearable_time']['raw']['brier']['mean']:.3f} → 校准 {summary['wearable_time']['calibrated']['brier']['mean']:.3f}；简单先验 {summary['wearable_time']['training_prior']['brier']['mean']:.3f}",'校准改善原始分数，尚未稳定超过简单概率基线','缺完整时间戳；探索性；没有事件报警效能结论',run,'https://github.com/PYxuejiang/t1d-wearable-lab']
    for i,line in enumerate(lines):draw.text((100,110+i*105),line,font=ImageFont.truetype(str(font),52 if i==1 else 35),fill='#276c61' if i in [3,4] else '#1d373b')
    card=ROOT/'showcase/public/cards/context-calibration.png';im.save(card)
    (ROOT/'showcase/public/cards/context-manifest.json').write_text(json.dumps({'run_id':run,'acceptance_sha256':hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'png_sha256':hashlib.sha256(card.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
    print('Exported contextual report, plot and card',run)


if __name__=='__main__':main()
