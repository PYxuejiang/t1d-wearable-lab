import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildResearchSnapshot, type ResearchInput } from '../research-snapshot.ts';
import { MECHANISM_EVIDENCE, withMechanismEvidence } from '../mechanism-knowledge.ts';
import { syntheticHistory } from '../../shared/health.ts';

function input(): ResearchInput {
  return {
    profile: { ageBand: '18-39', conditions: ['PRIVATE-CONDITION'], medications: ['PRIVATE-DRUG'], goals: ['PRIVATE-GOAL'], timezone: 'UTC', reportTime: '08:00', consent: { storeHealth: true, shareWithModel: true } },
    profileAvailableAt: '2026-10-01T00:00:00Z', cutoff: '2026-10-23T08:00:00Z', allowResearchTraining: true,
    days: syntheticHistory('2026-10-22').slice(-3).map(day => ({ day, availableAt: '2026-10-23T00:00:00Z' })),
  };
}

test('snapshot preserves missingness, elapsed gaps, and excludes private narrative and fake labels', () => {
  const data = input(); data.days[0].day.hrvMs = null;
  data.days.splice(1, 1);
  const snapshot = buildResearchSnapshot(data);
  assert.equal(snapshot.values[0][1], 0); assert.equal(snapshot.observed[0][1], false);
  assert.equal(snapshot.elapsed[1][0], 2 / 64);
  assert.equal(snapshot.dataKind, 'synthetic'); assert.equal(snapshot.label, null);
  assert.equal(snapshot.proteinMeasurements, null);
  assert.ok(!JSON.stringify(snapshot).includes('PRIVATE-'));
});

test('model sharing consent does not authorize training', () => {
  const data = input(); data.allowResearchTraining = false;
  assert.throws(() => buildResearchSnapshot(data), /training consent/);
});

test('coverage fields alone do not supply physiological measurements', () => {
  const data = input();
  for (const { day } of data.days) {
    day.restingHeartRate = null; day.hrvMs = null; day.sleepHours = null; day.steps = null;
  }
  assert.throws(() => buildResearchSnapshot(data), /No physiological/);
});

test('future profile, late records, incomplete days, duplicate days and mixed devices fail', () => {
  const profile = input(); profile.profileAvailableAt = '2026-10-24T00:00:00Z';
  assert.throws(() => buildResearchSnapshot(profile), /Future profile/);
  const late = input(); late.days[0].availableAt = '2026-10-24T00:00:00Z';
  assert.throws(() => buildResearchSnapshot(late), /Future record/);
  const incomplete = input(); incomplete.days[0].day.date = '2026-10-23';
  assert.throws(() => buildResearchSnapshot(incomplete), /completed/);
  const duplicate = input(); duplicate.days.push(duplicate.days[0]);
  assert.throws(() => buildResearchSnapshot(duplicate), /Duplicate/);
  const mixed = input(); mixed.days[0].day.deviceId = 'other-device';
  assert.throws(() => buildResearchSnapshot(mixed), /device/);
});

test('explicit evidence review overrides bundled summaries', () => {
  const pending = { ...MECHANISM_EVIDENCE[0], status: 'pending' as const };
  const evidence = withMechanismEvidence([pending]);
  assert.equal(evidence.filter(e => e.id === pending.id).length, 1);
  assert.equal(evidence.find(e => e.id === pending.id)!.status, 'pending');
});
