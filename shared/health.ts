export interface Profile {
  ageBand: '18-39' | '40-64' | '65+';
  conditions: string[];
  medications: string[];
  goals: string[];
  timezone: string;
  reportTime: string;
  consent: { storeHealth: boolean; shareWithModel: boolean };
}

export interface DailyData {
  date: string;
  source: 'synthetic' | 'phone-import';
  deviceId: string;
  wearHours: number;
  signalQuality: number;
  restingHeartRate: number | null;
  hrvMs: number | null;
  sleepHours: number | null;
  steps: number | null;
  symptoms: ('chest-pain' | 'severe-breathlessness' | 'fainting')[];
}

export interface Evidence {
  id: string;
  title: string;
  url: string;
  published: string;
  status: 'reviewed' | 'pending';
  kind: 'safety' | 'method' | 'research';
  note: string;
  reviewedAt?: string;
}

export interface Observation {
  id: string;
  title: string;
  detail: string;
  action: string;
}

export interface Analysis {
  status: 'urgent' | 'insufficient-data' | 'review' | 'observing';
  baselineDays: number;
  baseline: Record<string, number>;
  observations: Observation[];
  limitations: string[];
}

export interface DailyReport {
  id: string;
  date: string;
  createdAt: string;
  mode: 'rules' | 'pi-agent';
  analysis: Analysis;
  evidence: Evidence[];
  agent: { state: 'disabled' | 'consent-required' | 'completed' | 'unavailable'; tools: string[]; selectedObservationIds: string[] };
  readAt?: string;
}

export const SEED_EVIDENCE: Evidence[] = [
  { id: 'fda-glucose-2024', title: 'FDA：不要使用手表或戒指独立测量血糖', url: 'https://www.fda.gov/medical-devices/safety-communications/do-not-use-smartwatches-or-smart-rings-measure-blood-glucose-levels-fda-safety-communication', published: '2024-02-21', status: 'reviewed', kind: 'safety', note: 'PPG 和活动摘要不能代替血糖测量；本应用不从手表估算血糖。', reviewedAt: '2026-10-23' },
  { id: 'phia-2025', title: 'PHIA：通过工具与检索解释可穿戴健康数据', url: 'https://arxiv.org/abs/2406.06464', published: '2025-09-08', status: 'reviewed', kind: 'method', note: '支持工具分析与信息检索的系统设计，不是本项目的疾病预测验证。', reviewedAt: '2026-10-23' },
  { id: 'physiollm-2024', title: 'PhysioLLM：生理数据、个人背景与可解释健康洞察', url: 'https://arxiv.org/abs/2406.19283', published: '2024-06-27', status: 'reviewed', kind: 'method', note: '个人背景与统计分析的研究示例；不能据此宣称医疗疗效。', reviewedAt: '2026-10-23' },
];

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected an object');
  return value as Record<string, unknown>;
}

function strings(value: unknown, allowed?: string[]): string[] {
  if (!Array.isArray(value) || value.length > 12 || value.some(item => typeof item !== 'string' || item.length > 100 || (allowed && !allowed.includes(item)))) throw new Error('Invalid list');
  return value as string[];
}

export function validateProfile(value: unknown): Profile {
  const input = record(value);
  const consent = record(input.consent);
  if (!['18-39', '40-64', '65+'].includes(String(input.ageBand))) throw new Error('Invalid adult age band');
  if (typeof input.timezone !== 'string' || typeof input.reportTime !== 'string' || !/^([01]\d|2[0-3]):[0-5]\d$/.test(input.reportTime)) throw new Error('Invalid schedule');
  new Intl.DateTimeFormat('en', { timeZone: input.timezone }).format();
  if (consent.storeHealth !== true || typeof consent.shareWithModel !== 'boolean') throw new Error('Storage consent required');
  return {
    ageBand: input.ageBand as Profile['ageBand'], conditions: strings(input.conditions),
    medications: strings(input.medications), goals: strings(input.goals),
    timezone: input.timezone, reportTime: input.reportTime,
    consent: { storeHealth: true, shareWithModel: consent.shareWithModel },
  };
}

export function validateDay(value: unknown): DailyData {
  const input = record(value);
  if (typeof input.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(input.date) || !Number.isFinite(Date.parse(input.date)) || new Date(input.date).toISOString().slice(0, 10) !== input.date) throw new Error('Invalid date');
  if (!['synthetic', 'phone-import'].includes(String(input.source))) throw new Error('Invalid data source');
  if (typeof input.deviceId !== 'string' || !/^[a-zA-Z0-9_-]{1,64}$/.test(input.deviceId)) throw new Error('Invalid pseudonymous device id');
  const ranges: Record<string, [number, number]> = { wearHours: [0, 24], signalQuality: [0, 1], restingHeartRate: [20, 250], hrvMs: [0, 500], sleepHours: [0, 24], steps: [0, 150000] };
  for (const [field, [minimum, maximum]] of Object.entries(ranges)) {
    const actual = input[field];
    if (actual === null && !['wearHours', 'signalQuality'].includes(field)) continue;
    if (typeof actual !== 'number' || !Number.isFinite(actual) || actual < minimum || actual > maximum) throw new Error(`Invalid ${field}`);
  }
  return {
    date: input.date, source: input.source as DailyData['source'], deviceId: input.deviceId, wearHours: input.wearHours as number,
    signalQuality: input.signalQuality as number, restingHeartRate: input.restingHeartRate as number | null,
    hrvMs: input.hrvMs as number | null, sleepHours: input.sleepHours as number | null, steps: input.steps as number | null,
    symptoms: strings(input.symptoms, ['chest-pain', 'severe-breathlessness', 'fainting']) as DailyData['symptoms'],
  };
}

export function localClock(now: Date, timezone: string): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(now);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return { date: `${values.year}-${values.month}-${values.day}`, time: `${values.hour}:${values.minute}` };
}

export function analyzeDay(day: DailyData, history: DailyData[], profile: Profile): Analysis {
  const eligible = history.filter(previous => previous.date < day.date && previous.source === day.source && previous.deviceId === day.deviceId && previous.date >= new Date(Date.parse(day.date) - 28 * 86400000).toISOString().slice(0, 10) && previous.wearHours >= 12 && previous.signalQuality >= 0.7);
  const unique = [...new Map(eligible.map(previous => [previous.date, previous])).values()];
  const baseline: Record<string, number> = {};
  const observations: Observation[] = [];
  const limitations = ['这是健康趋势观察，未验证为疾病预测或临床报警。', 'PPG 不直接测血糖；血糖相关判断需要适当的血糖测量。', '基线只使用当日之前最多 28 天的同来源、同设备合格数据；工程阈值不是医学诊断阈值。'];
  if (profile.conditions.length || profile.medications.length) limitations.push('已记录既往情况和用药背景；本系统不据此调整药物或提供剂量。');
  if (day.symptoms.length) {
    observations.push({ id: 'symptoms', title: '你填写了需要及时处理的症状', detail: '胸痛、严重呼吸困难或晕厥不能由手表或日报排除风险。', action: '请及时寻求紧急医疗帮助，不等待 AI 报告。' });
    return { status: 'urgent', baselineDays: unique.length, baseline, observations, limitations };
  }
  if (day.wearHours < 12 || day.signalQuality < 0.7) {
    observations.push({ id: 'quality', title: '先补足可靠数据', detail: `佩戴 ${day.wearHours} 小时，信号质量 ${Math.round(day.signalQuality * 100)}%；本日不计算偏离结论。`, action: '检查佩戴和设备同步，继续采集；缺失不代表健康正常。' });
    return { status: 'insufficient-data', baselineDays: unique.length, baseline, observations, limitations };
  }
  for (const field of ['restingHeartRate', 'hrvMs', 'sleepHours', 'steps'] as const) {
    const values = unique.map(previous => previous[field]).filter((value): value is number => value !== null).sort((left, right) => left - right);
    if (values.length < 7 || day[field] === null) continue;
    const median = (values[Math.floor((values.length - 1) / 2)] + values[Math.floor(values.length / 2)]) / 2;
    baseline[field] = Math.round(median * 10) / 10;
    const current = day[field];
    const delta = current - median;
    if (field === 'restingHeartRate' && delta >= 10) observations.push({ id: 'resting-heart-rate', title: '静息心率高于个人近期水平', detail: `今日 ${current} bpm，近期中位数 ${baseline[field]} bpm。`, action: '结合近期活动和身体感受，检查信号后复测；持续异常或不适时咨询医生。' });
    if (field === 'sleepHours' && delta <= -1.5) observations.push({ id: 'sleep', title: '睡眠时长低于个人近期水平', detail: `今日 ${current} 小时，近期中位数 ${baseline[field]} 小时。`, action: '观察作息和后续数日变化；设备估计不能代替睡眠疾病检查。' });
    if (field === 'hrvMs' && median > 0 && delta / median <= -0.25) observations.push({ id: 'hrv', title: 'HRV 低于近期水平', detail: `今日 ${current} ms，近期中位数 ${baseline[field]} ms。`, action: '核对同一设备和测量条件，结合睡眠与活动观察；不能由此诊断疾病。' });
  }
  if (unique.length < 7) observations.push({ id: 'baseline', title: '正在学习你的个人基线', detail: `已积累 ${unique.length} 个合格历史日，至少 7 天后开始趋势比较。`, action: '保持同一设备和相近测量条件；今天不输出疾病概率。' });
  else if (!observations.length) observations.push({ id: 'routine', title: '继续观察个人趋势', detail: Object.keys(baseline).length ? '可比较指标未触发本项目的偏离规则；这不代表排除疾病。' : '历史天数足够，但单项指标缺失，尚无可用的比较基线。', action: '继续记录身体感受、佩戴和同步情况。' });
  const review = observations.some(observation => ['resting-heart-rate', 'sleep', 'hrv'].includes(observation.id));
  return { status: review ? 'review' : 'observing', baselineDays: unique.length, baseline, observations, limitations };
}

export function syntheticHistory(date: string): DailyData[] {
  return Array.from({ length: 15 }, (_, index) => ({
    date: new Date(Date.parse(date) - (14 - index) * 86400000).toISOString().slice(0, 10), source: 'synthetic', deviceId: 'synthetic-watch', wearHours: 22,
    signalQuality: 0.92, restingHeartRate: index === 14 ? 78 : 64 + index % 5,
    hrvMs: index === 14 ? 30 : 43 + index % 6, sleepHours: index === 14 ? 5.5 : 7.2 + index % 3 * 0.2,
    steps: 5600 + index * 130, symptoms: [],
  }));
}
