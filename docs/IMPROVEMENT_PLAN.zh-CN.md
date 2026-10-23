# 检测改进计划 v2

## 2026-10-23 PPG预训练与独立抗体：已执行更新

按用户确认方向新增真实Pulse-PPG编码器、T1D时序Transformer/LoRA对照、GSE45515独立抗体基线，并将有来源与局限的研究摘要接入原Harness检索；不融合不同患者的蛋白与传感器记录。

FIT2：4人训练14039窗、1人验证3719窗；18候选独立复核差0。修正299/301秒时钟抖动后，参考决策点覆盖39.55%→80.12%。验证AP：线性0.0955、全量0.0931、LoRA0.0781、病例比例0.0683。LoRA尚未超过简单头，参数不称全局最优；测试和事件报警未评估。FIT1全部保留。

抗体149张芯片按104保守命名组：AUC0.882/AP0.872，但患者身份、总说明标签冲突、pNA条目AUC0.735的混杂尚未解决；不能作个人风险或低血糖增益。BIG IDEAs16个背景ID与目录相符，只有Gender/HbA1c，没有逐人年龄；波形时钟/背景取得时间未验收，暂不准入训练。

完整文档：https://github.com/PYxuejiang/t1d-wearable-lab/blob/main/docs/MULTIMODAL_BRANCHES.zh-CN.md 。真实PPG表示、两轮全部候选和复核存本地outputs，不重复长任务。下一步训练人员内分组验证与背景数据审计；不扩大单个验证人参数搜索，不自动用Agent输出当标签。91项Python、19项Agent和生产构建通过，个人数据和权重不公开，定时仍PAUSED。


## 最新接续：2026-10-23 Transformer/LoRA + Harness 机制知识

用户已将范围扩展为可穿戴/用户背景微调与机制知识，明确保留新增 Agent Harness，排除旧质谱路线；确认没有个人蛋白配对数据。以 [当前实施及验收手册](TRANSFORMER_LORA.zh-CN.md) 为新增分支入口，旧“只推进 PPG”的限制不应覆盖此次明确新指令。原 PPG 审计与所有失败证据保留。

本次已同步远端 Harness 基线 ae760e0，实现时序 Transformer、Q/V LoRA、独立背景 token、离线快照桥接、真实队列预训练/微调入口和 SPAID/STING 证据包。合成工程验收通过：1281/21159参数可训练、冻结权重不变、适配器保存恢复输出差0；78 Python测试、18 Agent测试及前端构建通过。真实队列疾病效果尚未评估，QLoRA未实现，蛋白不作为患者特征。详见验收 LORA_ENGINEERING1。

下一步先冻结真实数据窗口/来源/标签/背景可获得时间与人员分组，再接入已审计 PPG 任务。任何实际缺失背景保留缺失；不将 Harness 日报规则当疾病标签，不训练于测试人，不混入CGM输入改变PPG-only终点。无配对蛋白不阻止信号模型研究；GSE45515可做独立抗体分支，但不能按疾病名拼接不同患者。预注册冻结头/全量微调/LoRA及有无背景的对照后再评分，不对当前已见测试集反复选阈值。

`outputs/wearable_lora_smoke_v1` 为已完成合成验收，勿当真实训练或重复报告为新增益。Agent Harness 本体、加密存储、现有三工具与日报回退保持。原定时任务磁盘状态为 PAUSED，本轮未擅自恢复；后续运行优先读本段新范围。

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


## 2026-10-19 PPG_STABILITY_DEV1完成

执行前协议/脚本9e118ce冻结。5名开发受试者10记录211窗，仅复用PPG峰缓存。0–60、60–120、0–120秒三校准方案固定用于相同尾段；未按尾段选方案。静坐F1 39.27/59.22/58.71%，步行39.37/49.18/47.60%；两一分钟校准偏移相差≤100ms分别2/5、4/5。按人尾段F1平均绝对差25.88个百分点，探索性95%区间[15.10,42.33]；是评分敏感性，不是算法增益。完整两分钟校准步行2/5有近似整搏周期竞争偏移，未触±1.5秒界不等于物理同步。评分时间覆盖静坐73.08%、步行70.73%，全部记录保留。

独立复核30次校准选择、30组尾段计数/PPI与群体汇总、按人区间通过；逐记录仅ignored outputs/ppg_stability_dev_v1，勿重复长任务。报告PPG_STABILITY_DEV_REPORT.zh-CN.md；成果卡ppgstable-255be8015c05。下一步仅开发集PPG峰/上升沿、校准平台和残差核查，先冻结协议；不再把靠近200ms的最大匹配数偏移视作唯一物理同步证据，不根据尾段挑规则。尚无新疾病事件、误报、及时性结果，V5及旧对照保持。


### PPG直接人工标注入口已取得（2026-10-19）

在稳定性诊断后进一步核查作者公开pyPPG标注包，已下载v1 PPG-BP_annot.zip 7.17MB并核对官方MD5；Zenodo记录CC-BY-4.0。结构审计确认219唯一信号条目、两套各219汇总标注、1000Hz、2.1–4.2秒；不是连续腕部波形，不能原样套现有30秒检测器。只读结构验收通过，未评分。详情docs/PPG_BP_ANNOT_AUDIT.zh-CN.md与acceptance/PPG_BP_ANNOT_SOURCE1.json；数据留data/ppg_bp_annot，不重复下载。下一步优先审计采集部位、标注预处理、时间/索引、空标签和标注者一致性，冻结短片段定位协议，再做PPG-DaLiA开发集峰/上升沿核查。不得拼接短片段伪造长记录，不把专家边界内定位当连续检出，不将此类信号成绩当疾病效果。


## 2026-10-19 PPG_LABEL_AUDIT1完成

预先冻结a9ea490，219条两套标注1752字段独立复核；汇总与merged MAT完全一致。严格单pk解析仅34/219配对，原因主要为邻搏多峰，不能称其余全部缺标。事后数量诊断：自己的os内恰一pk，MG219/219、PC218/219；PC1条os/u数量异常，保留不删。on/off/u均218配对，MAE3.208/3.472/1.119ms，仅标签差不是算法误差。原论文说明高质量指端单搏、12Hz人工标注滤波、>10ms分歧讨论；最终两套差异不应说成未经协商的独立标注可靠性。作者代码以round(t*fs)索引且使用专家边界，不能把其条件定位当连续检出。包内少数峰备注提示不确定性，未据此删记录。

公开docs/PPG_LABEL_AUDIT_REPORT.zh-CN.md、acceptance/PPG_LABEL_AUDIT1.json、成果卡ppglabel-168ed26d5dcf；本地outputs/ppg_label_audit_v1完整，勿重跑主审计。后续先冻结专家边界内单搏条件定位协议（目标峰/上升沿，两套标签和全部219覆盖），再回PPG-DaLiA开发集；不以当前标签MAE宣称新算法、腕部或低血糖效果。事件召回、误报、及时性和疾病PPV均无新结果。网站仍GitHub Pages自动发布。


## 2026-10-19 PPG_FIDUCIAL1完成

执行前05388c7冻结；219条指端精选单搏按名称哈希分70开发/149评价。MG专家边界作为明确输入，不输入参考pk/u；开发MG两类MAE选择offline12。评价MG峰MAE：raw12.178、causal5 43.979、offline12 7.741ms；上升沿24.319、63.984、2.791ms。PC分别12.735/42.911/8.937与24.290/63.631/3.035ms。MG参考149/149、PC148/149；全部保留、输出率100%，不是连续覆盖。MG峰≤50ms由raw98.66%降至97.32%，不可只报均值。

相对未补偿causal5的MG配对平均MAE差−48.716ms，按条目探索性95%区间[−55.945,−43.460]。这混合频段、相位、短片段滤波初始化影响；causal5上升沿偏差+63.984ms，不能说全部是检测器改善。双向用未来样本、专家边界、指端精选单搏及已见标注资源，均限制推论。未产生新的腕部连续检出、PPI、SQI拒绝或疾病报警效能。

独立MAT解析/极值/导数复算657组预测、438参考映射、24指标组、6区间和开发选择通过；3个合成控制通过，共享SciPy滤波内核已披露。主结果在outputs/ppg_fiducial_v1，勿重跑。公开PPG_FIDUCIAL_REPORT.zh-CN.md、acceptance/PPG_FIDUCIAL1.json与定位成果卡，只含群体汇总；研究页更新，首页不堆数据。V5及全部旧失败不变。

下一步先冻结5/12Hz与因果/双向分解对照，延迟修正仅开发估计，评价只作已见资源探索；关注尾部，随后回PPG-DaLiA固定开发人群核查独立找搏和整搏歧义。不要将专家边界定位成功追认为腕部或低血糖达标，不根据已见评价扩大搜索。


## 2026-10-19 PPG_FILTER1完成

执行前26a033b冻结；前次因自动审批额度未能执行，本次审批恢复后首次计算。固定219条、70开发/149评价，7路全公开、不选胜者。两路因果pk/u全局偏差只取开发MG中位数；全部校正结果计分、不裁剪。MG评价causal5的u MAE63.984→2.107ms，说明很大部分为固定定位偏移；常数校正不改变PPI，不能称找搏能力改善。

双向12Hz相对5Hz的峰/u平均MAE差−3.767ms，探索性95%按条目区间[−4.631,−2.873]。因果两路校正后12Hz反而平均高1.043ms [0.508,1.609]，不支持直接将所有链路改12Hz；峰差区间跨零。12Hz校正后1/149出界保留；MG参考149/149、PC148/149，输出149/149不等于时间覆盖。滤波双向改变幅频及边缘状态，非纯相位消融。旧三路完全复现，原低血糖失败与指标不变。

独立MAT与极值重算1533组预测、4开发常数、56指标组、30区间通过；两个合成控制通过。报告PPG_FILTER_REPORT.zh-CN.md、群体acceptance/PPG_FILTER1.json与成果卡；本地outputs/ppg_filter_v1完成勿重跑。公开没有条目身份/坐标/个体预测。下一阶段回到PPG-DaLiA固定开发受试者，先冻结无人工边界的PPG峰/上升沿配对和整搏歧义诊断，不能把指端固定偏移直接移到腕部；不继续扩张指端参数网格、不切回疾病模型。


## 2026-10-19 PPG_UPSTROKE_DEV1完成

运行前c835357冻结。原5开发人、静坐/步行10记录211窗，复用7954峰，仅从PPG独立定位上升沿；不输入专家边界或指端固定偏移。243个非严格谷/u/峰次序候选保留。三校准方案全公开；首120秒静坐F1 58.71→70.16%、PPI覆盖46.00→60.49%，步行F1 47.60→43.76%、PPI覆盖27.54→25.02%。按人两活动平均，F1差+3.81pp [−2.18,10.21]、PPI覆盖+5.98pp [−1.65,14.32]，均跨零；不能说稳定总体改善。条件PPI MAE静坐35.94→25.65ms，步行44.53→48.35ms。

固定核心时间覆盖静坐73.08%、步行70.73%；上升沿首120秒静坐1/5校准触边、步行1/5整周期歧义。两个一分钟偏移稳定≤100ms记录静坐峰2/5、u3/5；步行峰4/5、u2/5。ECG仅参考辅助匹配，非物理同步或上升沿真值。候选数量固定、窗口含等待，不等于连续在线检测或新疾病结果。

独立MAT复算211窗7954定位、60次校准、60组尾段计数/PPI及2个按人区间通过；旧峰基线精确复现、所有参考分母一致。本地outputs/ppg_upstroke_dev_v1完成勿重跑。公开报告PPG_UPSTROKE_DEV_REPORT.zh-CN.md、acceptance/PPG_UPSTROKE_DEV1.json及成果卡仅聚合；更新研究页，首页不堆数据。V1–V5失败和临床指标不变。

下一步先冻结活动分层的候选形态/质量诊断，核查步行非严格次序、位移和漏/多搏来源；不按尾段删记录或扩大粗特征参数搜索。若尝试质量拒绝，同时报告全部参考分母、保留时间及被拒部分，不以拒绝换取虚高精度。


## 2026-10-19 PPG_QUALITY_DEV1完成

执行前2c1b48c冻结，复用PPG_UPSTROKE_DEV1全部缓存与固定偏移，不重跑检测。5开发人10记录211窗7954候选；尾段固定核心171窗5119候选。固定三个错误风险分数全部报告：非严格次序AUC静坐0.5153/步行0.5072；校准段位移偏差0.7204/0.5085；1−旧SQI 0.7528/0.5580。按人两活动平均分别0.5113 [0.5021,0.5207]、0.6144 [0.5813,0.6382]、0.6554 [0.6196,0.6958]。标签为参考辅助未匹配，并非伪迹真值；5人已见开发探索，不能称疾病效果。

步行尾段次序异常仅覆盖91/1718=5.30%未匹配候选（逐记录宏平均5.75%），静坐17/539=3.15%。静坐1条无异常，其异常未匹配率按4条算且明确报告。位移IQR按记录宏平均静坐21.88ms/步行62.50ms。异常标记不能解释大部分错误，简单位移偏差和现有SQI在步行分辨力有限。全部候选保留，未选阈值、未翻转AUC、未拒绝数据；时间/PPI覆盖及疾病指标不变。

独立复算171窗5119候选、30个AUC、3个按人区间及4个合成AUC控制通过；旧上升沿逐记录计数精确复现。输出outputs/ppg_quality_dev_v1勿重跑；报告PPG_QUALITY_DEV_REPORT.zh-CN.md、汇总acceptance/PPG_QUALITY_DEV1.json和成果卡仅聚合，研究页更新。下一步先冻结校准段分位阈值的质量保留率/错误代价诊断，所有工作点、真实搏动损失、时间覆盖、原参考分母一起报；不得按尾段选阈值，不直接部署质量拒绝。V1–V5全部证据保持。


## 2026-10-20 PPG_RETENTION_DEV1完成

前次自动审批额度限制未执行；本次恢复后d0fba77先冻结协议/脚本并首次计算。仅原5开发人10记录171尾窗，首120秒4窗SQI的q25/q50/q75阈值加baseline全报告；无尾段选择，参考搏/PPI分母始终完整。独立复算30阈值、171窗、40记录工作点、4按人区间及零输出控制通过，baseline精确复现。

预设q50按人平均：输出PPV+7.71pp [3.52,12.47]，全参考敏感度−23.58pp [−31.44,−13.76]，PPI覆盖−18.57pp [−26.26,−9.61]，核心时间覆盖−28.26pp [−35.28,−18.33]。步行PPV45.87→49.60%，敏感度42.35→26.31%，核心覆盖70.73→47.37%，PPI覆盖25.02→13.64%；条件MAE48.35→48.68ms。q50步行移除418原FP同时丢580原TP，静坐290/675。全部筛选点活动宏F1均下降；不启用现有SQI整窗拒绝、不扩大其阈值搜索。

本地outputs/ppg_retention_dev_v1完成勿重跑。报告PPG_RETENTION_DEV_REPORT.zh-CN.md、群体acceptance/PPG_RETENTION_DEV1.json及成果卡公开；网站研究页、手册已同步。原疾病指标和V1–V5不变。下一步先冻结候选级局部模板/相邻间期一致性定义，对照已有窗级SQI，校准/训练内定规则，全部尾段评估有效搏动保留与错误排序；先证明信号信息增益再考虑筛选，不切新融合/疾病终点。


## 2026-10-20 PPG_LOCAL_DEV1完成

77ca846预先冻结候选级形态/间期风险，仅首120秒PPG构模板和间期中位数。5开发人211窗7954候选全保留，171尾窗5119候选沿用已复核标签。静坐模板/间期/SQI AUC 0.8204/0.7665/0.7528；步行0.5107/0.5631/0.5580。模板减SQI按人差+0.0101 [−0.0049,0.0290]，间期+0.0094 [−0.0653,0.0702]，均跨零。不能说总体改善，不启用筛选或扩展这组手工参数。

独立MAT/插值/相关性复算7954候选、5119尾候选30个AUC与5个区间通过，旧SQI精确复现；共享SciPy内核披露。静坐204、步行218单侧邻间期候选保留；无默认空形状触发。原F1/PPI/时间覆盖与疾病指标不变。输出outputs/ppg_local_dev_v1勿重跑；报告PPG_LOCAL_DEV_REPORT.zh-CN.md、聚合acceptance/PPG_LOCAL_DEV1.json、卡片与研究页已更新。

下一步优先人工质量标签入口审计，避免继续盲调同类手工特征。已查Segade作者仓库https://github.com/chengstark/Segade及2024预印本https://www.medrxiv.org/content/10.1101/2024.06.07.24308621v1.full：腕部逐点伪迹标签、DaLiA/WESAD/TROIKA来源；先核实代码/数据许可、下载可达性、标签语义、受试者映射与已见DaLiA重叠。尚未下载数据或借用代码，不能把整个资源当外部验证；不向作者发消息。先审计/冻结再训练，仍只研究PPG质量。7306段为论文描述，尚非本地核验计数。


## 2026-10-20 SEGADE_SOURCE1完成：结构可达，训练准入未通过

固定作者commit f5b2ad6e180a1474bc47d6c5ec5d482edaed6797；Git完整树105blob、data恰8文件。HTTP Range读取8个NPY前缀，均206；只保存128字节头，无完整波形/标签下载。numpy独立核验4组shape与Git文件大小：DaLiA train3436/test869、WESAD2888、TROIKA113，合计7306段×1920。标签dtype为float64，实际0/1取值/重复/对齐尚未核验，不能把结构审计说成数据集验收。

GitHub license为空，树中无许可名称文件，README/两脚本无许可关键词；代码和新增标签复用许可未明确。data无逐行身份/时间sidecar，db2npy顶层只导出两数组；data_split用shuffle KFold对X行分折而非group。外层按人说明不等于内层按人，不直接宣称全论文泄漏。未训练、不执行第三方代码、不联系作者。初版审计器误计SQLite函数内np.save，已改AST仅核顶层，结构验收通过。

公开docs/SEGADE_SOURCE_AUDIT.zh-CN.md、acceptance/SEGADE_SOURCE1.json、fetch_segade_metadata.py和audit_segade_headers.py及卡片。缓存outputs/segade_source_audit_v1完成勿重复下载；头SHA和源码摘要记录，不能冒充全文件SHA。原算法、疾病指标/覆盖不变。

下一步优先审计BUT PPG 2.0官方CC BY4入口的质量标签表、受试者ID与10秒30Hz结构，作为有明确许可的方法校验备用；手机域不等于腕部运动验证，禁止拼10秒为伪30秒。再检查PhysioKit SQA-Phys是否真有可取得且许可明确的腕部训练标签。尚未下载上述两者波形/训练标签。不盲调同类手工参数，不因Segade缺口停整个项目或请求联系他人。


## 2026-10-20 BUT_SOURCE1完成：明确许可与分组，先修导入边界

上一轮审批额度暂不可用，复制/下载未执行；本轮恢复后首次执行。BUT PPG2.0本地标签/采集表/PPG索引各3888条，50人，一一匹配，无标签/HR缺失或重复ID。好830、差3058，始终判差accuracy78.65%；49人双类、1人单类，每人4–108条。初版12人48条、扩展38人3840条；耳1962/指1926，12条复合活动2;3保留。CSV两种解析计数一致，9个元数据/头SHA与官方清单一致。主站清单慢，终止原下载并用官方S3镜像取得；无波形下载。初次csv未处理BOM已修正，源数据未更改。

固定四头抽查：旧版首尾均300信号/30Hz/1点，新版首尾3信号/30Hz/300点。不能直接取第一列或flatten冒充10秒序列；wfdb可选包当前未装，没有声称其读取验收通过。下一步先冻结跨版本波形适配协议，独立解码核对增益/基线、时间轴、RGB通道，之后冻结按人分组再评分；全部失败记录和覆盖要报。仅质量方法的手机域对照，不是腕部外部验证，不改疾病终点，不拼片段。PhysioKit README示例为指/耳，纠正此前“腕部标签”线索措辞，训练集仍待查。

本地outputs/but_source_v1缓存勿重下；公开脚本、BUT_SOURCE_AUDIT.zh-CN.md、BUT_SOURCE1.json及聚合卡。无新模型或疾病指标，V1–V5保持。训练准入待适配及分组协议，元数据验收已通过。


## 2026-10-20 BUT_ADAPTER1完成：原布局数值通过，legacy时间轴待定

96e0162先冻结四样本协议/自写读取器/7合成测试，再下载2.0.0官方S3的4条PPG波形。8个头/波形SHA通过；与隔离安装的WFDB4.3.1数字逐值一致、物理最大误差0，2400值全有限，缺失码0。旧版2条仍1×300，新版2条300×3；未reshape、未选通道、未读标签评分、未训练。新版共6个32767编码端点保留，不直接解释硬件削顶。

首次真实检查单位等同性失败：源a.u.被WFDB解析成a，核查其单位正则不接受点号。保留原始单位，把差异显式入JSON，未改源头/样本/容差；不能声称元数据完全一致。独立数值验收通过不等于legacy时间轴通过。outputs/but_adapter_v1/completed.json已完成勿重跑；outputs/adapter_tools为本地可选验证库，未改全局依赖。

公开BUT_ADAPTER_PROTOCOL.zh-CN.md、BUT_ADAPTER_REPORT.zh-CN.md、BUT_ADAPTER1.json、自写读取/测试/运行器与成果卡。下一步补旧版时间顺序的来源证据和全量导入覆盖；如48条legacy仍不能准入，明确列入失败分母，不能静默删除后称全库100%。之后冻结按人分组/通道再评分。V1–V5疾病指标及覆盖不变，手机指/耳不能替代腕部验证。


推进边界：旧版时间轴问题不应无限阻塞已知RGB布局的扩展版。下一轮先对扩展版3840条/38人做全量导入覆盖审计，同时保留初版48条/12人技术待定清单。若无法获得旧版时间顺序的可靠依据，可以在任何模型评分前预注册“扩展版固定子队列”，以明确的发布阶段/采集格式定义范围，并分别报3888条总库与3840条目标队列的覆盖；不得称50人全库验证、不得按质量标签或效果挑样本。此举只用于新的手机质量方法对照，不删改原T1D事件或V1–V5分母。
