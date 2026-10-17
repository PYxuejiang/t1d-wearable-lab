"""Publish capture-only aggregates and a clearly scoped share card."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main():
    record = json.loads((ROOT / 'docs/acceptance/ECG_CAPTURE_PILOT1.json').read_text())
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    run = 'ecg-' + digest[:12]
    names = ['existing_energy', 'wfdb_xqrs_default']
    summary = record['summary']
    labels = ['Existing energy', 'WFDB XQRS']
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), facecolor='#fffefa')
    for i, method in enumerate(names):
        rows = [r for r in record['record_summary'] if r['method'] == method]
        axes[0].plot([r['record'] for r in rows], [r['f1'] for r in rows], 'o-', label=labels[i])
        axes[1].plot([r['record'] for r in rows], [r['matched_timing_median_ms'] for r in rows], 'o-', label=labels[i])
    axes[0].set_ylim(.98, 1.001)
    axes[0].set_ylabel('Beat F1 (150 ms tolerance)')
    axes[0].set_title('Both methods pass this small capture pilot')
    axes[1].set_ylabel('Matched-beat median |timing error| (ms)')
    axes[1].set_title('Timing accuracy is separate from heart rate')
    for axis in axes:
        axis.set_xlabel('Fixed MIT-BIH record'); axis.legend(frameon=False)
    fig.text(.02, .01, run + ' | Four records, first ECG channel; no PPG / hypoglycemia / clinical alarm claim', fontsize=8)
    fig.tight_layout(rect=[0, .04, 1, 1])
    fig.savefig(ROOT / 'docs/figures/ecg-capture-pilot.png', dpi=170)
    plt.close(fig)
    table = '\n'.join(f"|{r['record']}|{'现有能量法' if r['method']==names[0] else 'XQRS'}|{r['sensitivity']:.2%}|{r['ppv']:.2%}|{r['f1']:.2%}|{r['window_hr_mae_bpm']:.3f}|{r['matched_timing_median_ms']:.1f}|" for r in record['record_summary'])
    text = f'''# ECG 心搏捕获：四记录先导验收

运行标识 `{run}`。**两种方法都通过本次捕获门槛；这不是低血糖检测通过。**

## 问题与冻结范围

检验现有能量峰值方法能否准确捕获带专家标注的心搏，并与默认XQRS对照。固定MIT-BIH v1.0.0的100、101、103、105记录、第一通道、全部完整五分钟非重叠窗口；没有按成绩选通道/片段或调参数。

共24个窗口、48组方法结果。每窗两端各2秒不评分，共118.4分钟可评分时间；每条末尾2,000样本（5.56秒）不足完整窗口未评分。裁边对专家与算法相同，未以质量或节律删除窗口。参考保留配置中的全部心搏类别，排除节律/伪影标记；没有只保留正常N心搏。

一对一匹配容差150ms，先匹配最早可行心搏；独立评分用最大二部匹配核对数量，再用二分搜索重构配对核对时序误差。门槛在运行前固定：每条记录敏感度及PPV均≥95%，24窗心率均可计算，平均心率绝对误差≤3bpm。此门槛为项目内部先导要求，不是临床标准。

## 结果与决策

记录等权平均F1：现有方法 **{summary[names[0]]['f1']:.4%}**，XQRS **{summary[names[1]]['f1']:.4%}**，增加约 **{(summary[names[1]]['f1']-summary[names[0]]['f1'])*100:.3f}个百分点**。平均心率误差分别 **{summary[names[0]]['window_hr_mae_bpm']:.4f}** 与 **{summary[names[1]]['window_hr_mae_bpm']:.4f} bpm**，没有支持心率提取误差获得实质改善。

|记录|方法|心搏敏感度|心搏PPV|心搏F1|窗心率MAE/bpm|已匹配心搏绝对时序误差中位数/ms|
|---|---|---:|---:|---:|---:|---:|
{table}

![固定记录对照](figures/ecg-capture-pilot.png)

能量包络峰并非精确R峰位置，因此同时公布时序误差。更小的已匹配心搏定位误差不能直接推断HRV更准确：RR/RMSSD、异常心搏过滤和漏搏后的连续性尚需单独验收。心率取60/中位RR，专家与候选均保留0.3–2秒RR且至少5个间隔；这个稳健定义可能掩盖零散错搏，不能替代心搏敏感度和PPV。

**本次不替换PhysioCGM原始特征。** 四条方便抽样的参考ECG成绩较高，只支持捕获流程在这批记录上可用。不能把低血糖失败简单归咎于粗峰值方法，也不能据此认定目标胸带、运动伪影或腕部PPG没有问题。下一步先扩展更完整ECG/噪声验证，再以冻结方案在PhysioCGM比较捕获一致性、覆盖与质量；没有专家标注的目标波形只能做一致性审计，不能自称准确率。

## 时间、许可与复现边界

- 算法只接收当前五分钟窗口，不读取窗结束后的样本。XQRS的窗内处理包含双向滤波/学习，**不是逐心搏零延迟实时算法**。该先导的输出时刻是窗口末端。
- [MIT-BIH官方数据说明](https://physionet.org/content/mitdb/1.0.0/)：Moody与Mark，2005，DOI[10.13026/C2F305](https://doi.org/10.13026/C2F305)，ODC Attribution v1.0；另引原始研究Moody & Mark, 2001, DOI[10.1109/51.932724](https://doi.org/10.1109/51.932724)。本次从官方文档公开S3镜像下载，12文件均以主站SHA256表校验，来源哈希见验收记录。
- [WFDB Python](https://github.com/MIT-LCP/wfdb-python)，MIT许可，固定4.3.1；[XQRS说明](https://wfdb.readthedocs.io/en/latest/processing.html#wfdb.processing.xqrs_detect)。只调用安装包，未复制其实现。四记录没有足够证据作人群泛化或临床推断。
- 没有血糖标签、糖尿病人群有效性、PPG验证、事件报警、传感器替代或疾病恶化预警结论。原始记录和逐搏匹配留在Git忽略目录；发布配置、代码、来源校验与汇总结果。

```powershell
python -m pip install -e ".[signals,reports]"
python scripts/download_ecg_pilot.py
python scripts/run_ecg_pilot.py
python scripts/verify_ecg_pilot.py
python scripts/export_ecg_pilot.py
```

本机WFDB在`outputs/signal_runtime`隔离环境；运行命令使用该环境Python。运行器拒绝覆盖已存在实验，完成记录为`outputs/ecg_capture_pilot_v1/completed.json`；无需重新评分。独立复算记录见[ECG_CAPTURE_PILOT1.json](acceptance/ECG_CAPTURE_PILOT1.json)。
'''
    (ROOT / 'docs/ECG_CAPTURE_REPORT.zh-CN.md').write_text(text, encoding='utf-8')
    from PIL import Image, ImageDraw, ImageFont
    font = next(p for p in [Path('C:/Windows/Fonts/msyh.ttc'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())
    image = Image.new('RGB', (1800, 1200), '#f6f5ef'); draw = ImageDraw.Draw(image)
    lines = ['T1D / SIGNAL CAPTURE PILOT', '先验收信号捕获，再研究检测能力', 'MIT-BIH固定4条ECG；24窗；48组独立复算',
             f"心搏F1：现有 {summary[names[0]]['f1']:.2%} → XQRS {summary[names[1]]['f1']:.2%}",
             '两方法均通过先导捕获门槛；心率误差均很小', '四记录先导；尚未替换目标数据的心搏提取',
             '不代表PPG、低血糖检测或临床报警有效', run, 'https://github.com/PYxuejiang/t1d-wearable-lab']
    for i, line in enumerate(lines):
        draw.text((100, 110+i*105), line, font=ImageFont.truetype(str(font), 52 if i == 1 else 35), fill='#276c61' if i == 3 else '#1d373b')
    card = ROOT / 'showcase/public/cards/ecg-capture.png'; image.save(card)
    (ROOT / 'showcase/public/cards/ecg-manifest.json').write_text(json.dumps({'run_id': run,
        'acceptance_sha256': digest, 'png_sha256': hashlib.sha256(card.read_bytes()).hexdigest()}, indent=2), encoding='utf-8')
    print('Exported ECG capture pilot', run)


if __name__ == '__main__':
    main()
