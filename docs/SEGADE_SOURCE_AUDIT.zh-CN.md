# Segade人工腕部质量标签：入口与复用条件审计

2026-10-20 · SEGADE_SOURCE1 · 仅元数据/数组头审计

已确认作者仓库4组数据的8个NPY文件入口可达，头部声明合计7306段、每段1920采样点，信号/标签尺寸配对一致。但本轮不能将其作为已验收训练集：未找到明确代码/新增标签许可，数组旁没有逐行受试者/时间映射；示例交叉验证按数组行随机分折，不能直接沿用为按人验证。

## 实际核查范围

固定作者提交[f5b2ad6e180a1474bc47d6c5ec5d482edaed6797](https://github.com/chengstark/Segade/tree/f5b2ad6e180a1474bc47d6c5ec5d482edaed6797)。GitHub完整树有105个blob且未截断，data目录恰8个文件。只读取每文件前1024字节，HTTP均206；只保存其中128字节NPY头，后续样本字节未落盘。读取了README、分折与导出脚本用于审计，没有执行第三方代码、下载完整波形或训练模型。

|目录|信号头shape|标签头shape|dtype|尺寸配对|
|---|---|---|---|---|
|TROIKA_channel_1|(113, 1920)|(113, 1920)|float64|一致|
|WESAD_all|(2888, 1920)|(2888, 1920)|float64|一致|
|new_PPG_DaLiA_test|(869, 1920)|(869, 1920)|float64|一致|
|new_PPG_DaLiA_train|(3436, 1920)|(3436, 1920)|float64|一致|

本轮7306是数组头声明行数的独立核验，不是完整数据质量验收。实际标签是否全为0/1、缺失/重复片段、波形与标签对齐、文件完整SHA256尚未检查。Git blob SHA与头SHA256已保存，不能把头哈希当全文件哈希。[验收JSON](acceptance/SEGADE_SOURCE1.json)公开这些范围与未核验项。

## 三个准入缺口

1. **复用许可尚未明确。** GitHub仓库license字段为空；完整文件树未发现名称含LICENSE/LICENCE/COPYING/NOTICE的文件，README、data_split.py、db2npy.py未检出许可/版权声明关键词。本次证据不足以确认代码或人工新增标签的再利用/再分发条件；这不代表作出法律定性，也不能把原始DaLiA等数据的许可自动套给衍生标签。本项目暂不导入其实现、权重或完整标签训练。
2. **受试者映射缺口。** data目录只有scaled_ppgs.npy与seg_labels.npy配对，没有身份/时间sidecar；顶层db2npy.py只导出这两个数组。它读取中间数据库，但被检查的公开树中没有对应逐行映射入口。不能据文件夹名恢复每行属于哪位受试者，也不能据此判断与本项目已见DaLiA数据是否重叠。[导出脚本](https://github.com/chengstark/Segade/blob/f5b2ad6e180a1474bc47d6c5ec5d482edaed6797/db2npy.py)
3. **示例内部分折不满足本项目按人隔离。** data_split.py使用带shuffle的KFold并直接对X按行分折，调用时没有groups。这不能证明作者外层训练/测试人群混合，但它确实不能作为本项目受试者隔离的内层验证方案。[分折脚本](https://github.com/chengstark/Segade/blob/f5b2ad6e180a1474bc47d6c5ec5d482edaed6797/data_split.py)

作者README说明30秒片段人工转成二值掩码，并将DaLiA外层按受试者划分；这个说明与内层代码的按行KFold是两个层次。不能把二者混淆后直接宣称整个方法泄漏，也不能照搬内层分折。其公开data目录本轮未见UCSF数组，README提到过该评价集不等于当前目录已提供。[README](https://github.com/chengstark/Segade/blob/f5b2ad6e180a1474bc47d6c5ec5d482edaed6797/README.md)

## 标注含义仍需区分

[2024相关方法预印本](https://www.medrxiv.org/content/10.1101/2024.06.07.24308621v1.full)描述这批标签参考运动、ECG和PPG观察，初始50段用于多人对齐标注规则，余下单人标注。其文中说明DaLiA训练来自ID2–13；与本项目已见开发人群有来源重合，但没有逐行映射，无法在本轮确认重复片段范围。此段是论文描述，不是对NPY值的审计结果。

人工伪迹标签也不同于ECG匹配标签、可靠PPI标签或低血糖标签。本轮无新模型性能，旧F1、AUC、事件召回、误报/参考人日、及时性、PPV与覆盖全部保持。

## 可执行后续

Segade保留为参考入口，本阶段“头结构审计通过、训练准入未通过”。不联系作者、不盲目下载模型，也不把缺许可转变成要求用户解决的前置条件。

下一步先审计明确许可的[BUT PPG 2.0官方入口](https://physionet.org/content/butppg/2.0.0/121063/)的质量标注、受试者ID规则和数据结构。官方列出CC BY 4.0、3888条10秒记录、50名受试者、30Hz手机PPG。它可作为质量标签方法验证的备用入口，不能替代腕部运动验证；不能把10秒数据拼接成伪30秒，也不能将其血糖单值注释变为本项目新临床终点。本轮尚未下载其波形或核验标签表。

继续寻找明确许可的腕部人工标签，可核查[PhysioKit作者项目](https://github.com/PhysiologicAILab/PhysioKit)的SQA-Phys资源；[原论文](https://www.mdpi.com/1424-8220/23/19/8244)描述了质量模块，但代码开放不等于训练数据已开放。本轮不宣称已取得其训练标签。

## 复现与验收

从仓库根目录运行 `python scripts/fetch_segade_metadata.py`，再运行 `python scripts/audit_segade_headers.py`。前者固定上述提交、仅读元数据/前缀，可选GITHUB_TOKEN仅发送GitHub API、不写盘；已存在本轮缓存时拒绝覆盖。后者用numpy.lib.format独立解析保存的头，与最初ast字面量解析交叉验证，并核验shape×dtype字节数+头长等于Git尺寸、四组信号/标签一致。

验收通过8文件/4组头结构及分折/导出代码观察。首轮审计器把函数内SQLite序列化np.save也计成顶层文件导出而触发断言；已改用AST仅检查模块顶层表达式后通过，未改第三方数据或脚本。原始读取代码和文本只在ignored输出，公开只有本项目审计工具、结构汇总与证据哈希。
