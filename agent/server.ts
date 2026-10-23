import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { localClock, validateDay, validateProfile, type DailyData, type DailyReport, type Profile } from '../shared/health.ts';
import { authenticate, requireSecret } from './auth.ts';
import { knowledge } from './knowledge.ts';
import { generateReport } from './reports.ts';
import { HealthStore } from './store.ts';

async function readBody(request: IncomingMessage): Promise<unknown> {
  let size = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    const buffer = Buffer.from(chunk);
    size += buffer.length;
    if (size > 256000) throw new Error('Request too large');
    chunks.push(buffer);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8')) as unknown;
}

function send(response: ServerResponse, status: number, data: unknown): void {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' });
  response.end(JSON.stringify(data));
}

export function createHealthServer(store: HealthStore, tokenSecret: string, allowedOrigin: string) {
  const generations = new Map<string, number>();
  return createServer(async (request, response) => {
    if (request.headers.origin && request.headers.origin !== allowedOrigin) {
      send(response, 403, { error: 'Origin not allowed' });
      return;
    }
    if (request.headers.origin === allowedOrigin) {
      response.setHeader('Access-Control-Allow-Origin', allowedOrigin);
      response.setHeader('Vary', 'Origin');
      response.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
      response.setHeader('Access-Control-Allow-Methods', 'GET, PUT, POST, DELETE, OPTIONS');
    }
    if (request.method === 'OPTIONS') { response.writeHead(204); response.end(); return; }
    const subject = authenticate(request.headers.authorization, tokenSecret);
    if (!subject) { send(response, 401, { error: 'Personal access token required' }); return; }
    const url = new URL(request.url ?? '/', 'http://localhost');
    try {
      if (url.pathname === '/api/profile' && request.method === 'GET') {
        send(response, 200, { profile: store.get<Profile>(subject, 'profile', 'current') ?? null });
      } else if (url.pathname === '/api/profile' && request.method === 'PUT') {
        const profile = validateProfile(await readBody(request));
        store.put(subject, 'profile', 'current', profile);
        send(response, 200, { profile });
      } else if (url.pathname === '/api/days' && request.method === 'PUT') {
        const profile = store.get<Profile>(subject, 'profile', 'current');
        if (!profile?.consent.storeHealth) { send(response, 409, { error: 'Create a consenting profile first' }); return; }
        const input = await readBody(request);
        const batch = (Array.isArray(input) ? input : [input]).map(validateDay);
        if (batch.length > 90 || !batch.length || new Set(batch.map(day => day.date)).size !== batch.length) throw new Error('Invalid batch');
        if (batch.some(day => day.date >= localClock(new Date(), profile.timezone).date)) throw new Error('Only completed local days can be imported');
        for (const day of batch) store.put(subject, 'day', day.date, day);
        send(response, 200, { imported: batch.length });
      } else if (url.pathname === '/api/days' && request.method === 'GET') {
        send(response, 200, { days: store.list<DailyData>(subject, 'day').slice(-90) });
      } else if (url.pathname === '/api/reports' && request.method === 'GET') {
        send(response, 200, { reports: store.list<DailyReport>(subject, 'report').reverse().slice(0, 30) });
      } else if (url.pathname === '/api/reports/generate' && request.method === 'POST') {
        if (Date.now() - (generations.get(subject) ?? 0) < 60000) { send(response, 429, { error: 'Wait one minute before regenerating' }); return; }
        const body = await readBody(request) as { date?: unknown };
        if (!body || typeof body.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(body.date)) throw new Error('Invalid report date');
        generations.set(subject, Date.now());
        send(response, 200, { report: await generateReport(store, subject, body.date) });
      } else if (url.pathname === '/api/reports/read' && request.method === 'POST') {
        const body = await readBody(request) as { date?: unknown };
        if (!body || typeof body.date !== 'string') throw new Error('Invalid report date');
        const report = store.get<DailyReport>(subject, 'report', body.date);
        if (!report) { send(response, 404, { error: 'Report not found' }); return; }
        store.put(subject, 'report', body.date, { ...report, readAt: new Date().toISOString() });
        send(response, 200, { ok: true });
      } else if (url.pathname === '/api/evidence' && request.method === 'GET') {
        send(response, 200, { papers: knowledge(store), sync: store.get('knowledge', 'sync', 'latest') ?? null });
      } else if (url.pathname === '/api/account' && request.method === 'DELETE') {
        store.deleteSubject(subject);
        send(response, 200, { deleted: true, note: 'Live records deleted. Operator-managed backups require separate retention controls.' });
      } else {
        send(response, 404, { error: 'Route not found' });
      }
    } catch {
      send(response, 400, { error: 'Request could not be completed. Check consent, dates and input format.' });
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const dataKey = requireSecret(process.env.HEALTH_DATA_KEY, 'HEALTH_DATA_KEY');
  const tokenSecret = requireSecret(process.env.HEALTH_TOKEN_SECRET, 'HEALTH_TOKEN_SECRET');
  if (dataKey === tokenSecret) throw new Error('Use independent encryption and authentication secrets');
  const store = new HealthStore(process.env.HEALTH_DATA_DIR ?? '.private/health-agent', dataKey);
  const server = createHealthServer(store, tokenSecret, process.env.HEALTH_ALLOWED_ORIGIN ?? 'http://127.0.0.1:5173');
  server.requestTimeout = 45000;
  server.headersTimeout = 10000;
  server.listen(Number(process.env.HEALTH_PORT ?? 8787), process.env.HEALTH_HOST ?? '127.0.0.1', () => console.log('Private health API ready. Provider credentials are never served.'));
  for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => server.close(() => { store.close(); process.exit(0); }));
}
