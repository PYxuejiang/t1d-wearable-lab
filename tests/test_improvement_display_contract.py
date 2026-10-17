import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).parents[1]


def test_improvement_display_uses_all_original_acceptance_records():
    public=json.loads((ROOT/'showcase/public/demo/improvement_data.json').read_text(encoding='utf-8'))
    for stage,record in public['stages'].items():
        assert record==json.loads((ROOT/'docs/acceptance'/f'{stage}.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(json.dumps(public['stages'],sort_keys=True,separators=(',',':')).encode()).hexdigest()[:12]
    assert public['run_id']=='improve-'+digest
    personal=public['stages']['COHORT_SW_PERSONAL1']
    assert personal['subject_count']==11
    assert personal['summary']['wearable_time']['ap']['n']==8
    assert personal['effect_status']=='inconclusive'
    assert 'row' in personal['scope'].lower()
    # A positive AP contrast cannot turn the failed event alarm into a pass.
    assert public['stages']['V2_1']['effect_status']=='failed'
    assert public['stages']['V2_2']['effect_status']=='failed'


def test_context_card_and_ledger_preserve_unfavorable_and_calibration_baselines():
    record=json.loads((ROOT/'docs/acceptance/CONTEXT_V1_1.json').read_text(encoding='utf-8'))
    public=json.loads((ROOT/'showcase/public/demo/improvement_data.json').read_text(encoding='utf-8'))
    assert public['stages']['CONTEXT_V1_1']==record
    assert record['groups_verified']==132 and record['subject_count']==11
    assert record['summary']['combined']['raw']['ap']['mean'] < record['summary']['wearable_time']['raw']['ap']['mean']
    assert record['summary']['wearable_time']['training_prior']['brier']['mean'] < record['summary']['wearable_time']['calibrated']['brier']['mean']
    assert record['effect_status']=='inconclusive'
    manifest=json.loads((ROOT/'showcase/public/cards/context-manifest.json').read_text())
    assert manifest['acceptance_sha256']==hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert manifest['png_sha256']==hashlib.sha256((ROOT/'showcase/public/cards/context-calibration.png').read_bytes()).hexdigest()


def test_capture_evidence_stays_separate_from_glucose_efficacy():
    record=json.loads((ROOT/'docs/acceptance/ECG_CAPTURE_PILOT1.json').read_text())
    public=json.loads((ROOT/'showcase/public/demo/improvement_data.json').read_text(encoding='utf-8'))
    assert public['stages']['ECG_CAPTURE_PILOT1']==record
    assert record['independently_verified_metric_groups']==48
    assert 'effect_status' not in record  # Signal capture does not pass the glucose target.
    assert len(record['source_audit'])==4
    assert all(r['valid_hr_windows']==6 for r in record['record_summary'])
    assert all(r['pilot_gate_passed'] for r in record['summary'].values())
    manifest=json.loads((ROOT/'showcase/public/cards/ecg-manifest.json').read_text())
    assert manifest['acceptance_sha256']==hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert manifest['png_sha256']==hashlib.sha256((ROOT/'showcase/public/cards/ecg-capture.png').read_bytes()).hexdigest()


def test_v3_coverage_gain_does_not_pass_failed_detection_or_hide_secondary_budget():
    record=json.loads((ROOT/'docs/acceptance/V3_MECHANISM1.json').read_text())
    public=json.loads((ROOT/'showcase/public/demo/improvement_data.json').read_text(encoding='utf-8'))
    assert public['stages']['V3_MECHANISM1']==record and record['groups_verified']==336
    primary=record['primary']
    assert primary['coverage']>.8 and record['effect_status']=='failed' and primary['matched_events']==0
    assert primary['reference_events']==30 and primary['events_with_input_opportunity']==27
    diagnostics=[r for r in record['failure_diagnostics'] if r['arm']=='pooled_fallback' and r['budget']==1]
    assert sum(sum(r['miss_reasons'].values()) for r in diagnostics)==30
    assert sum(r['unmatched_alert_timing']['within30min_before_onset'] for r in diagnostics)==primary['unmatched_alarms']==1
    secondary=record['results']['pooled_fallback/pooled_validation/b2/end_to_end']
    assert secondary['matched_events']==2 and secondary['false_alerts_per_person_day']>1
    assert 'ap' not in record['paired_differences']['pooled_residual__to__pooled_fallback/end_to_end']
    manifest=json.loads((ROOT/'showcase/public/cards/mechanism-manifest.json').read_text())
    assert manifest['acceptance_sha256']==hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert manifest['png_sha256']==hashlib.sha256((ROOT/'showcase/public/cards/mechanism-v3.png').read_bytes()).hexdigest()
