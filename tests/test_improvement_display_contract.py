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


def test_v4_ranking_gain_keeps_failed_primary_and_source_clock_limit():
    record=json.loads((ROOT/'docs/acceptance/V4_LATE_FUSION1.json').read_text())
    source=json.loads((ROOT/'docs/acceptance/SOURCE_TIME1.json').read_text())
    public=json.loads((ROOT/'showcase/public/demo/improvement_data.json').read_text(encoding='utf-8'))
    assert public['stages']['V4_LATE_FUSION1']==record and public['stages']['SOURCE_TIME1']==source
    assert record['groups_verified']==392 and len(record['results'])==56
    assert record['primary_key']=='late_stack/run/b1/end_to_end'
    assert record['primary']['matched_events']==0 and record['effect_status']=='failed'
    assert all(r['reference_events']==30 for r in record['results'].values())
    assert record['paired_differences']['late_stack/point']['ap']['95_interval'][0]>0
    assert record['results']['ppg/point/b1/end_to_end']['matched_events']==3
    assert record['results']['ppg/point/b1/end_to_end']['coverage']<.8
    assert source['feature_label_mismatches']==0 and 'unresolved' in source['status']
    assert source['feature_anchors_checked']==34218 and len(source['subjects'])==10
    assert all(not r['probe_integrity']['full_archive_verified'] for r in source['subjects'])
    manifest=json.loads((ROOT/'showcase/public/cards/fusion-manifest.json').read_text())
    assert manifest['acceptance_sha256']==hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert manifest['png_sha256']==hashlib.sha256((ROOT/'showcase/public/cards/late-fusion-v4.png').read_bytes()).hexdigest()


def test_v5_display_preserves_same_mask_controls_and_timing_denominators():
    record=json.loads((ROOT/'docs/acceptance/V5_PPG_MORPH1.json').read_text(encoding='utf-8'))
    public=json.loads((ROOT/'showcase/public/demo/improvement_data.json').read_text(encoding='utf-8'))
    assert public['stages']['V5_PPG_MORPH1']==record
    assert record['groups_verified']==42 and record['inner_candidates_verified']==9
    assert record['primary_key']=='morphology/b1' and record['coarse_v4_maximum_score_difference']<1e-9
    assert len(record['results'])==6
    for r in record['results'].values():
        assert r['reference_events']==30 and r['events_hit_within15min']<=r['matched_events']
        assert abs(r['coverage']-record['results']['coarse/b1']['coverage'])<1e-12
        assert r['micro_event_recall']==r['matched_events']/30
    # A fixed mask below80% cannot pass the original combined alarm target.
    assert record['primary']['coverage']<.8 and record['effect_status']=='failed'
    manifest=json.loads((ROOT/'showcase/public/cards/ppg-morphology-manifest.json').read_text())
    assert manifest['acceptance_sha256']==hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert manifest['png_sha256']==hashlib.sha256((ROOT/'showcase/public/cards/ppg-morphology-v5.png').read_bytes()).hexdigest()


def test_ppg_capture_keeps_reference_denominators_and_conditional_interval_coverage():
    r=json.loads((ROOT/'docs/acceptance/PPG_CAPTURE1.json').read_text(encoding='utf-8'))
    assert r['records_verified']==29 and r['metric_groups_verified']==464
    assert r['clinical_effect_status']=='not_evaluated'
    assert r['development_candidates_verified']==5
    assert r['paired_differences']['calibrated/f1']['95_interval'][0]<0<r['paired_differences']['calibrated/f1']['95_interval'][1]
    primary=r['results']['heldout/calibrated/dual_average/raw']
    baseline=r['results']['heldout/calibrated/v5_peaks/raw']
    assert primary['records']==baseline['records']==19
    assert primary['reference_beats']==baseline['reference_beats']
    assert 'metrics_by_record' not in r
    assert 'development_lags' not in r['selection']
    assert all('records' not in c for c in r['selection']['candidates'])
    import re
    assert not re.search(r'\"S\d+/(?:sitting|walking)\"', json.dumps(r))
    for row in r['results'].values():
        assert 0<=row['ppi_pair_coverage']<=1 and 0<=row['hr_output_fraction']<=1
        assert row['covered_reference_time_fraction']<=row['accepted_core_fraction']
    manifest=json.loads((ROOT/'showcase/public/cards/ppg-capture-manifest.json').read_text())
    assert manifest['acceptance_sha256']==hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert manifest['png_sha256']==hashlib.sha256((ROOT/'showcase/public/cards/ppg-capture-v1.png').read_bytes()).hexdigest()
