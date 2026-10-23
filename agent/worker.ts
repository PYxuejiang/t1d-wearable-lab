import { requireSecret } from './auth.ts';
import { refreshKnowledge } from './knowledge.ts';
import { runDailyReports } from './reports.ts';
import { HealthStore } from './store.ts';

const store = new HealthStore(process.env.HEALTH_DATA_DIR ?? '.private/health-agent', requireSecret(process.env.HEALTH_DATA_KEY, 'HEALTH_DATA_KEY'));
let active = false;
let lastLiteratureAttempt = 0;
let stopping = false;
async function tick(): Promise<void> {
  if (active || stopping) return;
  active = true;
  try {
    const previous = store.get<{ checkedAt: string }>('knowledge', 'sync', 'latest');
    if ((!previous || Date.now() - Date.parse(previous.checkedAt) >= 86400000) && Date.now() - lastLiteratureAttempt >= 3600000) {
      lastLiteratureAttempt = Date.now();
      try { console.log(JSON.stringify({ job: 'literature', ...await refreshKnowledge(store) })); }
      catch { console.error('Literature refresh failed; previous reviewed evidence retained.'); }
    }
    console.log(JSON.stringify({ job: 'daily-reports', ...await runDailyReports(store) }));
  } finally {
    active = false;
    if (stopping) { store.close(); process.exit(0); }
  }
}
await tick();
if (process.argv.includes('--once')) store.close();
else {
  const interval = setInterval(() => { void tick().catch(() => console.error('Worker tick failed.')); }, 60000);
  for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => {
    stopping = true;
    clearInterval(interval);
    if (!active) { store.close(); process.exit(0); }
  });
}
