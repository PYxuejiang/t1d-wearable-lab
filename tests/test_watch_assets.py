"""Public, self-contained GLB integrity; no patient data needed."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_watch_assets_are_self_contained_valid_gltf_with_interactive_nodes():
    assets = ROOT / 'showcase/public/models'
    manifest = json.loads((assets / 'manifest.json').read_text())
    assert manifest['license'] == 'MIT'
    assert len(manifest['files']) == 3
    for entry in manifest['files']:
        raw = (assets / entry['file']).read_bytes()
        magic, version, length = struct.unpack_from('<III', raw)
        assert magic == 0x46546C67 and version == 2 and length == len(raw)
        assert len(raw) == entry['bytes'] < 1000000
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        size, kind = struct.unpack_from('<II', raw, 12)
        assert kind == 0x4E4F534A
        gltf = json.loads(raw[20:20+size])
        assert gltf['asset']['version'] == '2.0'
        assert all('uri' not in resource for resource in gltf.get('buffers', []) + gltf.get('images', []))
        assert {'Case', 'Bezel', 'Display', 'SensorHousing', 'MotionSensor'} <= {n.get('name') for n in gltf['nodes']}
        assert {'OpticalSensor', 'MotionChip', 'CaseFinish'} <= {m.get('name') for m in gltf['materials']}
        triangles = sum(gltf['accessors'][p.get('indices', p['attributes']['POSITION'])]['count'] // 3 for n in gltf['nodes'] if 'mesh' in n for p in gltf['meshes'][n['mesh']]['primitives'])
        assert triangles == entry['triangles'] < 15000
