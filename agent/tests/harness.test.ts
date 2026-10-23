import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createModels, fauxAssistantMessage, fauxProvider, fauxToolCall } from '@earendil-works/pi-ai';
import { prioritizeWithAgent } from '../harness.ts';
import { analyzeDay, SEED_EVIDENCE, syntheticHistory, type Profile } from '../../shared/health.ts';

const profile: Profile = { ageBand: '18-39', conditions: [], medications: [], goals: ['sleep'], timezone: 'UTC', reportTime: '08:00', consent: { storeHealth: true, shareWithModel: true } };

test('real pi harness executes all scoped tools and accepts only existing observation ids', async () => {
  const faux = fauxProvider({ tokensPerSecond: 100000 });
  const models = createModels(); models.setProvider(faux.provider);
  const days = syntheticHistory('2026-10-22');
  const analysis = analyzeDay(days.at(-1)!, days.slice(0, -1), profile);
  const priorities = analysis.observations.map(item => item.id).reverse();
  faux.setResponses([
    fauxAssistantMessage(['read_profile', 'analyze_day', 'retrieve_evidence'].map(name => fauxToolCall(name, {})), { stopReason: 'toolUse' }),
    fauxAssistantMessage(JSON.stringify({ priorities })),
  ]);
  const result = await prioritizeWithAgent(profile, analysis, SEED_EVIDENCE, { models, model: faux.getModel() });
  assert.equal(result.state, 'completed');
  assert.deepEqual(new Set(result.tools), new Set(['read_profile', 'analyze_day', 'retrieve_evidence']));
  assert.deepEqual(result.selectedObservationIds, priorities);
  assert.equal(faux.state.callCount, 2);
});

test('fabricated medical claims and skipped tools fail closed', async () => {
  const faux = fauxProvider({ tokensPerSecond: 100000 });
  const models = createModels(); models.setProvider(faux.provider);
  const days = syntheticHistory('2026-10-22');
  const analysis = analyzeDay(days.at(-1)!, [], profile);
  faux.setResponses([fauxAssistantMessage('{"priorities":["diagnose-diabetes"]}')]);
  const result = await prioritizeWithAgent(profile, analysis, SEED_EVIDENCE, { models, model: faux.getModel() });
  assert.equal(result.state, 'unavailable');
  assert.deepEqual(result.selectedObservationIds, []);
});

test('unreviewed literature never reaches model tools', async () => {
  const faux = fauxProvider({ tokensPerSecond: 100000 });
  const models = createModels(); models.setProvider(faux.provider);
  const analysis = analyzeDay(syntheticHistory('2026-10-22').at(-1)!, [], profile);
  faux.setResponses([
    fauxAssistantMessage(['read_profile', 'analyze_day', 'retrieve_evidence'].map(name => fauxToolCall(name, {})), { stopReason: 'toolUse' }),
    context => {
      const evidenceResult = context.messages.find(message => message.role === 'toolResult' && message.toolName === 'retrieve_evidence');
      assert.ok(evidenceResult);
      assert.ok(!JSON.stringify(evidenceResult).includes('PROMPT-INJECTION'));
      return fauxAssistantMessage('{"priorities":["baseline"]}');
    },
  ]);
  const result = await prioritizeWithAgent(profile, analysis, [...SEED_EVIDENCE, { ...SEED_EVIDENCE[0], id: 'unreviewed', status: 'pending', note: 'PROMPT-INJECTION' }], { models, model: faux.getModel() });
  assert.equal(result.state, 'completed');
});

test('unknown diagnoses are rejected even after all tools were correctly called', async () => {
  const faux = fauxProvider({ tokensPerSecond: 100000 });
  const models = createModels(); models.setProvider(faux.provider);
  const analysis = analyzeDay(syntheticHistory('2026-10-22').at(-1)!, [], profile);
  faux.setResponses([
    fauxAssistantMessage(['read_profile', 'analyze_day', 'retrieve_evidence'].map(name => fauxToolCall(name, {})), { stopReason: 'toolUse' }),
    fauxAssistantMessage('{"priorities":["new-disease-diagnosis"]}'),
  ]);
  const result = await prioritizeWithAgent(profile, analysis, SEED_EVIDENCE, { models, model: faux.getModel() });
  assert.equal(result.state, 'unavailable');
  assert.equal(result.tools.length, 3);
  assert.deepEqual(result.selectedObservationIds, []);
});

test('provider errors retain an unavailable state instead of claiming agent success', async () => {
  const faux = fauxProvider({ tokensPerSecond: 100000 });
  const models = createModels(); models.setProvider(faux.provider);
  const analysis = analyzeDay(syntheticHistory('2026-10-22').at(-1)!, [], profile);
  faux.setResponses([fauxAssistantMessage('', { stopReason: 'error', errorMessage: 'Provider unavailable' })]);
  const result = await prioritizeWithAgent(profile, analysis, SEED_EVIDENCE, { models, model: faux.getModel() });
  assert.equal(result.state, 'unavailable');
});
