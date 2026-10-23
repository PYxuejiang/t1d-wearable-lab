import assert from 'node:assert/strict';
import { test } from 'node:test';
import { analyzeDay, localClock, syntheticHistory, validateDay, validateProfile, type Profile } from '../../shared/health.ts';

const profile: Profile = { ageBand: '18-39', conditions: ['T1D'], medications: [], goals: ['sleep'], timezone: 'Asia/Shanghai', reportTime: '08:00', consent: { storeHealth: true, shareWithModel: false } };

test('baseline excludes future, duplicate, low-quality and different-source days', () => {
  const days = syntheticHistory('2026-10-22');
  const day = days.at(-1)!;
  const history = days.slice(0, -1);
  const original = analyzeDay(day, history, profile);
  const extra = [day, { ...day, date: '2026-10-23' }, ...history, ...history.map(item => ({ ...item, date: '2026-10-01', restingHeartRate: 150, signalQuality: 0.1 })), ...history.map(item => ({ ...item, source: 'phone-import' as const, restingHeartRate: 150 }))];
  assert.deepEqual(analyzeDay(day, extra, profile), original);
  assert.equal(original.baselineDays, 14);
  assert.equal(original.status, 'review');
  assert.deepEqual(original.observations.map(item => item.id), ['resting-heart-rate', 'hrv', 'sleep']);
  assert.equal(analyzeDay({ ...day, deviceId: 'different-watch' }, history, profile).baselineDays, 0);
});

test('data quality abstains, cold start abstains, symptoms override insufficient coverage', () => {
  const day = syntheticHistory('2026-10-22').at(-1)!;
  assert.equal(analyzeDay({ ...day, signalQuality: 0.2 }, [], profile).status, 'insufficient-data');
  assert.equal(analyzeDay(day, [], profile).observations[0].id, 'baseline');
  assert.equal(analyzeDay({ ...day, wearHours: 0, symptoms: ['chest-pain'] }, [], profile).status, 'urgent');
});

test('input validation rejects NaN, invalid dates, unknown symptoms and absent consent', () => {
  const day = syntheticHistory('2026-10-22').at(-1)!;
  assert.throws(() => validateDay({ ...day, hrvMs: Number.NaN }));
  assert.throws(() => validateDay({ ...day, date: '2026-02-30' }));
  assert.throws(() => validateDay({ ...day, symptoms: ['unknown'] }));
  assert.throws(() => validateProfile({ ...profile, consent: { storeHealth: false, shareWithModel: false } }));
  assert.throws(() => validateProfile({ ...profile, timezone: 'Moon/Sea' }));
  assert.deepEqual(validateDay({ ...day, hrvMs: null }), { ...day, hrvMs: null });
});

test('local schedule follows timezone across UTC and daylight-saving boundaries', () => {
  assert.deepEqual(localClock(new Date('2026-10-22T23:30:00Z'), 'Asia/Shanghai'), { date: '2026-10-23', time: '07:30' });
  assert.deepEqual(localClock(new Date('2026-11-01T06:30:00Z'), 'America/New_York'), { date: '2026-11-01', time: '01:30' });
});
