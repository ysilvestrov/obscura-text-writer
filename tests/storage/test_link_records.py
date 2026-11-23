import json
import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.storage.integrity import check_integrity
from storygen.storage.link_records import LinkVerdict, write_verdict, new_verdict_id



def one_scene(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Зв’язки'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='Початок'))
    return repo, story, scene


def verdict(story_id, scene_id, link='brief', fingerprint='a' * 64, **changes):
    values = dict(id=new_verdict_id(), story_id=story_id, scene_id=scene_id, link=link,
                  inputs={'plan': None, 'p0': None, 'brief': 'b1'}, fingerprint=fingerprint, source='author',
                  outcome='valid', confidence=None, discrepancies=[], reason=None, attempt_id=None, run_id=None,
                  created_at='2026-11-23T00:00:00+00:00')
    values.update(changes)
    return LinkVerdict(**values)


def store(repo, record):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        write_verdict(db, record)


@pytest.mark.req('VALID-LINKS')
def test_verdict_round_trip_through_view(tmp_path):
    repo, story, scene = one_scene(tmp_path)
    record = verdict(story.id, scene.id)
    store(repo, record)
    view = repo.context_view(story.id)
    assert view.link_verdicts[(scene.id, 'brief', 'a' * 64)] == record


@pytest.mark.req('VALID-LINKS')
def test_view_opened_before_the_write_does_not_hide_a_later_verdict(tmp_path):
    repo, story, scene = one_scene(tmp_path)
    assert repo.context_view(story.id).link_verdicts == {}
    record = verdict(story.id, scene.id)
    store(repo, record)
    assert repo.context_view(story.id).link_verdicts[(scene.id, 'brief', 'a' * 64)] == record


@pytest.mark.req('VALID-LINKS')
def test_latest_verdict_wins_per_fingerprint(tmp_path):
    repo, story, scene = one_scene(tmp_path)
    first = verdict(story.id, scene.id, outcome='discrepancy', source='auditor', confidence=40,
                    discrepancies=[{'text': 'Інше ім’я', 'quote': None}])
    second = verdict(story.id, scene.id)
    other = verdict(story.id, scene.id, fingerprint='b' * 64)
    for record in (first, second, other):
        store(repo, record)
    verdicts = repo.context_view(story.id).link_verdicts
    assert verdicts[(scene.id, 'brief', 'a' * 64)] == second
    assert verdicts[(scene.id, 'brief', 'b' * 64)] == other


@pytest.mark.req('VALID-LINKS')
def test_verdict_rejects_bad_values(tmp_path):
    with pytest.raises(ValueError):
        verdict('s', 'c', fingerprint='short')
    with pytest.raises(ValueError):
        verdict('s', 'c', confidence=101)
    with pytest.raises(ValueError):
        verdict('s', 'c', discrepancies=[{'text': 'x', 'quote': None}] * 21)


@pytest.mark.req('VALID-LINKS')
def test_fsck_reports_foreign_scene_verdict(tmp_path):
    repo, story, scene = one_scene(tmp_path)
    other = repo.create_story(StoryCreate(title='Інший'))
    foreign = repo.create_scene(other.id, SceneCreate(title='Чужа', beats='x'))
    record = verdict(story.id, scene.id)
    store(repo, record)
    assert not any(i.code == 'invalid_link_verdict' for i in check_integrity(repo.root).issues)
    raw = record.model_dump(); raw['scene_id'] = foreign.id
    with repo.db.connection() as db:
        db.execute('UPDATE app_settings SET payload=? WHERE key=?',
                   (json.dumps(raw), 'link_verdict:' + story.id + ':' + record.id))
    assert any(i.code == 'invalid_link_verdict' for i in check_integrity(repo.root).issues)


@pytest.mark.req('VALID-LINKS')
def test_view_refuses_verdict_under_a_foreign_key(tmp_path):
    repo, story, scene = one_scene(tmp_path)
    record = verdict(story.id, scene.id)
    with repo.db.connection() as db:
        db.execute('INSERT INTO app_settings VALUES(?,?)', ('link_verdict:' + story.id + ':other', record.model_dump_json()))
    with pytest.raises(ValueError):
        repo.context_view(story.id)


@pytest.mark.req('VALID-LINKS')
def test_fsck_reports_foreign_equivalence(tmp_path):
    from storygen.storage.link_records import ProseEquivalence, write_equivalence
    repo, story, scene = one_scene(tmp_path)
    other = repo.create_story(StoryCreate(title='Інший'))
    foreign = repo.create_scene(other.id, SceneCreate(title='Чужа', beats='x'))
    first = repo.save_version(story.id, scene.id, 'manual', 'Перша.', [])
    second = repo.save_version(story.id, scene.id, 'manual', 'Друга.', [])
    record = ProseEquivalence(id=new_verdict_id(), story_id=story.id, scene_id=scene.id, old_prose_id=first.id,
                              new_prose_id=second.id, verdict_id='v', created_at='2026-11-23T00:00:00+00:00')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        write_equivalence(db, record)
    assert repo.context_view(story.id).prose_equivalences == [record]
    assert not any(i.code == 'invalid_prose_equivalence' for i in check_integrity(repo.root).issues)
    raw = record.model_dump(); raw['scene_id'] = foreign.id
    with repo.db.connection() as db:
        db.execute('UPDATE app_settings SET payload=? WHERE key=?',
                   (json.dumps(raw), 'prose_equivalence:' + story.id + ':' + record.id))
    assert any(i.code == 'invalid_prose_equivalence' for i in check_integrity(repo.root).issues)
    with pytest.raises(ValueError):
        repo.context_view(story.id)
