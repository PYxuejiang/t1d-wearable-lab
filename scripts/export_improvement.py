"""Export aggregate improvement ledger without replacing v1 evidence."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    stages={}
    for stage in ['V2_1','V2_2','COHORT_SW1','COHORT_SW_PERSONAL1','CONTEXT_V1_ABORTED','CONTEXT_V1_1']:
        p=ROOT/'docs/acceptance'/f'{stage}.json'
        if p.exists():stages[stage]=json.loads(p.read_text(encoding='utf-8'))
    run='improve-'+hashlib.sha256(json.dumps(stages,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:12]
    data={'run_id':run,'scope':'Exploratory improvement ledger; separate from the original frozen v1 run','stages':stages}
    path=ROOT/'showcase/public/demo/improvement_data.json';path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    folder=ROOT/'data/raw/smartwatch_hypo'
    source={'dataset':'Zenodo15309060','license':'CC BY 4.0','doi':'https://doi.org/10.5281/zenodo.15309060','data_descriptor':'https://doi.org/10.1371/journal.pone.0325956','files':json.loads((folder/'download_manifest.json').read_text())}
    (ROOT/'docs/smartwatch_source_manifest.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
    p=stages['COHORT_SW_PERSONAL1'];r=p['summary'];gain=p['paired_gain']['clock__to__wearable_time'];ci=gain['ap']['95_interval']
    # Independent artifact for sharing this limited positive result.
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(1800,1200),'#f6f5ef');draw=ImageDraw.Draw(im)
    fonts=[Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')];font=next(x for x in fonts if x.exists())
    lines=['T1D / IMPROVEMENT LEDGER','个体化模型：初步排序改善','新公开队列 11 人；8 人测试期有正类',f"AP：{r['clock']['ap']['mean']:.3f} → {r['wearable_time']['ap']['mean']:.3f}",f"配对 AP 差值：+{gain['ap']['mean']:.3f}，95%区间 [{ci[0]:.3f}, {ci[1]:.3f}]",'AUC / 报警效能仍不稳定；整体目标未达标','行顺序留出，缺完整时间戳；探索性、未作多重校正',run,'https://github.com/PYxuejiang/t1d-wearable-lab']
    for i,line in enumerate(lines):draw.text((100,110+i*105),line,font=ImageFont.truetype(str(font),52 if i==1 else 35),fill='#276c61' if i==3 else '#1d373b')
    im.save(ROOT/'showcase/public/cards/improvement.png')
    report=f'''# 检测改进报告

运行标识：`{run}`。原始失败证据未覆盖；下列新实验均单独保存。

## 初步正向效果与不能越过的边界

新公开手表队列个体化实验，比较同一个人的相同测试行：纯时间基线平均 AP **{r['clock']['ap']['mean']:.4f}**，穿戴信号+时间 **{r['wearable_time']['ap']['mean']:.4f}**。8 名测试期有正类的受试者配对 AP 差值 **+{gain['ap']['mean']:.4f}**，按人 2,000 次 bootstrap 的探索性 95%区间 **[{ci[0]:.4f}, {ci[1]:.4f}]**。这是排序能力的候选改善；比较未作多重校正，不是确认性统计结论。另3人的测试期只有单类，AUC/AP记NA，仍保留其混淆矩阵和特异度。

穿戴+时间 AUC 为 **{r['wearable_time']['roc_auc']['mean']:.4f}**，相对纯时间基线的差值区间跨零。验证阈值下平均点敏感度 **{r['wearable_time']['sensitivity']['mean']:.1%}**；各人结果差异大，不能作为可靠低血糖报警器。没有宣布80%事件召回目标达标。

公开 CSV 缺日期/完整时间戳，采用原始行顺序前60%训练、中20%验证、末20%测试，边界两侧各删除120行。**不是已确认的前瞻性时间验证**，没有把行号换算成观察人日或事件时长。按小时与连续分钟行网格的一致性另作预先列出的99%子组检查；它不能排除整日缺失，也不用于挑选总体最优成绩。

模型不输入CGM、源低血糖标签、IOB或饮食记录；训练/验证内选择学习器和分类阈值。源数据的状态标签采用作者定义及参考回填，和PhysioCGM源`<70mg/dL`事件终点不同。该结果不能与PhysioCGM直接做传感器增益相减。

## 所有已完成路线

|实验|数据/验证|结果|
|---|---|---|
|v2.1 静态/因果时序、四学习器、密集验证阈值|PhysioCGM 7人，严格未来时间|独立复算63组；静态有1次事件命中，时序主预算仍零命中，未达目标|
|v2.2 增加设备HR/呼吸率/HRV/质量摘要|同源7人，历史与边界扩大到65分钟|独立复算63组；静态主预算2次命中，但宏召回低于纯时间基线；时序主预算零命中，未达目标|
|SW1 新队列整人留出|11人，测试人完全不进入训练/验证|独立复算33组；穿戴+时间平均AUC0.535，AP0.0627；相对时间的AUC/AP配对区间跨零，证据不足|
|SW-P1 新队列个体化|11人，源行顺序留出|AP出现上述探索性正向改善；AUC/报警能力未稳定，不替代主事件目标|

PhysioCGM的60/65分钟历史让参考事件数从首轮31变为30；原始v1在同一决策机会重算后再比较，未通过缩小分母宣称进步。v2.2用了胸带设备摘要，不是只增加纯腕部特征。E4分钟HR在分箱结束时才视为可用；设备内部HRV时间支持仍缺独立确认。

## 数据、许可和复现

新队列来自 [Zenodo 15309060](https://doi.org/10.5281/zenodo.15309060)，11份文件已核对大小/MD5并登记SHA256；许可CC BY 4.0，作者出处为 [Mohamed等，PLOS ONE 2025](https://doi.org/10.1371/journal.pone.0325956)。本项目没有复制无明确许可的作者代码。原始个人记录留在git-ignored目录，公开的是自写代码、配置、逐人汇总和来源哈希。

```powershell
python scripts/download_data.py --dataset smartwatch_hypo
python scripts/run_improvement.py
python scripts/verify_improvement.py
python scripts/extract_device_summaries.py
python scripts/run_improvement.py --config improvement_v2_2.json
python scripts/verify_improvement.py --folder improvement_v2_2
python scripts/run_smartwatch_replication.py
python scripts/verify_smartwatch_replication.py
python scripts/run_smartwatch_replication.py --config smartwatch_personalized_v1.json
python scripts/verify_smartwatch_replication.py --folder smartwatch_personalized_v1
python scripts/export_improvement.py
```

新队列的统一下载CLI会检查CC BY 4.0许可、11份源文件数量、大小与MD5；入口和校验清单见 `docs/smartwatch_source_manifest.json`。

## 下一轮优先级

1. 保留当前AP改善，检查按人方向、早期校准量、概率质量及单类验证折；选择新协议比较正常时间、活动、个体基线与生活情境。
2. 统一下载CLI与报告测试已经补齐；继续保留失败受试者及单类折。
3. PhysioCGM优先核对CGM—胸带时间语义和心搏/伪影质量；现有摘要增强未解决主事件任务。
4. 对新的独立数据或新增可信原始时间戳进行方法冻结后的确认。未能确认来源时间时，明确降为点级分类研究，不计算医疗报警效果。

每两小时的当前聊天自动任务 `t1d` 已启用，持续接续并同步GitHub与实验日志。研究目标仍未完成，不能把有一个正向AP结果当作整项低血糖报警研究结束。
'''
    if 'CONTEXT_V1_1' in stages:
        report+='\n\n## 后续批次：情境信息与校准\n\n已完成132组独立复算。新增日记情境未支持稳定AP增益；校准降低原始Brier，但未稳定优于训练期正类概率基线。该批次边界范围不同，上轮0.1887不能与本轮均值直接比较。详见[本轮报告](CONTEXT_REPORT.zh-CN.md)。下一轮优先级转向原始心搏形态、伪影质量与源时钟证据。\n'
    (ROOT/'docs/IMPROVEMENT_REPORT.zh-CN.md').write_text(report,encoding='utf-8')
    print('Exported aggregate improvement ledger, report and card',run)


if __name__=='__main__':main()
