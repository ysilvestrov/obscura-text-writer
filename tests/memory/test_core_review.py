import json

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.memory.core import SLOTS
from storygen.memory.core_review import captured_wire, core_review, prefix_fragments, prefix_scenes
from storygen.memory.journal import MemoryJournal, _add_event, _change_event, _extend
from storygen.memory.service import save_scene_memory
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from tests.memory.wire_helpers import core_unchanged, threads_open, v4_response
from tests.storage.test_memory_core_selectors import cards

PROSE1 = 'Анна в халаті.\nУ кишені ключ.\nХто стукав у двері?'
PROSE2 = 'Анна вдягла пальто.\nСтукав сусід.'


def role():
    return RoleSettings(provider=ProviderSettings(model='fake'), memory_mode='evidence_delta', context_tokens=32768)


def two_scenes(tmp_path):
    """Scene 1 has a memory with Anna's clothing and carried slots and one open thread; scene 2 has prose only."""
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ядро'))
    repo.publish_story_material(story.id, 'characters_version_id', cards(repo, story.id, 'A'), repo.get_story(story.id).revision)
    s1, s2 = (repo.create_scene(story.id, SceneCreate(title=f'С{i}', beats='Анна.', character_ids=['A'])) for i in (1, 2))
    p1 = repo.save_version(story.id, s1.id, 'manual', PROSE1, [])
    repo.set_head(s1.id, 'prose', p1.id, repo.get_scene(s1.id).revision)
    cloth = _add_event('character_states', 'Халат', p1.id, 'Анна в халаті.', 0, ['A'], slot='clothing')
    key = _add_event('character_states', 'Ключ', p1.id, 'У кишені ключ.', 0, ['A'], slot='carried')
    thread = _add_event('open_threads', 'Хто стукав?', p1.id, 'Хто стукав у двері?', 0)
    journal = MemoryJournal(schema_version=3, source_prose_ids=[p1.id], events=[cloth, key, thread])
    memory = repo.save_version(story.id, s1.id, 'memory', journal.model_dump_json(), [p1.id])
    repo.set_head(s1.id, 'memory', memory.id, repo.get_scene(s1.id).revision)
    p2 = repo.save_version(story.id, s2.id, 'manual', PROSE2, [])
    repo.set_head(s2.id, 'prose', p2.id, repo.get_scene(s2.id).revision)
    return repo, story, repo.get_scene(s1.id), repo.get_scene(s2.id), journal, {'cloth': cloth, 'key': key, 'thread': thread}


def run_memory(repo, scene, raw):
    import threading
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent

    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    context = build_context(repo, scene.id, 'memory', role())
    attempt = execute_stage(repo, scene.id, 'memory', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed', attempt.error
    return attempt


def v4_scene(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    core = core_unchanged('A')
    core['A']['clothing'] = {'status': 'changed', 'text': 'Пальто', 'evidence_ids': ['f000001'], 'reason': ''}
    core['A']['carried'] = {'status': 'unknown', 'text': '', 'evidence_ids': [], 'reason': 'Ключ більше не згадано'}
    threads = {claims['thread'].claim_id: {'status': 'closed', 'resolution': 'Стукав сусід', 'evidence_ids': ['f000002']}}
    attempt = run_memory(repo, s2, v4_response(core, threads))
    return repo, story, repo.get_scene(s2.id), claims, attempt


def by_slot(review):
    return {(row['character_id'], row['slot']): row for row in review['slots']}


@pytest.mark.req('MEMORY-CONFIRM')
def test_core_review_changed_unknown_closed(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    review = core_review(repo, scene.id)
    head = scene.heads['memory']
    assert attempt.result_version_id == head
    assert set(review) == {'scene_id', 'memory_version_id', 'revision', 'has_wire', 'day_change', 'confirmation', 'slots', 'threads'}
    assert review['scene_id'] == scene.id and review['memory_version_id'] == head and review['revision'] == scene.revision
    assert review['has_wire'] is True and review['day_change'] is False and review['confirmation'] is None
    assert [(r['character_id'], r['slot']) for r in review['slots']] == [('A', s.name) for s in SLOTS]
    rows = by_slot(review)
    assert rows[('A', 'clothing')] == {'character_id': 'A', 'name': 'Анна', 'slot': 'clothing', 'label': 'одяг',
        'before': 'Халат', 'after': 'Пальто', 'status': 'changed', 'reason': None, 'reader_unknown': False}
    carried = rows[('A', 'carried')]
    assert (carried['before'], carried['after'], carried['status'], carried['reason']) == ('Ключ', None, 'unknown', 'Ключ більше не згадано')
    assert rows[('A', 'location')]['status'] == 'unchanged' and rows[('A', 'location')]['before'] is None
    assert review['threads'] == [{'claim_id': claims['thread'].claim_id, 'text': 'Хто стукав?', 'status': 'closed', 'resolution': 'Стукав сусід'}]
    wire, bounds = captured_wire(repo, head)
    assert wire['schema_version'] == 4 and bounds['tracked'] == {'A': [s.name for s in SLOTS]}
    # Confirmation is reported once set; English labels on request.
    repo.confirm_memory(scene.id, head, scene.revision)
    review = core_review(repo, scene.id, locale='en')
    assert review['confirmation']['by'] == 'author' and review['confirmation']['confirmed_at']
    assert by_slot(review)[('A', 'clothing')]['label'] == 'clothing'


def test_captured_wire_none_on_unreadable_attempt(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    repo.files.resolve(attempt.partial_path).write_text('{не json', encoding='utf-8')
    assert captured_wire(repo, scene.heads['memory']) is None
    assert core_review(repo, scene.id)['has_wire'] is False
    assert captured_wire(repo, 'missing') is None


def test_core_review_first_scene_and_legacy_journal(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Старе'))
    scene = repo.create_scene(story.id, SceneCreate(title='С1', character_ids=['A']))
    prose = repo.save_version(story.id, scene.id, 'manual', PROSE1, [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    legacy = {'source_prose_ids': [prose.id], 'facts': [], 'character_states': [], 'timeline': [],
              'open_threads': [{'text': 'Хто стукав?', 'source_version_id': prose.id, 'quote': 'Хто стукав у двері?'}]}
    memory = repo.save_version(story.id, scene.id, 'memory', json.dumps(legacy, ensure_ascii=False), [prose.id])
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    review = core_review(repo, scene.id)
    assert review['slots'] == [] and review['has_wire'] is False
    assert [(t['text'], t['status'], t['resolution']) for t in review['threads']] == [('Хто стукав?', 'open', None)]
    # A scene without memory yet answers an empty review instead of failing.
    empty = repo.create_scene(story.id, SceneCreate(title='С2', character_ids=['A']))
    review = core_review(repo, empty.id)
    assert review['memory_version_id'] is None and review['slots'] == [] and review['threads'] == []


def manual_scene(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    p2 = s2.heads['prose']
    events = [
        _change_event('update', claims['cloth'].claim_id, 'Пальто', 'character_states', ['A'], p2, 'Анна вдягла пальто.', slot='clothing'),
        _change_event('retire', claims['key'].claim_id, 'Ключ', 'character_states', ['A'], p2, 'Стукав сусід.', slot='carried'),
        _add_event('character_states', 'Кухня', p2, None, 0, ['A'], slot='location', source_kind='author'),
        _add_event('open_threads', 'Чого хоче сусід?', p2, 'Стукав сусід.', 0),
    ]
    save_scene_memory(repo, s2.id, _extend(journal, p2, events).model_dump_json(), s2.revision)
    return repo, story, repo.get_scene(s2.id), claims


def test_core_review_without_wire(tmp_path):
    repo, story, scene, claims = manual_scene(tmp_path)
    review = core_review(repo, scene.id)
    assert review['has_wire'] is False and captured_wire(repo, scene.heads['memory']) is None
    rows = by_slot(review)
    assert (rows[('A', 'clothing')]['status'], rows[('A', 'clothing')]['after']) == ('changed', 'Пальто')
    assert (rows[('A', 'carried')]['status'], rows[('A', 'carried')]['after']) == ('unknown', None)
    assert (rows[('A', 'location')]['status'], rows[('A', 'location')]['after']) == ('author', 'Кухня')
    assert (rows[('A', 'body')]['status'], rows[('A', 'body')]['after']) == ('unchanged', None)
    assert all(row['reason'] is None for row in review['slots'])
    assert [(t['text'], t['status']) for t in review['threads']] == [('Хто стукав?', 'open'), ('Чого хоче сусід?', 'open')]


def test_reader_unknown_flag(tmp_path):
    repo, story, scene, claims = manual_scene(tmp_path)
    rows = by_slot(core_review(repo, scene.id))
    assert rows[('A', 'location')]['reader_unknown'] is True
    assert rows[('A', 'clothing')]['reader_unknown'] is False and rows[('A', 'carried')]['reader_unknown'] is False


def test_prefix_fragments_only_up_to_scene(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    assert [s['scene_id'] for s in prefix_scenes(repo, s1.id)] == [s1.id]
    assert [(s['scene_id'], s['scene_number'], s['version_id']) for s in prefix_scenes(repo, s2.id)] == [
        (s1.id, 1, s1.heads['prose']), (s2.id, 2, s2.heads['prose'])]
    assert prefix_fragments(repo, s1.id, 'пальто') == []
    found = prefix_fragments(repo, s2.id, 'ПАЛЬТО')
    assert found == [{'version_id': s2.heads['prose'], 'scene_id': s2.id, 'scene_number': 2, 'fragment_id': 'f000001', 'text': 'Анна вдягла пальто.'}]
    assert [f['text'] for f in prefix_fragments(repo, s2.id, 'анна')] == ['Анна в халаті.', 'Анна вдягла пальто.']
    with pytest.raises(ValueError):
        prefix_fragments(repo, s1.id, source_scene_id=s2.id)
    with pytest.raises(ValueError):
        prefix_fragments(repo, s1.id)


def test_prefix_fragments_by_scene(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    got = prefix_fragments(repo, s2.id, source_scene_id=s1.id)
    assert [(f['fragment_id'], f['text']) for f in got] == [
        ('f000001', 'Анна в халаті.'), ('f000002', 'У кишені ключ.'), ('f000003', 'Хто стукав у двері?')]
    assert [f['text'] for f in prefix_fragments(repo, s2.id, 'ключ', source_scene_id=s1.id)] == ['У кишені ключ.']
    assert len(prefix_fragments(repo, s2.id, source_scene_id=s1.id, limit=2)) == 2


@pytest.mark.req('MEMORY-CONFIRM')
def test_changed_to_the_same_value_shows_as_unchanged(tmp_path):
    # The model may re-confirm a slot with a fresh quote and mark it 'changed'; the panel must not show «було: X / стало: X» as a change.
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    core = core_unchanged('A')
    core['A']['clothing'] = {'status': 'changed', 'text': 'халат ', 'evidence_ids': ['f000001'], 'reason': ''}
    run_memory(repo, s2, v4_response(core, {claims['thread'].claim_id: {'status': 'open', 'resolution': '', 'evidence_ids': []}}))
    row = by_slot(core_review(repo, s2.id))[('A', 'clothing')]
    assert (row['before'], row['status']) == ('Халат', 'unchanged')


def test_captured_wire_splits_joined_evidence(tmp_path):
    # The saved answer keeps the model's joined string; the review rebuilds from the same reading as the parser.
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    core = core_unchanged('A')
    core['A']['clothing'] = {'status': 'changed', 'text': 'Пальто', 'evidence_ids': ['f000001,f000002'], 'reason': ''}
    run_memory(repo, s2, v4_response(core, threads_open(claims['thread'].claim_id)))
    wire, _ = captured_wire(repo, repo.get_scene(s2.id).heads['memory'])
    assert wire['core']['A']['clothing']['evidence_ids'] == ['f000001', 'f000002']
