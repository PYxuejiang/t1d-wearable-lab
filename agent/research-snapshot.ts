import { validateDay, validateProfile, type DailyData, type Profile } from '../shared/health.ts';

// Offline, opt-in bridge. No store reads, network calls, diagnoses, or training labels.
export interface ResearchInput {
  profile: Profile;
  profileAvailableAt: string;
  cutoff: string;
  allowResearchTraining: boolean;
  days: { day: DailyData; availableAt: string }[];
}

function instant(value: string): number {
  if (!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) throw new Error('Timestamp with timezone required');
  return Date.parse(value);
}

export function buildResearchSnapshot(input: ResearchInput) {
  if (input.allowResearchTraining !== true) throw new Error('Separate research training consent required');
  const profile = validateProfile(input.profile);
  const cutoff = instant(input.cutoff);
  if (instant(input.profileAvailableAt) > cutoff) throw new Error('Future profile is not available at cutoff');
  const parts = new Intl.DateTimeFormat('en', { timeZone: profile.timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(cutoff));
  const part = (name: string) => parts.find(p => p.type === name)!.value;
  const localDate = `${part('year')}-${part('month')}-${part('day')}`;
  if (!input.days.length || input.days.length > 64) throw new Error('Expected 1–64 complete local days');
  const days = input.days.map(record => {
    if (instant(record.availableAt) > cutoff) throw new Error('Future record unavailable at cutoff');
    const day = validateDay(record.day);
    if (day.date >= localDate) throw new Error('Only completed local days may enter history');
    return day;
  }).sort((a, b) => a.date.localeCompare(b.date));
  if (new Set(days.map(day => day.date)).size !== days.length) throw new Error('Duplicate day');
  if (new Set(days.map(day => `${day.source}/${day.deviceId}`)).size !== 1) throw new Error('Keep device and source domains separate');
  // Fixed unit conversions, not population statistics fitted across subjects.
  const divisors = [100, 100, 24, 10000, 24, 1];
  const raw = days.map(d => [d.restingHeartRate, d.hrvMs, d.sleepHours, d.steps, d.wearHours, d.signalQuality]);
  if (!raw.some(row => row.slice(0, 4).some(value => value !== null))) throw new Error('No physiological or activity measurements');
  return {
    schema: 'harness-daily-v1', dataKind: days[0].source === 'synthetic' ? 'synthetic' : 'real',
    featureNames: ['restingHeartRate/100', 'hrvMs/100', 'sleepHours/24', 'steps/10000', 'wearHours/24', 'signalQuality'],
    contextNames: ['age18_39', 'age40_64', 'age65_plus'],
    values: raw.map(row => row.map((value, i) => value === null ? 0 : value / divisors[i])),
    observed: raw.map(row => row.map(value => value !== null)),
    elapsed: days.map(d => [(Date.parse(d.date) - Date.parse(days[0].date)) / 86400000 / 64]),
    context: ['18-39', '40-64', '65+'].map(age => Number(profile.ageBand === age)),
    contextObserved: [true, true, true],
    scope: 'offline-research-only',
    // Free-text conditions, medications, goals and symptoms remain in the Harness.
    // A later, versioned annotation workflow is required before they become features.
    proteinMeasurements: null,
    label: null,
  };
}
