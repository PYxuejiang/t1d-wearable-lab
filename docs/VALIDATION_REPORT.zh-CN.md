# 两模块验证报告

运行标识：`t1d-26c297decb6a`；协议：`1.2-implementation-1`。阶段判定见 [验收总表](acceptance/STATUS.md)。

本轮完成了公开数据下载、适配、时间审计、固定模型、独立复算、敏感性分析和可视化。**工程/评价流程通过，腕部信息增益与低血糖报警研究目标未通过。** 这些结果支持后续算法研究，不支持把原型作为医疗报警器。

## 数据与纳排

BrisT1D-Open 全部 20 份设备 CSV 已校验，共 2,875,613 源记录、847,956 清理后 CGM 锚点。按通道处理相同/冲突时间戳，418 个冲突组显式排除。名义 CGM 间隔为 5 或 15 分钟。饮食/胰岛素是已记录事件，缺失记录不证明实际没有摄入或用药。记录到达时间不可得，离线因果输入不能证明实时服务延迟。

PhysioCGM 全部 10 份原始 ZIP 已通过官方大小和 MD5 检查，直接流式读取，未展开全部压缩包。7 人的腕部—胸带对齐通过训练期 HR 检查；3 人隔离。排除依据不使用血糖标签或测试成绩。

|源受试者|处理状态|参考锚点|全部通道可用锚点（划分前）|
|---|---|---:|---:|
|c1s01|extracted|5566|2498|
|c1s02|extracted|4839|3116|
|c1s03|extracted|4018|3077|
|c1s04|clock_quarantined|—|—|
|c1s05|extracted|4822|3318|
|c2s01|clock_quarantined|—|—|
|c2s02|extracted|4642|2697|
|c2s03|clock_quarantined|—|—|
|c2s04|extracted|6129|3655|
|c2s05|extracted|4202|3624|

E4 UTC 转为胸带壁钟的候选偏移只在前 60% 的独立 HR 信号上判定。CGM 与胸带朴素壁钟相同仍是**源数据假设**；±5 分钟标签敏感性只报告，不能用来选择最高血糖识别成绩的偏移。无法排除这一假设对信号任务失败的影响。`Low/High` 仅供阈值分类，未用于精确数值回归。

## 模块一：已有 CGM 时的协同价值

历史 60 分钟预测未来 30 分钟；目标为 ±2.5 分钟内真实参考，不以未来插值补输入。LOSO 测试人不进入训练/验证；个体未来验证按 60/20/20 分割并删除跨边界支持。固定 HGB 参数；简单基线在验证集选择；校准和报警阈值不读取测试标签。

LOSO 等权 MAE：简单基线 1.1710、CGM 1.0261、CGM+情境 1.0252、再加腕部信息 1.0290 mmol/L。CGM 相对简单基线改善 12.37%；腕部信息相对情境模型为 **−0.37%**，未达到预设 5% 目标。个体未来验证的腕部增益 0.23%，区间跨零，不能描述为稳定收益。

新发事件另外训练/评价。融合模型 LOSO 事件召回 **47.5%**，未匹配报警 **0.53 次/人日**，命中事件提前量中位数 **10 分钟**。有 1,842 个可评价参考事件、873 次命中；20 人宏平均与事件总数的微平均不同。提前量只条件于命中，不能掩盖漏检。未达到内部 80% 召回目标。

![模块一比较](figures/module1-comparison.png)

## 模块二：原始信号与传感器对照

过去 5 分钟非 CGM 信号做当前检测；PPG、PPG+ACC、再加 EDA/温度、ECG、全部通道共五组。各组在相同全通道有效训练/验证集合拟合，以控制训练样本差异。共同有效测试视角固定相同弃判位置；端到端视角保留各自缺失，事件分母包括整段没有输出的事件。

主要检测事件是源单位 `<70 mg/dL` 连续观察低值至少 15 分钟；任何非低值或长缺失中断。当前实现不以 15 分钟正常恢复合并事件，配置 `recovery_minutes` 为预留项，未参与本轮事件算法。M1 的新发预测要求此前 15 分钟正常。

7 人 LOSO 共 146 个参考事件，2,835.95 参考观察小时。下表为受试者等权召回/覆盖、汇总参考人日误报率；AP 为逐人平均精确率摘要。

|配置|事件召回|时间覆盖|未匹配报警/人日|AP|
|---|---:|---:|---:|---:|
|ppg|0.0%|75.8%|0.085|0.0426|
|wrist|0.0%|75.8%|0.000|0.0492|
|wrist_eda_temp|0.0%|75.7%|0.000|0.0411|
|ecg|0.0%|69.8%|0.000|0.0451|
|all|0.0%|65.0%|0.000|0.0367|

多数组合在验证约束下选出的阈值为 1.001，即**停止报警的失败工作点**；不能把零误报解释为可靠报警。PPG 的部分 LOSO 折有报警，但未匹配到事件。未来时间测试 31 个事件，同样零命中。该失败可能涉及弱特征、跨人差异、标签对齐假设和有效输入缺失，本轮不能确定单一原因；不据此证明非侵入检测在所有条件下不可行。

时间覆盖只累计参考连续段的相邻真实时长，要求区间两端都有有限输出。长缺失不计入观察小时；点覆盖另存，未把点数冒充时间。全部通道相对腕部两通道覆盖下降约 10.8 个百分点，没有支持追加传感器的稳定增益证据。

![模块二覆盖](figures/module2-coverage.png)

## 不确定性、信号质量和成本

以人做 2,000 次 bootstrap，报告事件召回、覆盖、AP、Brier 区间及通道差值。校准可靠性分箱只作描述；不通过测试集重新校准。只有 7 人，窗/事件数量不能增加独立人数。未做临床功效分析。

固定预测上补做完整率 0.9/0.95/1.0、确定性输出掉线 0/10/30%、参考标签 ±5 分钟压力测试；属于主结果后的工程敏感性分析，不是预先注册的确认性试验。零召回不会因这些分析自动转为合格。壁钟分层不是睡眠分期。逐人明细、分母和单类状态保存在 [验收目录](acceptance)。

PPG 与自写 ECG 检测器的速率一致性仅为算法间一致性，没有人工心搏真值；不能声称 ECG 检测已验证，PRV 也不等同 HRV。当前 SQI 只有样本完整率和非平直筛查，运动伪影仍可能漏过。后续优先做盲态人工抽样标注/有许可参考算法对照，再研究疾病识别。

![稳健性](figures/robustness.png)

固定机器的特征计算耗时见 [环境与基准](environment.json)，仅统计顺序特征计算，不含读取和训练，不能换算成手表电池续航。

## 传感器需求与后续推进边界

|信息|本轮角色|数据条件|当前结论|
|---|---|---|---|
|CGM|模块一输入；模块二参考|源时间、单位、质量和未来标签可判定|是主要预测信息；不声称无创替代|
|心率/活动汇总|模块一增量输入|向后匹配，最大年龄 10 分钟；缺失显式保留|本模型未观察稳定增益|
|原始 PPG / ACC|模块二腕部配置|64 / 32 Hz、可靠时钟、5 分钟完整率至少 90%|当前检测失败；先改善 SQI 和心搏提取|
|EDA / 温度|增量通道|4 Hz，同一观察时间配对|无稳定追加价值证据|
|胸带 ECG|对照通道/脉率参考候选|250 Hz、样本时钟检查；需要人工/参考算法核验|当前不支持为低血糖报警追加此通道|

下一轮应建立新的预注册协议和独立留出数据：①先核实 CGM—胸带时钟、峰值检测与 SQI；②按验证预算研究时间序列/个体校准与报警持续性；③增加外部队列或前瞻性采集，区分算法问题与数据可辨识性。不能在本轮已查看测试集上选出最好改动后仍称独立验证。T1D 的自身免疫背景可作研究动机，SPAID/PTM 与本队列没有配对，未进入模型，不能据此预测免疫活性或因果机制。

## 展示与复现

本地站点读取相同 `project_data.json`，提供结果卡、独立验收抽屉、真实历史回放和本地真实同步波形。个体轨迹只在本机生成并 git-ignored；公共仓库仅含汇总证据和卡片。所有卡片携带任务、范围、单位、效果状态和 `t1d-26c297decb6a`。部署到公网和个人设备迁移均不属于本轮必做范围。

数据来源与许可证见 [README](../README.md)；文件哈希见 [源清单](source_manifest.json)，可重现环境见 [固定依赖](../requirements-reproduce.txt)。没有外部独立队列验证、临床终点确认或干预获益证据。


## 2026-10-18：V5已完成，交互展示与每小时接续

V5_PPG_MORPH1已完成提取、训练、独立复算与导出，**不要重跑旧控制器或流水线**。42组测试、9个内层候选、6个选中验证工作点全部核对。三路使用同一腕部掩码和全部7人、30次事件；粗特征分数与V4精确复现。

主形态方案1/30命中，前15分钟0/30，17次未匹配报警/18次总报警，误报0.717985次/参考人日，覆盖72.8007%。旧粗特征对照3/30、前15分钟2/30。形态AP0.0770，对照0.0992；配对差−0.0222，按人探索性95%区间[−0.0814,0.0185]。**工程与评价通过，信息增益和原检测目标失败**。5次无输入、22次低于阈值、2次报警状态未触发；不能隐藏这些漏检。新增形态尚无专家搏动准确性验证，源物理时钟仍未解决。

下一阶段仅限PPG：先审计有参考心搏标注的公开基准与许可，冻结跨记录、活动分层的峰值/PPI/质量验证；先确认提取是否可靠，再决定是否回到低血糖模型。候选PPG-DaLiA/PPG-beats不是新疾病标签，也不是低血糖外部验证。无新证据不扩大固定特征参数网格、不按测试改报警阈值。旧80%召回/1次误报/80%覆盖目标保留；其属于内部目标，固定72.8%掩码无法过覆盖门槛。分层研究目标见GOAL_REVIEW，任何新门槛必须前瞻冻结，不能追认本轮成功。

用户要求接续间隔改为每1小时；原t1d自动任务已更新为ACTIVE，每小时推进算法和交互展示。首页改为原创三维概念手表与五步感知流程；复杂指标和历史证据保留在#research。动画是合成示意，不代表PPG血糖测量、已验证心律/呼吸异常或真实医疗通知。公开资产为自写模型、汇总验收和截图，患者数据仍仅本地。三分钟现场录屏尚未完成。

详细结果：[PPG形态报告](PPG_MORPHOLOGY_REPORT.zh-CN.md)。交互展示：[设计与验收](WATCH_EXPERIENCE.zh-CN.md)。


## 2026-10-19 / PPG_CAPTURE1 completed; no detector improvement

Frozen code/protocol32c7b1d pushed before scoring. Fixed V5 short-window peak rule versus original dual-moving-average adaptation ofElgendi2013; common causal0.5–5Hz filter,30s windows,27s cardiac-time cores. S1–S5development10records, S6–S15heldout19records (S6walking absent). Eachrecordfirst120s ECGreference selects shared0–0.6s lag; this is offline reference-assisted, not standalonewearable performance. FiveSQI candidates frozen before heldout; threshold0 selected, highergates faildevelopmentwalkingcoverage. No ECGinput to detector andno glucoseendpoint.

607windows and464metricgroups independently checked, including rawsourceRpeakwindows, calibratedlags, allSQIcandidates, one-to-one counts via dynamicprogramming, adjacentPPI and HR errors. Initialverifierexactfloatcomparison failed due5.55e-17 summation-orderdifference; tolerance corrected to1e-12, originalfailedlog retained, no method/prediction/selection changes. Do not rerun extraction; ignoredoutputs/ppg_capture_v1 complete.

HeldoutmacroF1 .4777299→.4758344, paired−.0018955 CI[−.0044216,.0007305]; no stablegain. HRMAE4.809→5.387bpm; matchedadjacentPPIcoverage30.31%→29.93%. The ~41msPPIerror is conditional, notfullreferenceaccuracy. Fixed200ms F1 .1568→.1475; unadjusted .1959→.1880.5/19heldoutrecords calibrate at upper0.6s bound, so F1 mixes detector errors with unresolvedrelative/filterdelay. Do not conclude wristPPGintrinsically48%accurate. Coretimecoverage88.0% is a different benchmark denominator, notPhysioCGM72.8% improvement. V5remains1/30failed. Fullreport docs/PPG_CAPTURE_REPORT.zh-CN.md, cardppgcap-aef624ada333; oldresearchpage linksadded, homepage remainsminimal.

Next onlyPPG: onfixeddevelopmentS1–S5 audit raw/filtered pulse timing and calibrated-lagboundary withknown syntheticdelay andpublishedE4timing. Freeze a newalignmentprotocol before further scoring. Existingheldout is nowseen; furthersamecohortchanges exploratory. No broadercoarsefeaturetuning or ECG/CGMdiseasefusion. Preserve allfailedmethods/SQIcoverage. Hourlyautomationactive; no activeanalysisjob expected after verification.


## 2026-10-19 PPG_TIMING_DEV1完成

开发集S1–S5共10记录211窗，复用现有峰值，不改疾病模型；执行前协议557ea1b。首120秒校准范围由0–0.6诊断为±1.5秒，固定4–26秒评分核心、尾段冻结偏移。静坐F1 .4112→.5871，步行 .3818→.4760；5人配对差+.1350，探索性95%区间[.0114,.2729]。这是对齐敏感性，不是检测器改善。8/10校准在旧范围外；2/5步行有近似等分的远处偏移，存在整搏混淆。分块偏移变化中位80/90ms；合成滤波峰移随脉宽变化，真实未滤波/滤波峰配对不是时钟真值。独立验证20个校准选择、20组尾段计数，同参考分母。公开仅群体汇总，逐记录在ignored outputs。

下一步仍仅PPG：开发集整搏混淆、峰/上升沿与不同校准段稳定性，先冻结对齐协议再同队列探索验证；不回到低血糖模型、不按留出成绩挑时移、不删除歧义记录。完整报告PPG_TIMING_DEV_REPORT.zh-CN.md。已完成输出勿重复长任务。


## 2026-10-19 PPG_STABILITY_DEV1完成

执行前协议/脚本9e118ce冻结。5名开发受试者10记录211窗，仅复用PPG峰缓存。0–60、60–120、0–120秒三校准方案固定用于相同尾段；未按尾段选方案。静坐F1 39.27/59.22/58.71%，步行39.37/49.18/47.60%；两一分钟校准偏移相差≤100ms分别2/5、4/5。按人尾段F1平均绝对差25.88个百分点，探索性95%区间[15.10,42.33]；是评分敏感性，不是算法增益。完整两分钟校准步行2/5有近似整搏周期竞争偏移，未触±1.5秒界不等于物理同步。评分时间覆盖静坐73.08%、步行70.73%，全部记录保留。

独立复核30次校准选择、30组尾段计数/PPI与群体汇总、按人区间通过；逐记录仅ignored outputs/ppg_stability_dev_v1，勿重复长任务。报告PPG_STABILITY_DEV_REPORT.zh-CN.md；成果卡ppgstable-255be8015c05。下一步仅开发集PPG峰/上升沿、校准平台和残差核查，先冻结协议；不再把靠近200ms的最大匹配数偏移视作唯一物理同步证据，不根据尾段挑规则。尚无新疾病事件、误报、及时性结果，V5及旧对照保持。


### PPG直接人工标注入口已取得（2026-10-19）

在稳定性诊断后进一步核查作者公开pyPPG标注包，已下载v1 PPG-BP_annot.zip 7.17MB并核对官方MD5；Zenodo记录CC-BY-4.0。结构审计确认219唯一信号条目、两套各219汇总标注、1000Hz、2.1–4.2秒；不是连续腕部波形，不能原样套现有30秒检测器。只读结构验收通过，未评分。详情docs/PPG_BP_ANNOT_AUDIT.zh-CN.md与acceptance/PPG_BP_ANNOT_SOURCE1.json；数据留data/ppg_bp_annot，不重复下载。下一步优先审计采集部位、标注预处理、时间/索引、空标签和标注者一致性，冻结短片段定位协议，再做PPG-DaLiA开发集峰/上升沿核查。不得拼接短片段伪造长记录，不把专家边界内定位当连续检出，不将此类信号成绩当疾病效果。
