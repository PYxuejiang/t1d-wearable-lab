"""Check public scientific artifacts agree without downloading patient data."""
import hashlib
import json
import struct
from pathlib import Path

ROOT=Path(__file__).parents[1]


def test_public_results_are_identical_to_verified_acceptance():
    artifact=json.loads((ROOT/'showcase/public/demo/project_data.json').read_text(encoding='utf-8'))
    for name,stage in [('regression','S2a'),('incident','S2b'),('detection','S3')]:
        record=json.loads((ROOT/'docs/acceptance'/f'{stage}.json').read_text(encoding='utf-8'))
        actual=artifact[name]['results'] if name=='regression' else artifact[name]
        assert actual==record['results']
    fingerprint=hashlib.sha256((ROOT/'configs/protocol.yaml').read_text(encoding='utf-8').encode())
    for stage in ['S2a','S2b','S3','S4']:
        fingerprint.update(json.dumps(json.loads((ROOT/'docs/acceptance'/f'{stage}.json').read_text(encoding='utf-8')),sort_keys=True,separators=(',',':')).encode())
    assert artifact['run_id']=='t1d-'+fingerprint.hexdigest()[:12]
    # Shared artifacts must not embed raw readings or participant timelines.
    def inspect(value):
        if isinstance(value,dict):
            assert not {'decision_time','alarm_time','observed','frames','EcgWaveform'}.intersection(value)
            for child in value.values():inspect(child)
        elif isinstance(value,list):
            for child in value:inspect(child)
    inspect(artifact)


def test_exported_cards_match_manifest_and_show_run_id():
    folder=ROOT/'showcase/public/cards'
    manifest=json.loads((folder/'manifest.json').read_text())
    assert len(manifest['cards'])==10
    data=json.loads((ROOT/'showcase/public/demo/project_data.json').read_text(encoding='utf-8'))
    assert manifest['source_sha256']==hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for name,digest in manifest['cards'].items():
        content=(folder/name).read_text(encoding='utf-8').encode() if name.endswith('.svg') else (folder/name).read_bytes()
        assert hashlib.sha256(content).hexdigest()==digest
        if name.endswith('.png'):
            assert content[:8]==b'\x89PNG\r\n\x1a\n'
            assert struct.unpack('>II',content[16:24])==(1800,1200)
        else:assert manifest['run_id'] in content.decode('utf-8')
