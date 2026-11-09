from storygen.memory.core import SLOTS
from storygen.memory.wire_v4 import memory_wire_v4_schema
from tests.memory.test_wire_v3_schema import ALLOWED, nodes

BOUNDS={'fragment_ids':['f000001','f000002'],'mutable':{'character_states':['mc_s']},'threads':['mc_t1','mc_t2'],
    'character_ids':['h'],'tracked':{'h':[s.name for s in SLOTS]},'unestablished':{'h':['carried']},
    'day_change':{'h':True},'slot_registry':'core-slots-v1'}
EMPTY={'fragment_ids':[],'mutable':{'character_states':[]},'threads':['mc_t1'],'character_ids':[],
    'tracked':{'h':[s.name for s in SLOTS]},'unestablished':{'h':[]},'day_change':{},'slot_registry':'core-slots-v1'}
BARE={**EMPTY,'threads':[],'tracked':{},'unestablished':{}}


def slot(schema,name,cid='h'):return schema['properties']['core']['properties'][cid]['properties'][name]


def th_evidence(schema,claim_id):return schema['properties']['threads']['properties'][claim_id]['properties']['evidence_ids']


def fragment_enums(schema,fragments):
    return sum(1 for node in nodes(schema) if node.get('enum')==fragments)


def test_schema_size_does_not_grow_fragment_enums_with_threads():
    import json
    fragments=[f'f{i:06d}' for i in range(1,121)]
    def schema(count):
        return memory_wire_v4_schema({**BOUNDS,'fragment_ids':fragments,'threads':[f'mc_t{i}' for i in range(count)]})
    one,many=schema(1),schema(46)
    # Only the group adds/changes carry the fragment enum (as in v3): their count is fixed by the groups, not the catalog.
    assert fragment_enums(one,fragments)==fragment_enums(many,fragments)==6
    assert len(json.dumps(many))<40000


def test_schema_uses_only_allowed_keywords():
    for bounds in (BOUNDS,EMPTY,BARE):
        for node in nodes(memory_wire_v4_schema(bounds)):
            assert set(node)<=ALLOWED,set(node)-ALLOWED
            assert node.get('enum')!=[]


def test_schema_requires_every_slot_and_thread():
    s=memory_wire_v4_schema(BOUNDS)
    assert s['properties']['schema_version']=={'type':'integer','enum':[4]}
    assert s['properties']['core']['required']==['h'] and s['properties']['core']['additionalProperties'] is False
    person=s['properties']['core']['properties']['h']
    assert person['required']==[x.name for x in SLOTS] and person['additionalProperties'] is False
    assert slot(s,'body')['required']==['status','text','evidence_ids','reason']
    # Decisions take plain strings; check_v4 rejects unknown fragment IDs (evidence_unknown).
    assert slot(s,'body')['properties']['evidence_ids']=={'type':'array','minItems':0,'maxItems':3,'items':{'type':'string'}}
    assert th_evidence(s,'mc_t1')=={'type':'array','minItems':0,'maxItems':3,'items':{'type':'string'}}
    assert s['properties']['facts']['properties']['add']['items']['properties']['evidence_ids']['items']=={'type':'string','enum':['f000001','f000002']}
    th=s['properties']['threads']
    assert th['required']==['mc_t1','mc_t2'] and th['additionalProperties'] is False
    assert th['properties']['mc_t1']['required']==['status','resolution','evidence_ids']
    assert th['properties']['mc_t1']['properties']['status']['enum']==['open','closed']
    assert set(s['properties']['open_threads']['properties'])=={'add'}
    assert s['properties']['character_states']['properties']['update']['items']['properties']['claim_id']['enum']==['mc_s']
    assert memory_wire_v4_schema(BARE)['properties']['core']=={'type':'object','properties':{},'required':[],'additionalProperties':False}


def test_introduced_in_enum_only_for_unestablished():
    s=memory_wire_v4_schema(BOUNDS)
    assert slot(s,'carried')['properties']['status']['enum']==['unchanged','changed','unknown','introduced']
    assert slot(s,'clothing')['properties']['status']['enum']==['unchanged','changed','unknown']


def test_schema_without_fragments_forbids_evidence():
    s=memory_wire_v4_schema(EMPTY)
    assert slot(s,'body')['properties']['evidence_ids']['maxItems']==0
    assert 'enum' not in slot(s,'body')['properties']['evidence_ids']['items']
    assert slot(s,'body')['properties']['status']['enum']==['unchanged','unknown']
    thread=s['properties']['threads']['properties']['mc_t1']['properties']
    assert thread['evidence_ids']['maxItems']==0 and thread['status']['enum']==['open']
    for category in ('facts','character_states','open_threads','timeline'):
        assert s['properties'][category]['properties']['add']['maxItems']==0
