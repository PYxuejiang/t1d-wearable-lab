# PPG_FILTER1 滤波与固定定位偏差对照

2026-10-19，执行前冻结。承接已完成PPG_FIDUCIAL1，固定同219条、同70开发/149评价、同MG专家边界和两套参考映射。原评价已见，所有结果是探索性。只研究PPG条件定位，不修改低血糖模型、阈值或队列。

七路全部公开：原信号raw、causal5、offline5、causal12、offline12，以及causal5_centered、causal12_centered。原有raw/causal5/offline12复用已验收的本地预测；新增两路仍为3阶Butterworth带通，下限0.5Hz，上限5/12Hz。causal使用零状态sosfilt；offline使用默认sosfiltfilt。整段处理，MG边界内最大幅值为峰，起点至预测峰内最大中心差分为u，同值取最早，规则与前轮一致。

每个因果方案分别从70条开发MG参考计算峰、u的有符号误差中位数，作为两个全局常数。centered预测=原预测减去对应常数，不按人拟合、不用评价或PC参考、不裁剪到边界，不改变已有峰搜索与滤波器。不删除补偿后出界/顺序异常；全部计误差，另报告出界与严格顺序比例。该操作是参考辅助的时间戳偏差诊断，不是重新找峰。对同一类连续特征减常数不改变相邻间期，因此不能由其误差下降推断PPI变准。

不按本轮结果选胜者。预设配对差（前者减后者）：offline12-offline5、causal12_centered-causal5_centered、causal5_centered-causal5、causal12_centered-causal12、offline12-causal12_centered。MG和PC分别报告pk/u/等权joint的MAE差与10000次按条目bootstrap区间，种子20261019。全部7路两个分区报告MAE/中位/P95/偏差/≤10、20、50ms，参考覆盖、输出率及顺序/越界。无SQI筛选，219分母不变。

这不是严格仅改变相位的消融：双向滤波将单程幅度响应平方、阶数加倍，并改变边缘处理，仍包含幅频/瞬态差异。只能比较固定处理链和去除全局偏差后的剩余误差。[SciPy说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.filtfilt.html)。标注预处理、高质量指端单搏和人工边界的限制保持。

验收：从源MAT独立重读并复算五个未补偿方案；开发常数、全部补偿结果、56个指标组和30个配对区间独立核对。增加合成恒定偏移移除及相邻间期不变控制。不改旧验收JSON；旧三路需精确复现，失败则停止后续应用。原始记录/逐条输出仅ignored outputs，公开群体汇总和源哈希。通过后才决定下一轮腕部开发验证，不把本轮成绩追认为腕部或疾病有效。
