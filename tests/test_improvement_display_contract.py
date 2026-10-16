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
