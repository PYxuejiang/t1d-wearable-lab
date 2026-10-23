import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { test } from 'node:test';
import { HealthStore } from '../store.ts';
import { authenticate, issueToken } from '../auth.ts';
import { createHealthServer } from '../server.ts';
import { generateReport, runDailyReports } from '../reports.ts';
import { knowledge, refreshKnowledge, reviewEvidence } from '../knowledge.ts';
import { syntheticHistory, type DailyReport, type Profile } from '../../shared/health.ts';

const profile: Profile = { ageBand: '18-39', conditions: ['PRIVATE-HEALTH-MARKER'], medications: [], goals: ['sleep'], timezone: 'Asia/Shanghai', reportTime: '08:00', consent: { storeHealth: true, shareWithModel: false } };

test('encrypted persistence survives restart, prevents cross-user reads and rejects wrong keys', () => {
  const directory = mkdtempSync(join(tmpdir(), 'health-store-'));
  const key = randomBytes(32).toString('hex');
  let store = new HealthStore(directory, key);
  try {
    store.put('alice', 'profile', 'current', profile);
    assert.equal(store.get('bob', 'profile', 'current'), undefined);
    store.close();
    assert.ok(!readFileSync(join(directory, 'health.sqlite')).includes(Buffer.from('PRIVATE-HEALTH-MARKER')));
    store = new HealthStore(directory, key);
    assert.deepEqual(store.get('alice', 'profile', 'current'), profile);
    const wrong = new HealthStore(directory, randomBytes(32).toString('hex'));
    try { assert.throws(() => wrong.get('alice', 'profile', 'current')); } finally { wrong.close(); }
  } finally { store.close(); rmSync(directory, { recursive: true, force: true }); }
});

test('authenticated API rejects CORS/forged tokens and isolates profile, reports and deletion', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'health-http-'));
  const store = new HealthStore(directory, randomBytes(32).toString('hex'));
  const secret = randomBytes(32).toString('hex');
  const server = createHealthServer(store, secret, 'http://127.0.0.1:5173');
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const address = server.address(); assert.ok(address && typeof address !== 'string');
  const base = `http://127.0.0.1:${address.port}/api`;
  const headers = { Authorization: `Bearer ${issueToken('alice', secret)}`, 'Content-Type': 'application/json' };
  try {
    assert.equal(authenticate(`Bearer ${issueToken('alice', secret)}x`, secret), undefined);
    assert.equal((await fetch(`${base}/profile`)).status, 401);
    assert.equal((await fetch(`${base}/profile`, { headers: { ...headers, Origin: 'https://evil.example' } })).status, 403);
    assert.equal((await fetch(`${base}/profile`, { method: 'PUT', headers, body: JSON.stringify(profile) })).status, 200);
    const other = await fetch(`${base}/profile`, { headers: { Authorization: `Bearer ${issueToken('bob', secret)}` } });
    assert.deepEqual(await other.json(), { profile: null });
    const days = syntheticHistory('2026-01-02');
    assert.equal((await fetch(`${base}/days`, { method: 'PUT', headers, body: JSON.stringify(days) })).status, 200);
    const generated = await fetch(`${base}/reports/generate`, { method: 'POST', headers, body: JSON.stringify({ date: '2026-01-02' }) });
    assert.equal(generated.status, 200);
    const value = await generated.json() as { report: DailyReport };
    assert.equal(value.report.mode, 'rules');
    assert.equal(value.report.analysis.baselineDays, 14);
    assert.equal(generated.headers.get('cache-control'), 'no-store');
    assert.equal((await fetch(`${base}/account`, { method: 'DELETE', headers })).status, 200);
    assert.equal(store.list('alice', 'day').length, 0);
    assert.equal(store.list('alice', 'report').length, 0);
  } finally { await new Promise<void>(resolve => server.close(() => resolve())); store.close(); rmSync(directory, { recursive: true, force: true }); }
});

test('daily worker is timezone-aware, idempotent and uses only completed local days', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'health-jobs-'));
  const store = new HealthStore(directory, randomBytes(32).toString('hex'));
  try {
    store.put('alice', 'profile', 'current', profile);
    for (const day of syntheticHistory('2026-10-22')) store.put('alice', 'day', day.date, day);
    assert.equal((await runDailyReports(store, new Date('2026-10-22T23:59:00Z'))).generated, 0);
    assert.equal((await runDailyReports(store, new Date('2026-10-23T00:00:00Z'))).generated, 1);
    assert.equal((await runDailyReports(store, new Date('2026-10-23T00:01:00Z'))).generated, 0);
    await assert.rejects(generateReport(store, 'alice', '2026-10-22', new Date('2026-10-22T01:00:00Z')));
    const report = store.get<DailyReport>('alice', 'report', '2026-10-22')!;
    assert.ok(report.evidence.every(paper => paper.status === 'reviewed'));
  } finally { store.close(); rmSync(directory, { recursive: true, force: true }); }
});

test('literature refresh deduplicates candidates, review is explicit and errors preserve evidence', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'health-evidence-'));
  const store = new HealthStore(directory, randomBytes(32).toString('hex'));
  const fetcher: typeof fetch = async () => new Response(JSON.stringify({ resultList: { result: [{ id: '123456', source: 'MED', title: 'Wearable study', firstPublicationDate: '2026-10-21' }] } }));
  try {
    const initialCount = knowledge(store).length;
    assert.ok(knowledge(store).some(paper => paper.id === 'spaid-evidence-tiers-2026'));
    assert.ok(knowledge(store).some(paper => paper.id === 'sting-palmitoylation-2016'));
    assert.equal((await refreshKnowledge(store, fetcher)).added, 1);
    assert.equal((await refreshKnowledge(store, fetcher)).added, 0);
    assert.equal(knowledge(store).find(paper => paper.id === 'MED:123456')?.status, 'pending');
    assert.throws(() => reviewEvidence(store, 'MED:123456', 'ok'));
    reviewEvidence(store, 'MED:123456', 'Study population and limitations checked; methods reference only, no clinical recommendation.');
    assert.equal(knowledge(store).find(paper => paper.id === 'MED:123456')?.status, 'reviewed');
    await assert.rejects(refreshKnowledge(store, async () => new Response('unavailable', { status: 503 })));
    assert.equal(knowledge(store).length, initialCount + 1);
  } finally { store.close(); rmSync(directory, { recursive: true, force: true }); }
});
