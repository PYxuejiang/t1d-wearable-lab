import type { Evidence } from '../shared/health.ts';

// Aggregate study findings only. Never personal model scores or training labels.
export const RESEARCH_EVIDENCE: Evidence[] = [
  {
    id: 'lab-pulse-temporal-fit2', title: '本项目：真实 T1D 时序微调与 LoRA 对照',
    url: 'https://github.com/PYxuejiang/t1d-wearable-lab/blob/main/docs/acceptance/PULSE_TEMPORAL_FIT2.json',
    published: '2026-10-23', reviewedAt: '2026-10-23', status: 'reviewed', kind: 'research',
    note: '4人训练、1人验证，18个候选全部保留并复核。验证AP：线性头0.0955、全量时序微调0.0931、LoRA0.0781、病例比例基线0.0683。LoRA本轮选择r4/alpha8/lr0.001；不是全局最优。参考决策点覆盖80.1%，未评估测试集或事件报警，也未证明配对背景增益。验证分数已用于选模型，不能作为个人风险或独立泛化结果。不得改变今天的异常等级或自动触发再训练。',
  },
  {
    id: 'lab-pulse-transfer1', title: '本项目：真实 PPG 预训练表示接入',
    url: 'https://github.com/PYxuejiang/t1d-wearable-lab/blob/main/docs/MULTIMODAL_BRANCHES.zh-CN.md',
    published: '2026-10-23', reviewedAt: '2026-10-23', status: 'reviewed', kind: 'method',
    note: '工程证据：MIT Pulse-PPG 编码器在 PPG-DaLiA 5人150窗生成有效512维表示，重复运行一致；可接时序Transformer与LoRA。不是个人模型输出；不证明低血糖识别、心率准确性或临床报警有效。公开权重为CNN，新增时序Transformer的训练与比较另行验收。',
  },
  {
    id: 'lab-antibody-array1', title: '本项目：GSE45515 独立抗体芯片分支',
    url: 'https://github.com/PYxuejiang/t1d-wearable-lab/blob/main/docs/acceptance/ANTIBODY_ARRAY1.json',
    published: '2026-10-23', reviewedAt: '2026-10-23', status: 'reviewed', kind: 'research',
    note: '149张芯片、774条目，按104个保守命名组做嵌套交叉验证；全条目逻辑回归AUC0.882、AP0.872。组不等于已确认患者；病例/对照总说明与逐样本标签数量冲突。仅17个pNA条目也有AUC0.735，批次与非特异差异尚未排除。不是个人患病概率、当前低血糖检测或可穿戴增益。该队列无配对可穿戴，不允许按疾病名称拼接患者，也不用于改变今天的异常等级。',
  },
];

export function withResearchEvidence(evidence: Evidence[]): Evidence[] {
  const ids = new Set(evidence.map(item => item.id));
  return [...evidence, ...RESEARCH_EVIDENCE.filter(item => !ids.has(item.id))];
}
