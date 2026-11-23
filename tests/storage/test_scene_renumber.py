"""SCENE-RENUMBER (IMPORT-NUMBER-S03): plan numbers follow reading order; a new scene goes where it is inserted."""
import pytest
from storygen.authoring.imports import SourceFile, import_sources
from storygen.authoring.trash import restore_scene, trash_scene
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.plan_renumber import renumber_plan
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository

def make(tmp_path, *beats):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Порядок'))
    for index, text in enumerate(beats):
        repo.create_scene(story.id, SceneCreate(title=f'S{index}', beats=text))
    return repo, story.id


def plans(repo, story_id):
    """(beats, plan head text or None, author number) of each active scene in reading order."""
    return [(s.beats, repo.read_text(s.heads['plan']) if s.heads.get('plan') else None, s.author_scene_number)
            for s in repo.list_scenes(story_id)]


def reorder(repo, story_id, order):
    scenes = repo.list_scenes(story_id)
    repo.reorder_scenes(story_id, [scenes[i].id for i in order], repo.get_story(story_id).revision)


@pytest.mark.req('IMPORT-NUMBER')
@pytest.mark.parametrize('before,after', [
    ('## Сцена 3: Шторм\nПлан.', '## Сцена 1: Шторм\nПлан.'),
    ('**Scene 3.** Storm\nPlan.', '**Scene 1.** Storm\nPlan.'),
    ('Сцена 3: Шторм', 'Сцена 1: Шторм'),
    ('\n  \n# Сцена 12:  Шторм\r\nПлан.\r\n', '\n  \n# Сцена 1:  Шторм\r\nПлан.\r\n'),
    ('Інтерлюдія\nСцена 3: не заголовок', 'Інтерлюдія\nСцена 3: не заголовок'),
    ('', ''),
])
def test_renumber_plan_changes_only_the_number(before, after):
    assert renumber_plan(before, 1) == after


@pytest.mark.req('IMPORT-NUMBER')
def test_reorder_renumbers_beats_and_a_new_plan_version(tmp_path):
    repo, story_id = make(tmp_path, 'Сцена 1: Ранок\nА.', 'Сцена 2: Обід\nБ.', 'Сцена 3: Вечір\nВ.')
    second = repo.list_scenes(story_id)[1]
    second = repo.update_scene_plan(second.id, 'Сцена 2: Обід\nБ переписано.', second.revision)
    old_head = second.heads['plan']
    reorder(repo, story_id, [2, 0, 1])
    assert plans(repo, story_id) == [
        ('Сцена 1: Вечір\nВ.', None, 1),
        ('Сцена 2: Ранок\nА.', None, 2),
        ('Сцена 3: Обід\nБ переписано.', 'Сцена 3: Обід\nБ переписано.', 3)]
    moved = repo.get_scene(second.id)
    assert moved.heads['plan'] != old_head and moved.head_revisions['plan'] == 2
    assert not repo.get_version(moved.heads['plan']).stale


@pytest.mark.req('IMPORT-NUMBER')
def test_replaced_plan_head_invalidates_its_dependants(tmp_path):
    repo, story_id = make(tmp_path, 'Сцена 1: Ранок', 'Сцена 2: Обід')
    second = repo.list_scenes(story_id)[1]
    second = repo.update_scene_plan(second.id, 'Сцена 2: Обід\nБ.', second.revision)
    dependant = repo.save_version(story_id, second.id, 'brief', '{}', [second.heads['plan']])
    assert not repo.get_version(dependant.id).stale
    repo.create_scene(story_id, SceneCreate(title='Вставка', position=0))
    assert repo.get_version(dependant.id).stale
    assert repo.read_text(repo.get_scene(second.id).heads['plan']) == 'Сцена 3: Обід\nБ.'


@pytest.mark.req('IMPORT-NUMBER')
def test_number_without_heading_changes_no_plan_and_invalidates_nothing(tmp_path):
    repo, story_id = make(tmp_path, 'Сцена 1: Ранок')
    scene = repo.create_scene(story_id, SceneCreate(title='Вступ', author_scene_number=2))
    scene = repo.update_scene_plan(scene.id, 'Вступ без номера.', scene.revision)
    dependant = repo.save_version(story_id, scene.id, 'brief', '{}', [scene.heads['plan']])
    repo.create_scene(story_id, SceneCreate(title='Перша', position=0, beats='Сцена 1: Перша'))
    after = repo.get_scene(scene.id)
    assert after.heads['plan'] == scene.heads['plan'] and after.author_scene_number is None
    assert not repo.get_version(dependant.id).stale


@pytest.mark.req('IMPORT-NUMBER')
def test_unnumbered_scene_keeps_its_place_and_gets_no_versions(tmp_path):
    repo, story_id = make(tmp_path, 'Пролог\nТиша.', 'Сцена 1: Ранок', 'Сцена 2: Обід')
    prologue = repo.list_scenes(story_id)[0]
    prologue = repo.update_scene_plan(prologue.id, 'Пролог\nТиша й туман.', prologue.revision)
    reorder(repo, story_id, [0, 2, 1])
    reorder(repo, story_id, [0, 2, 1])
    assert [p[0] for p in plans(repo, story_id)] == ['Пролог\nТиша й туман.', 'Сцена 2: Ранок', 'Сцена 3: Обід']
    after = repo.get_scene(prologue.id)
    assert after.heads['plan'] == prologue.heads['plan'] and after.author_scene_number is None
    assert len([v for v in repo.list_versions(story_id) if v.scene_id == prologue.id and v.kind == 'scene_plan']) == 1


@pytest.mark.req('IMPORT-NUMBER')
def test_scene_numbered_right_is_untouched(tmp_path):
    repo, story_id = make(tmp_path, 'Сцена 1: Ранок', 'Сцена 2: Обід', 'Сцена 3: Вечір')
    first = repo.list_scenes(story_id)[0]
    first = repo.update_scene_plan(first.id, 'Сцена 1: Ранок\nА.', first.revision)
    reorder(repo, story_id, [0, 2, 1])
    assert repo.get_scene(first.id).heads['plan'] == first.heads['plan']


@pytest.mark.req('IMPORT-NUMBER')
def test_insert_in_the_middle_takes_the_place_number_and_shifts_later_scenes(tmp_path):
    repo, story_id = make(tmp_path, 'Сцена 1: Ранок\nПерсонажі: \nЩо відбувається: лист.', 'Сцена 2: Обід', 'Сцена 3: Вечір')
    repo.create_scene(story_id, SceneCreate(title='Полудень', position=1), plan_template=True)
    numbers = [p[2] for p in plans(repo, story_id)]
    assert numbers == [1, 2, 3, 4]
    rows = plans(repo, story_id)
    assert rows[1][0].splitlines()[0] == '## Сцена 2: Полудень'
    assert [r[0] for r in rows[2:]] == ['Сцена 3: Обід', 'Сцена 4: Вечір']


@pytest.mark.req('IMPORT-NUMBER')
def test_insert_with_an_explicit_number_is_checked_after_the_shift(tmp_path):
    repo, story_id = make(tmp_path, 'Сцена 1: Ранок', 'Сцена 2: Обід')
    scene = repo.create_scene(story_id, SceneCreate(title='Вставка', position=1, author_scene_number=2))
    assert scene.author_scene_number == 2
    assert [p[2] for p in plans(repo, story_id)] == [1, 2, 3]
    # The scene without a plan heading keeps a number too: the shift moves it to 3, so 2 is taken again by «Ранок».
    with pytest.raises(ValueError, match='вже використано'):
        repo.create_scene(story_id, SceneCreate(title='Друга', position=0, author_scene_number=2))
    assert [p[2] for p in plans(repo, story_id)] == [1, 2, 3]


@pytest.mark.req('IMPORT-NUMBER')
def test_appending_keeps_imported_numbers(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Пропуски'))
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw='## Сцена 1: А\nа\n## Сцена 2: Б\nб\n## Сцена 5: В\nв'.encode(), kind='source_plan')])
    repo.create_scene(story.id, SceneCreate(title='Кінець'), plan_template=True)
    # Appending renumbers nothing: the new scene follows the previous number, as before.
    assert [p[2] for p in plans(repo, story.id)] == [1, 2, 5, 6]


@pytest.mark.req('IMPORT-NUMBER')
def test_trash_and_restore_renumber_the_whole_list(tmp_path):
    # Own numbering from 2: the scenes before the trashed one are renumbered too, so no number repeats.
    repo, story_id = make(tmp_path, 'Сцена 2: Ранок', 'Сцена 3: Обід', 'Сцена 4: Вечір')
    first, middle, last = repo.list_scenes(story_id)
    repo.update_scene_plan(last.id, 'Сцена 4: Вечір\nВ.', last.revision)
    trashed = trash_scene(repo, story_id, middle.id, middle.revision)
    assert plans(repo, story_id) == [('Сцена 1: Ранок', None, 1), ('Сцена 2: Вечір\nВ.', 'Сцена 2: Вечір\nВ.', 2)]
    repo.update_scene_metadata(first.id, {'title': 'Світанок'}, repo.get_scene(first.id).revision)  # no duplicate number
    restore_scene(repo, story_id, middle.id, trashed.revision)
    assert plans(repo, story_id) == [('Сцена 1: Ранок', None, 1), ('Сцена 2: Обід', None, 2), ('Сцена 3: Вечір\nВ.', 'Сцена 3: Вечір\nВ.', 3)]
    head = repo.list_scenes(story_id)[0]
    trash_scene(repo, story_id, head.id, head.revision)
    assert [p[2] for p in plans(repo, story_id)] == [1, 2]


@pytest.mark.req('IMPORT-NUMBER')
def test_insert_joins_the_arc_of_the_scene_before(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Арки'))
    plan = '## Сцена 1: А\nАрка: Перша\nа\n## Сцена 2: Б\nб\n## Сцена 3: В\nАрка: Друга\nв'
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw=plan.encode(), kind='source_plan')])
    first, second, third = repo.list_scenes(story.id)
    scene = repo.create_scene(story.id, SceneCreate(title='Г', position=2), plan_template=True)
    arcs = repo.get_story(story.id).scene_arcs
    assert arcs[scene.id] == arcs[second.id] != arcs[third.id]
    assert [p[2] for p in plans(repo, story.id)] == [1, 2, 3, 4]


@pytest.mark.req('IMPORT-NUMBER')
def test_insert_already_makes_other_briefs_stale(tmp_path):
    """The renumbering adds no staleness: an insertion changes the order every draft snapshot records."""
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Застарілість'))
    first = repo.create_scene(story.id, SceneCreate(title='Перша'))
    repo.create_scene(story.id, SceneCreate(title='Друга'))
    context = build_context(repo, first.id, 'brief', RoleSettings(provider=ProviderSettings(model='fake')))
    # VALID-LINKS: a brief head is marked by its link only; the order selector is compared for non-head versions
    draft = repo.save_version(story.id, first.id, 'brief', '{}', [], dependency_snapshot=context.dependency_snapshot)
    assert not repo.get_version(draft.id).stale
    repo.create_scene(story.id, SceneCreate(title='Вставка', position=1))
    assert repo.get_version(draft.id).stale
