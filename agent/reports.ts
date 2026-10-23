import { createHash } from 'node:crypto';
import { analyzeDay, localClock, type DailyData, type DailyReport, type Profile } from '../shared/health.ts';
import { configuredModels, prioritizeWithAgent } from './harness.ts';
import { knowledge } from './knowledge.ts';
import type { HealthStore } from './store.ts';

const running = new Set<string>();

export async function generateReport(store: HealthStore, subject: string, date: string, now = new Date()): Promise<DailyReport> {
  if (running.has(subject)) throw new Error('Report generation already running');
  running.add(subject);
  try {
    const profile = store.get<Profile>(subject, 'profile', 'current');
    const day = store.get<DailyData>(subject, 'day', date);
    if (!profile?.consent.storeHealth || !day) throw new Error('Profile consent and daily data required');
    if (date >= localClock(now, profile.timezone).date) throw new Error('Only completed local days can be reported');
    const history = store.list<DailyData>(subject, 'day').filter(previous => previous.date < date);
    const evidence = knowledge(store).filter(paper => paper.status === 'reviewed');
    const fingerprint = JSON.stringify({ profile, day, history, evidence });
    const analysis = analyzeDay(day, history, profile);
    let agent: DailyReport['agent'] = { state: process.env.HEALTH_LLM_ENABLED === 'true' ? 'consent-required' : 'disabled', tools: [], selectedObservationIds: [] };
    if (process.env.HEALTH_LLM_ENABLED === 'true' && profile.consent.shareWithModel && analysis.status !== 'urgent') {
      try {
        agent = await prioritizeWithAgent(profile, analysis, evidence, configuredModels());
      } catch {
        agent = { state: 'unavailable', tools: [], selectedObservationIds: [] };
      }
    }
    if (agent.state === 'completed') analysis.observations.sort((left, right) => agent.selectedObservationIds.indexOf(left.id) - agent.selectedObservationIds.indexOf(right.id));
    const report: DailyReport = {
      id: createHash('sha256').update(fingerprint).digest('hex').slice(0, 20), date, createdAt: now.toISOString(),
      mode: agent.state === 'completed' ? 'pi-agent' : 'rules', analysis, evidence, agent,
    };
    store.transaction(() => {
      const current = store.get<Profile>(subject, 'profile', 'current');
      const currentDay = store.get<DailyData>(subject, 'day', date);
      const currentHistory = store.list<DailyData>(subject, 'day').filter(previous => previous.date < date);
      if (JSON.stringify({ profile: current, day: currentDay, history: currentHistory, evidence: knowledge(store).filter(paper => paper.status === 'reviewed') }) !== fingerprint) throw new Error('Inputs changed during generation; retry required');
      store.put(subject, 'report', date, report);
    });
    return report;
  } finally {
    running.delete(subject);
  }
}

export async function runDailyReports(store: HealthStore, now = new Date()): Promise<{ generated: number; failed: number }> {
  let generated = 0;
  let failed = 0;
  for (const subject of store.subjects()) {
    const profile = store.get<Profile>(subject, 'profile', 'current');
    if (!profile?.consent.storeHealth) continue;
    const clock = localClock(now, profile.timezone);
    if (clock.time < profile.reportTime) continue;
    const date = new Date(Date.parse(clock.date) - 86400000).toISOString().slice(0, 10);
    if (store.get(subject, 'report', date) || !store.get(subject, 'day', date)) continue;
    try {
      await generateReport(store, subject, date, now);
      generated++;
    } catch {
      failed++;
    }
  }
  return { generated, failed };
}
