import { SEED_EVIDENCE, type Evidence } from '../shared/health.ts';
import type { HealthStore } from './store.ts';

export function knowledge(store: HealthStore): Evidence[] {
  const stored = store.list<Evidence>('knowledge', 'paper');
  return [...new Map([...SEED_EVIDENCE, ...stored].map(paper => [paper.id, paper])).values()];
}

export async function refreshKnowledge(store: HealthStore, fetcher: typeof fetch = fetch, now = new Date()): Promise<{ added: number; checkedAt: string }> {
  const previous = store.get<{ checkedAt: string }>('knowledge', 'sync', 'latest');
  const start = new Date(now.getTime() - 30 * 86400000).toISOString().slice(0, 10);
  const end = now.toISOString().slice(0, 10);
  const query = `(TITLE_ABS:wearable OR TITLE_ABS:smartwatch) AND (TITLE_ABS:diabetes OR TITLE_ABS:sleep OR TITLE_ABS:"personal health") AND FIRST_PDATE:[${start} TO ${end}]`;
  const url = new URL('https://www.ebi.ac.uk/europepmc/webservices/rest/search');
  url.search = new URLSearchParams({ query, format: 'json', pageSize: '25', sort: 'FIRST_PDATE_D desc' }).toString();
  const response = await fetcher(url, { signal: AbortSignal.timeout(15000), redirect: 'error' });
  if (!response.ok) throw new Error('Literature source unavailable');
  const payload = await response.json() as { resultList?: { result?: { id?: string; source?: string; title?: string; firstPublicationDate?: string; pubYear?: string }[] } };
  if (!Array.isArray(payload.resultList?.result)) throw new Error('Invalid literature response');
  let added = 0;
  for (const paper of payload.resultList.result) {
    if (!paper.id || !paper.source || !paper.title || !/^[a-z\d]+$/i.test(paper.id) || !/^[a-z]+$/i.test(paper.source)) continue;
    const id = `${paper.source}:${paper.id}`;
    if (store.get('knowledge', 'paper', id)) continue;
    const entry: Evidence = {
      id, title: paper.title.slice(0, 500), url: `https://europepmc.org/article/${paper.source}/${paper.id}`,
      published: paper.firstPublicationDate ?? paper.pubYear ?? 'unknown', status: 'pending', kind: 'research',
      note: '自动检索的候选文献，待核验研究设计、适用人群、撤稿状态与局限；尚不用于健康建议。',
    };
    store.put('knowledge', 'paper', id, entry);
    added++;
  }
  const checkedAt = now.toISOString();
  store.put('knowledge', 'sync', 'latest', { checkedAt, added, previousCheckedAt: previous?.checkedAt, query, source: url.origin });
  return { added, checkedAt };
}

export function reviewEvidence(store: HealthStore, id: string, note: string): void {
  const entry = store.get<Evidence>('knowledge', 'paper', id);
  if (!entry || note.trim().length < 20) throw new Error('A candidate id and a substantive review note are required');
  store.put('knowledge', 'paper', id, { ...entry, status: 'reviewed', reviewedAt: new Date().toISOString(), note: note.slice(0, 2000) });
}
