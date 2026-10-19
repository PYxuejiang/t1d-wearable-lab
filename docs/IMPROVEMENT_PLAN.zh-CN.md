# 检测改进计划 v2

用户于 2026-10-16 要求继续寻找多种方法，取得可复核的正向效果；每两小时接续的自动任务已启用（ID `t1d`）。此文档和实验日志是接续入口，不应重复已完成的下载与波形提取。

## 首轮状态与需要区分的问题

- 公开仓库：https://github.com/PYxuejiang/t1d-wearable-lab 。v1 负结果保留，不能覆盖其验收证据。
- BrisT1D 20 人已下载审计；PhysioCGM 10 份 ZIP 已校验，7 人通过腕部—胸带时钟检查，3 人隔离。CGM/胸带壁钟仍为源假设。
- 首版 HGB + 静态五分钟特征未实现可用检测。主误报预算下经常选出停止报警阈值。应先判断是信号质量/对齐、分类无信息、校准/阈值搜索还是报警策略的问题，不能立即归咎于传感器无效。
- v1 测试已经看过；同队列新方法是探索性 v2。模型与阈值继续在训练/验证中选择，不能将已看的队列重新命名为独立验证。

## v2.1：先冻结再运行

主任务仍为非 CGM 输入的当前 `<70 mg/dL` 状态检测。主观察规则、事件持续 15 分钟、缺失间隔、观察人日及 80%/1次/80% 内部目标沿用 v1。重点是判断是否存在正向且可复核的效果，不把点级 AUC 改善包装成达到临床报警目标。

1. 主验证：个体内前 60% 训练、20% 验证、末 20% 测试，完整输入/确认范围删除边界。先审计每段阳性和事件数；无训练阳性不能训练正常监督模型，必须登记而非移除测试事件。
2. 特征候选：静态腕部；加入 15/30/60 分钟因果历史、差值、局部均值/波动；再加入壁钟 sin/cos。增加纯壁钟基线，避免把生活时间模式当作传感器专有收益。只使用既有特征中可靠/可用的通道，CGM 不作模块二输入。
3. 学习器候选：正则逻辑回归、随机森林、ExtraTrees、限制复杂度 HGB。固定种子、候选数及参数；训练集拟合插补、缩放、重采样。验证 AP 用于模型选择，正类率一起报告；阈值另用验证事件召回和误报预算选择。类别权重与有监督的个体化不等同于没有标签的跨人模型。
4. 报警候选：密集验证分数量化阈值，修正首轮只有少量阈值的搜索限制；输出平滑仅用过去分数。主预算 1 次/人日，2/4 次是另外标注的探索工作点，不替代主目标。保留停止报警阈值作为诚实失败退路，不能只删除它强制报出非零召回。
5. 先锁定每个受试者/方法的选择再生成测试预测，保存选择清单、因果特征时间、逐点预测和独立评价。比较统一测试参考集合下 v1 与 v2 的事件宏召回、AP、误报、时间覆盖、点级特异度及按人区间。分类优于时间基线和能运行的事件报警是不同层级成果。
6. 不按测试成绩再改 v2.1。下一轮新方法建立新 ID，保留全部候选和失败。模型改善有限时先解决信号质量和峰值检测，不继续无界扩大搜索。

## 后续方法，分阶段执行

|方向|要解决的问题|验收要求|
|---|---|---|
|训练期传感器时钟复核、原始参考时间语义|排除 CGM—胸带系统偏移或漂移|不以疾病识别成绩选偏移；无可靠证据保留假设|
|原始 ECG/PPG 心搏质量、呼吸率、可靠设备摘要|静态粗特征弱、运动伪影|参考算法许可、抽样心搏核对、覆盖及误差；不能用算法输出自证真值|
|个体化与有限早期校准|自主神经反应个体差异|披露需早期 CGM 标签；后期测试严格隔离|
|时间序列/形态模型|五分钟统计丢失形态和变化|先验证因果窗口与足够事件；不以随机重叠窗拆分虚增结果|
|独立公开队列|现有测试被查看，缺乏外部验证|先审计许可、标签、采样和输入可比性；方法冻结后才看外部测试|

## 已查原始研究与项目线索

- [PhysioCGM 原文](https://www.nature.com/articles/s41597-025-06090-6) / [作者代码](https://github.com/PSI-TAMU/PhysioCGM)：核查作者个体化设定、时序处理和数据字段。未发现许可前不复制作者实现。
- [Mohamed 等，PLOS ONE 2025](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0325956)：使用个体化、心脏/活动/时间信息，提供[公开数据](https://zenodo.org/records/15309060)和[代码](https://github.com/YMM-0/smartwatch_hypo_detection)。其按日/夜留出以及终点定义与本项目不同，论文分数不能直接作为本项目目标或已复现成绩。
- [2026 预印本：低成本 HR/GSR 检测](https://arxiv.org/abs/2602.10407)：候选融合与序列方案线索，尚未在本项目验证；预印本不等于已证实有效。

每次接续先读 `docs/EXPERIMENT_LOG.md`、Git 状态和实际进程。只提交自写代码、汇总指标、参数和源哈希；患者记录、逐点轨迹、波形和凭据留在 git-ignored 目录。


## 2026-10-17 接续状态

情境与分数校准批次已完成132组独立复算：见 `docs/CONTEXT_REPORT.zh-CN.md`。新增日记情境未支持稳定AP增益；校准虽降低原始Brier，未稳定优于训练期正类先验。120行边界旧尝试已登记隔离，替代版本150行。不要重做这一批次；下一优先级转向原始心搏形态、伪影质量与源时钟语义，先冻结可检验的信号子任务。既有源行顺序AP改善仍单独保留，不覆盖也不夸大。

四记录ECG捕获先导也已完成：`docs/ECG_CAPTURE_REPORT.zh-CN.md`，48组独立复算。能量法/XQRS F1约99.66%/99.77%，两者通过；心率误差均很小。没有更换PhysioCGM检测器，也没有低血糖效能改善结论。下一次不要重跑本先导；先冻结更广记录/噪声覆盖和RR时序质量协议，再审计PhysioCGM目标波形、数据覆盖和CGM—胸带原始时钟证据。目标数据无专家心搏标注时只报告一致性，不把算法互相比对称为准确率。临床事件目标仍未达标。

## V3：用户要求仔细改进方法与参数

`V3_MECHANISM1`已经完成，**不要重跑**。协议六条路线、10种有限超参数、训练内嵌套时间调参、个人/共同验证选报警策略、两预算两视图，336组测试与63个选中验证配置独立复算。源特征沿用v2.1，没重新提取或修改旧信号。

新增个人活动残差、多人的共享生理模型、持续2点确认/EMA/30分钟提醒及胸带后备，与原始精简模型、时间模型、缺失模式控制分别比较。覆盖72.8%→82.8%，按人差值10.04个百分点，探索性区间[2.54,21.46]个百分点；但预设主方案0/30命中。次要2次预算2/30命中、宏召回17.1%、误报1.858/参考人日，不能替代原目标。全部30次事件保留。详见`docs/MECHANISM_REPORT.zh-CN.md`。

优先级据新诊断调整：3次无输入、26次分数低于阈值、1次未触发，单改冷却无法解决主体失败。唯一事件前30分钟内的报警仍计当前检测误报，不作为擅自改任务或偏移标签的依据。**下一轮先核对作者加工版本/原始时钟的配对时间证据，验证CGM—胸带和腕部的源语义；不按高识别分数选时移。** 再制定真实RR/形态质量及参考标签对应研究。没有对齐与信息量的新证据时，不继续无界堆超参数。保留本轮覆盖改善与所有负结果，主任务仍未达标。

## 最新：2026-10-18来源审计与V4完成

`SOURCE_TIME1`与`V4_LATE_FUSION1`已完成，**不要重复下载加工探针或重训V4**。34,218个源参考标签一致；10人各1个固定加工片段对应原始CGM，3个非恒定腕部序列唯一匹配到UTC−5。其余7个首片段不具备匹配条件。作者E4使用主机localtime；CGM/胸带物理时钟仍未独立校准，未修改任何偏移或纳入名单。

V4新增ECG/PPG/EDA专家与后期融合、点/低值片段权重、3种有限学习器；保持过去训练/验证选参和所有30次测试事件。392组独立核对、30个内层候选、28个选中验证工作点，融合层独立重拟合误差约2.4e-15。后期融合AP0.0755→0.0969，按人配对差+0.0213，探索性区间[0.0041,0.0437]；相对缺失+时间及早期融合仍未支持稳定AP优势。预设主方案0/30、误报0.127/参考人日，事件验收失败。

PPG/点权重预设对照3/30，宏召回6.94%（总体10%），误报0.718/参考人日，覆盖72.8%；仅2人有命中，其他5人仍失败。它是值得研究的线索，不能事后替换主方案。已冻结分数的共同腕部配对另作事后描述，全部标记，未更改阈值。

下一步优先冻结**原始PPG短窗形态、可靠RR/质量及活动分层**的新增信息协议，先做信号子任务与覆盖审计，再训练；别再向已有粗特征无限堆模型。保持所有7人和无输入事件；未经专家参考的算法间一致性不等于准确率。用户2026-10-18最新要求仅推进PPG形态/间期/质量，本阶段不再并行模块一算法。更新报告见`docs/LATE_FUSION_REPORT.zh-CN.md`。当时每两小时接续（现已改每小时，见末尾），三分钟现场录屏仍待完成。


## 当前唯一算法方向：V5_PPG_MORPH1

按用户最新限制，仅推进原始PPG短窗形态、脉搏间期和质量。已冻结configs/ppg_morphology_v5.json，现已完成（见末尾）。先完成新增信号特征、同掩码粗特征/质量时间/形态三路比较；全部选参和报警工作点先在训练/验证冻结。保留旧80/1/80目标与失败证据。现掩码覆盖72.8%是固定设计约束，新增特征按信息增益单独评价。目标合理性、论文/产品参照及未来分层验收见[GOAL_REVIEW](GOAL_REVIEW.zh-CN.md)。新数值提案不追认本轮成功。后续仍在PPG方向，未获新指令前不切换CGM、ECG/EDA融合或夜间专属终点。


## 2026-10-18：V5已完成，交互展示与每小时接续

V5_PPG_MORPH1已完成提取、训练、独立复算与导出，**不要重跑旧控制器或流水线**。42组测试、9个内层候选、6个选中验证工作点全部核对。三路使用同一腕部掩码和全部7人、30次事件；粗特征分数与V4精确复现。

主形态方案1/30命中，前15分钟0/30，17次未匹配报警/18次总报警，误报0.717985次/参考人日，覆盖72.8007%。旧粗特征对照3/30、前15分钟2/30。形态AP0.0770，对照0.0992；配对差−0.0222，按人探索性95%区间[−0.0814,0.0185]。**工程与评价通过，信息增益和原检测目标失败**。5次无输入、22次低于阈值、2次报警状态未触发；不能隐藏这些漏检。新增形态尚无专家搏动准确性验证，源物理时钟仍未解决。

下一阶段仅限PPG：先审计有参考心搏标注的公开基准与许可，冻结跨记录、活动分层的峰值/PPI/质量验证；先确认提取是否可靠，再决定是否回到低血糖模型。候选PPG-DaLiA/PPG-beats不是新疾病标签，也不是低血糖外部验证。无新证据不扩大固定特征参数网格、不按测试改报警阈值。旧80%召回/1次误报/80%覆盖目标保留；其属于内部目标，固定72.8%掩码无法过覆盖门槛。分层研究目标见GOAL_REVIEW，任何新门槛必须前瞻冻结，不能追认本轮成功。

用户要求接续间隔改为每1小时；原t1d自动任务已更新为ACTIVE，每小时推进算法和交互展示。首页改为原创三维概念手表与五步感知流程；复杂指标和历史证据保留在#research。动画是合成示意，不代表PPG血糖测量、已验证心律/呼吸异常或真实医疗通知。公开资产为自写模型、汇总验收和截图，患者数据仍仅本地。三分钟现场录屏尚未完成。


## 2026-10-19 / PPG_DALIA_AUDIT1 completed

No active PPG jobs; V5 remains complete. Downloaded only fixed sitting/walking MAT files from Zenodo12793711; published MD5+size verified, localSHA256 recorded. Sitting15records/2.5403h/9,263ECG R peaks; walking14records/2.6087h/15,458peaks, S6 absent in source.29records, no detector scoring. Integer increasingRpeaks andfinitePPG do not establish signalaccuracy. HRsummaryoffsetunknown; bothzero/onebasedboundsvalid, indexing andpulse/filterdelay mustbe explicitlyhandledbefore scoring. MATLABconverter preservesfirstactivityepisode, notalltime. UCI/ZenodoCCBY wording differsolderuniversityscientificnoncommercialtext; dataremainlocal, no commercialredistributionclaim. PPG-beatsalignmentGPL distinctfromdocumentationlicense, no copiedcode. Source report docs/PPG_DALIA_AUDIT.zh-CN.md and aggregate acceptance/PPG_DALIA_AUDIT1.json. Next: freeze beat-matching/lag protocol andindependentverifier onfixeddevelopmentS1–S5, evaluateheldoutS6–S15 onlyafterfreeze; no glucoseendpoint. FullV5andwatchcodecommitd79ab38CIalreadygreen. Hourlyautomationactive. No repeat downloadsneeded; audit script validatescachedfiles.


## 2026-10-19 / PPG_CAPTURE1 completed; no detector improvement

Frozen code/protocol32c7b1d pushed before scoring. Fixed V5 short-window peak rule versus original dual-moving-average adaptation ofElgendi2013; common causal0.5–5Hz filter,30s windows,27s cardiac-time cores. S1–S5development10records, S6–S15heldout19records (S6walking absent). Eachrecordfirst120s ECGreference selects shared0–0.6s lag; this is offline reference-assisted, not standalonewearable performance. FiveSQI candidates frozen before heldout; threshold0 selected, highergates faildevelopmentwalkingcoverage. No ECGinput to detector andno glucoseendpoint.

607windows and464metricgroups independently checked, including rawsourceRpeakwindows, calibratedlags, allSQIcandidates, one-to-one counts via dynamicprogramming, adjacentPPI and HR errors. Initialverifierexactfloatcomparison failed due5.55e-17 summation-orderdifference; tolerance corrected to1e-12, originalfailedlog retained, no method/prediction/selection changes. Do not rerun extraction; ignoredoutputs/ppg_capture_v1 complete.

HeldoutmacroF1 .4777299→.4758344, paired−.0018955 CI[−.0044216,.0007305]; no stablegain. HRMAE4.809→5.387bpm; matchedadjacentPPIcoverage30.31%→29.93%. The ~41msPPIerror is conditional, notfullreferenceaccuracy. Fixed200ms F1 .1568→.1475; unadjusted .1959→.1880.5/19heldoutrecords calibrate at upper0.6s bound, so F1 mixes detector errors with unresolvedrelative/filterdelay. Do not conclude wristPPGintrinsically48%accurate. Coretimecoverage88.0% is a different benchmark denominator, notPhysioCGM72.8% improvement. V5remains1/30failed. Fullreport docs/PPG_CAPTURE_REPORT.zh-CN.md, cardppgcap-aef624ada333; oldresearchpage linksadded, homepage remainsminimal.

Next onlyPPG: onfixeddevelopmentS1–S5 audit raw/filtered pulse timing and calibrated-lagboundary withknown syntheticdelay andpublishedE4timing. Freeze a newalignmentprotocol before further scoring. Existingheldout is nowseen; furthersamecohortchanges exploratory. No broadercoarsefeaturetuning or ECG/CGMdiseasefusion. Preserve allfailedmethods/SQIcoverage. Hourlyautomationactive; no activeanalysisjob expected after verification.


## 2026-10-19 PPG_TIMING_DEV1完成

开发集S1–S5共10记录211窗，复用现有峰值，不改疾病模型；执行前协议557ea1b。首120秒校准范围由0–0.6诊断为±1.5秒，固定4–26秒评分核心、尾段冻结偏移。静坐F1 .4112→.5871，步行 .3818→.4760；5人配对差+.1350，探索性95%区间[.0114,.2729]。这是对齐敏感性，不是检测器改善。8/10校准在旧范围外；2/5步行有近似等分的远处偏移，存在整搏混淆。分块偏移变化中位80/90ms；合成滤波峰移随脉宽变化，真实未滤波/滤波峰配对不是时钟真值。独立验证20个校准选择、20组尾段计数，同参考分母。公开仅群体汇总，逐记录在ignored outputs。

下一步仍仅PPG：开发集整搏混淆、峰/上升沿与不同校准段稳定性，先冻结对齐协议再同队列探索验证；不回到低血糖模型、不按留出成绩挑时移、不删除歧义记录。完整报告PPG_TIMING_DEV_REPORT.zh-CN.md。已完成输出勿重复长任务。
