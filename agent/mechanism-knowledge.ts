import type { Evidence } from '../shared/health.ts';

// Public source summaries only. No user candidates or individual protein measurements.
export const MECHANISM_EVIDENCE: Evidence[] = [
  {
    id: 'spaid-evidence-tiers-2026', title: 'SPAID：自身抗原证据等级与疾病背景',
    url: 'https://link.springer.com/article/10.1007/s44307-026-00117-8',
    published: '2026-06-08', status: 'reviewed', kind: 'research', reviewedAt: '2026-10-23',
    note: '文献机制知识：区分实验验证自身抗原与候选层级；检测到蛋白或表达变化不等于修饰或免疫原性得到验证。未提供本项目患者的配对蛋白、可穿戴和结局数据；不能作为个人实测特征或解释某次低血糖的病因。',
  },
  {
    id: 'sting-palmitoylation-2016', title: 'STING Golgi 棕榈酰化与干扰素信号的实验机制',
    url: 'https://www.nature.com/articles/ncomms11932',
    published: '2016-06-21', status: 'reviewed', kind: 'research', reviewedAt: '2026-10-23',
    note: '机制实验：该研究中 STING C88/C91 突变抑制棕榈酰化及信号激活；这是特定实验条件下的机制证据，不是本用户修饰测量、T1D低血糖预测证据或药物建议。',
  },
];

export function withMechanismEvidence(evidence: Evidence[]): Evidence[] {
  // Caller-provided review status takes precedence, including deliberate pending status.
  const ids = new Set(evidence.map(item => item.id));
  return [...evidence, ...MECHANISM_EVIDENCE.filter(item => !ids.has(item.id))];
}
