import json

from storygen.memory.journal import MemoryJournal, MemoryOperation, MemoryOperations, apply_operations, replay_memory
from storygen.memory.wire_v3 import MemoryWireV3, memory_wire_v3_schema, schema_bounds
from tests.memory.wire_helpers import v3_response

BOUNDS = {'fragment_ids': ['f000001', 'f000002'],
    'mutable': {'character_states': ['mc_s'], 'open_threads': ['mc_t']}, 'character_ids': ['c1']}
EMPTY = {'fragment_ids': ['f000001'], 'mutable': {'character_states': [], 'open_threads': []}, 'character_ids': []}
ALLOWED = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum', 'minItems', 'maxItems'}


def nodes(node):
    """Every schema node (dict with schema keywords), skipping property names."""
    if isinstance(node, dict):
        yield node
        for key, value in node.items():
            if key == 'properties':
                for sub in value.values():
                    yield from nodes(sub)
            elif key == 'items':
                yield from nodes(value)


def test_schema_limits_and_enums():
    s = memory_wire_v3_schema(BOUNDS)
    assert s['properties']['schema_version'] == {'type': 'integer', 'enum': [3]}
    facts_add = s['properties']['facts']['properties']['add']
    assert facts_add['maxItems'] == 3
    ev = facts_add['items']['properties']['evidence_ids']
    assert ev == {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {'type': 'string', 'enum': ['f000001', 'f000002']}}
    upd = s['properties']['character_states']['properties']['update']['items']['properties']['claim_id']
    assert upd['enum'] == ['mc_s']
    assert s['properties']['open_threads']['properties']['retire']['items']['properties']['claim_id']['enum'] == ['mc_t']
    assert s['properties']['character_states']['properties']['add']['items']['properties']['character_ids']['items']['enum'] == ['c1']
    assert 'update' not in s['properties']['facts']['properties']


def test_schema_uses_only_supported_keywords():
    for bounds in (BOUNDS, EMPTY):
        for node in nodes(memory_wire_v3_schema(bounds)):
            assert set(node) <= ALLOWED, set(node) - ALLOWED


def test_schema_without_mutable_claims_has_no_empty_enum():
    s = memory_wire_v3_schema(EMPTY)
    for category in ('character_states', 'open_threads'):
        for action in ('update', 'retire'):
            node = s['properties'][category]['properties'][action]
            assert node['maxItems'] == 0
            assert 'enum' not in node['items']['properties']['claim_id']
    for node in nodes(s):
        assert node.get('enum') != []


def test_schema_without_characters():
    s = memory_wire_v3_schema(EMPTY)
    chars = s['properties']['character_states']['properties']['add']['items']['properties']['character_ids']
    assert chars['maxItems'] == 0 and 'enum' not in chars and 'enum' not in chars['items']


def test_every_object_is_closed_and_fully_required():
    for bounds in (BOUNDS, EMPTY):
        for node in nodes(memory_wire_v3_schema(bounds)):
            if 'properties' in node:
                assert node['additionalProperties'] is False
                assert node['required'] == list(node['properties'])


def _resolve(model_schema, node):
    if '$ref' in node:
        return model_schema['$defs'][node['$ref'].split('/')[-1]]
    return node


def _shape(schema, root, node):
    node = _resolve(root, node)
    if 'properties' in node:
        return {k: _shape(schema, root, v) for k, v in node['properties'].items()}
    if node.get('type') == 'array':
        return [_shape(schema, root, node['items'])]
    return None


def _shape_dynamic(node):
    if 'properties' in node:
        return {k: _shape_dynamic(v) for k, v in node['properties'].items()}
    if node.get('type') == 'array':
        return [_shape_dynamic(node['items'])]
    return None


def test_valid_answer_matches_schema_shape():
    model = MemoryWireV3.model_json_schema()
    static = _shape(model, model, model)
    dynamic = _shape_dynamic(memory_wire_v3_schema(BOUNDS))
    assert dynamic == static
    answer = v3_response(facts_add=[{'text': 'Факт', 'evidence_ids': ['f000001']}],
        character_states_add=[{'text': 'Стан', 'evidence_ids': ['f000002'], 'character_ids': ['c1']}],
        open_threads_update=[{'claim_id': 'mc_t', 'text': 'Лінія', 'evidence_ids': ['f000001']}])
    MemoryWireV3.model_validate_json(answer)
    assert set(json.loads(answer)) == set(memory_wire_v3_schema(BOUNDS)['properties'])


def test_schema_bounds_from_captured_inputs():
    previous = apply_operations(MemoryJournal(), MemoryOperations(operations=[
        MemoryOperation(action='add', category='facts', text='Факт', evidence_id='f000001'),
        MemoryOperation(action='add', category='character_states', text='Стан', character_ids=['c1'], evidence_id='f000001'),
        MemoryOperation(action='add', category='open_threads', text='Лінія', evidence_id='f000001')]), 'p1', 'Доказ.', ['c1'])
    fact, state, thread = (e.claim_id for e in previous.events)
    bounds = schema_bounds(previous, 'Один.\nДва.\nТри.', ['c1'])
    assert bounds == {'fragment_ids': ['f000001', 'f000002', 'f000003'],
        'mutable': {'character_states': [state], 'open_threads': [thread]}, 'character_ids': ['c1']}
    assert fact not in json.dumps(bounds)
    assert schema_bounds(MemoryJournal(), 'Один.', [])['mutable'] == {'character_states': [], 'open_threads': []}


def test_schema_without_fragments_forbids_elements_and_has_no_empty_enum():
    bounds = {'fragment_ids': [], 'mutable': {'character_states': ['mc_s'], 'open_threads': ['mc_t']}, 'character_ids': ['c1']}
    s = memory_wire_v3_schema(bounds)
    for node in nodes(s):
        assert node.get('enum') != []
        assert set(node) <= ALLOWED
    groups = s['properties']
    for group in groups.values():
        if group['type'] != 'object' or 'add' not in group.get('properties', {}):
            continue
        for action in ('add', 'update', 'retire'):
            if action in group['properties']:
                assert group['properties'][action]['maxItems'] == 0
                assert 'enum' not in group['properties'][action]['items']['properties']['evidence_ids']['items']
