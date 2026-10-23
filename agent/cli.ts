import { issueToken, requireSecret } from './auth.ts';
import { refreshKnowledge, reviewEvidence } from './knowledge.ts';
import { HealthStore } from './store.ts';

const [command, subjectOrId, ...notes] = process.argv.slice(2);
if (command === 'token') {
  console.log(issueToken(subjectOrId ?? 'demo-user', requireSecret(process.env.HEALTH_TOKEN_SECRET, 'HEALTH_TOKEN_SECRET')));
} else {
  const store = new HealthStore(process.env.HEALTH_DATA_DIR ?? '.private/health-agent', requireSecret(process.env.HEALTH_DATA_KEY, 'HEALTH_DATA_KEY'));
  try {
    if (command === 'refresh') console.log(JSON.stringify(await refreshKnowledge(store)));
    else if (command === 'review') {
      reviewEvidence(store, subjectOrId, notes.join(' '));
      console.log('Evidence review recorded. No model weights or medical thresholds changed.');
    } else throw new Error('Use token, refresh or review');
  } finally {
    store.close();
  }
}
