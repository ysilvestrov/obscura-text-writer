import json
import pytest
from storygen.domain import ContentRating as R, RevisionConflict, Scene, SceneCreate, Story, StoryCreate
from storygen.rating.levels import age_label, from_wire, higher_axes, is_lower, to_wire
from storygen.storage.repository import Repository

pytestmark = pytest.mark.unrated_stories  # first-set semantics need stories created unrated

def make(tmp_path, n=2):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Рейтинг'))
    scenes = []
    for i in range(n):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Сцена {i}'))
        draft = repo.save_version(story.id, scene.id, 'draft', 'A', [])
        scene = repo.set_head(scene.id, 'draft', draft.id, scene.revision)
        dep = repo.save_version(story.id, scene.id, 'edited', 'B', [draft.id])
        scenes.append((scene, dep))
    return repo, repo.get_story(story.id), scenes


def clean(repo, scene, dep):
    s = repo.get_scene(scene.id)
    return not s.needs_review and not repo.get_version(dep.id).stale


def test_old_payload_reads_unrated(tmp_path):
    repo, story, [(scene, _), _] = make(tmp_path)
    with repo.db.connection() as db:
        for table, id in (('stories', story.id), ('scenes', scene.id)):
            raw = json.loads(db.execute(f'SELECT payload FROM {table} WHERE id=?', (id,)).fetchone()[0])
            for k in ('content_rating', 'initial_content_rating'):
                raw.pop(k, None)
            db.execute(f'UPDATE {table} SET payload=? WHERE id=?', (json.dumps(raw), id))
    story, scene = repo.get_story(story.id), repo.get_scene(scene.id)
    assert story.content_rating is None and story.initial_content_rating is None
    assert scene.content_rating is None


def test_first_story_rating_sets_initial_once(tmp_path):
    repo, story, _ = make(tmp_path)
    s = repo.update_story_rating(story.id, R(sexual=1, violence=0, themes=0), story.revision)
    assert s.initial_content_rating == R(sexual=1, violence=0, themes=0)
    s = repo.update_story_rating(story.id, R(sexual=2, violence=2, themes=2), s.revision)
    assert s.content_rating == R(sexual=2, violence=2, themes=2)
    assert s.initial_content_rating == R(sexual=1, violence=0, themes=0)
    assert repo.get_story(story.id) == s


def test_same_rating_is_noop(tmp_path):
    repo, story, _ = make(tmp_path)
    s = repo.update_story_rating(story.id, R(sexual=1, violence=1, themes=1), story.revision)
    assert repo.update_story_rating(story.id, R(sexual=1, violence=1, themes=1), s.revision).revision == s.revision


def test_revision_conflict_and_reset_forbidden(tmp_path):
    repo, story, _ = make(tmp_path)
    with pytest.raises(RevisionConflict):
        repo.update_story_rating(story.id, R(sexual=0, violence=0, themes=0), story.revision + 5)
    with pytest.raises(ValueError, match='не можна скинути'):
        repo.update_story_rating(story.id, None, story.revision)


def test_story_lowering_invalidates_only_inheriting_scenes(tmp_path):
    repo, story, [(a, adep), (b, bdep)] = make(tmp_path)
    s = repo.update_story_rating(story.id, R(sexual=2, violence=2, themes=2), story.revision)
    b = repo.update_scene_rating(b.id, R(sexual=2, violence=2, themes=2), b.revision)
    assert clean(repo, a, adep) and clean(repo, b, bdep)
    repo.update_story_rating(story.id, R(sexual=0, violence=2, themes=2), repo.get_story(story.id).revision)
    assert repo.get_version(adep.id).stale and repo.get_scene(a.id).needs_review
    assert clean(repo, b, bdep)


def test_raising_and_first_set_invalidate_nothing(tmp_path):
    repo, story, [(a, adep), (b, bdep)] = make(tmp_path)
    s = repo.update_story_rating(story.id, R(sexual=1, violence=1, themes=1), story.revision)
    assert clean(repo, a, adep) and clean(repo, b, bdep)
    repo.update_story_rating(story.id, R(sexual=2, violence=1, themes=1), s.revision)
    assert clean(repo, a, adep) and clean(repo, b, bdep)


def test_scene_override_and_reset(tmp_path):
    repo, story, [(a, adep), _] = make(tmp_path)
    repo.update_story_rating(story.id, R(sexual=1, violence=1, themes=1), story.revision)
    a = repo.update_scene_rating(a.id, R(sexual=2, violence=2, themes=2), repo.get_scene(a.id).revision)
    assert clean(repo, a, adep)  # raised
    a = repo.update_scene_rating(a.id, R(sexual=0, violence=0, themes=0), a.revision)
    assert repo.get_version(adep.id).stale and repo.get_scene(a.id).needs_review
    # reset to story rating (1,1,1) is a raise relative to (0,0,0): no new invalidation
    with repo.db.connection() as db:
        v = repo.get_version(adep.id); v.stale = False
        db.execute('UPDATE versions SET payload=? WHERE id=?', (v.model_dump_json(), v.id))
        sc = repo.get_scene(a.id); sc.needs_review = False; repo._save_scene(db, sc)
    a = repo.update_scene_rating(a.id, None, repo.get_scene(a.id).revision)
    assert a.content_rating is None and clean(repo, a, adep)


def test_levels_helpers():
    assert is_lower(R(sexual=1, violence=2, themes=2), R(sexual=2, violence=0, themes=0))
    assert not is_lower(R(sexual=2, violence=2, themes=2), R(sexual=1, violence=1, themes=1))
    assert not is_lower(None, R(sexual=0, violence=0, themes=0))
    r = R(sexual=1, violence=0, themes=2)
    assert to_wire(r) == ['1', '0', '2'] and from_wire(to_wire(r)) == r
    assert to_wire(None) is None and from_wire(None) is None
    assert higher_axes(R(sexual=2, violence=0, themes=1), R(sexual=1, violence=0, themes=1)) == ['sexual']


def test_age_label_takes_highest_level_over_story_and_scenes():
    story = Story(id='s1', title='T', content_rating=R(sexual=0, violence=0, themes=0))
    assert age_label(Story(id='s1', title='T'), []) is None
    assert age_label(story, []) == '0+'
    assert age_label(story, [Scene(id='c1', story_id=story.id, title='a', position=0, content_rating=R(sexual=0, violence=1, themes=0))]) == '16+'
    assert age_label(story.model_copy(update={'content_rating': R(sexual=0, violence=0, themes=2)}), [Scene(id='c1', story_id=story.id, title='a', position=0)]) == '18+'
