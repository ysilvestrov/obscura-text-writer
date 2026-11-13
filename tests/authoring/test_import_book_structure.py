import pytest

from storygen.authoring.imports import ImportBatchFailure, SourceFile, import_sources
from storygen.book.structure import effective_structure
from storygen.domain import SceneCreate, StoryCreate
from storygen.plan_sections import split_book_plan
from storygen.storage.repository import Repository


PLAN = '''# План

# Частина 1: Дім

## Сцена 1: Ранок
Арка: Ранок
Герой прокидається.

## Сцена 2: Обід
Герой їсть.

# Частина 2: Дорога

## Сцена 3: Вихід
Герой виходить.
'''

MORE = '''# Частина 2: Дорога

## Сцена 4: Міст
**Арка:** Міст
Герой переходить міст.
'''


def run(repo, story, text):
    return import_sources(repo, story.id, [SourceFile(name='plan.md', raw=text.encode())])


def book(repo, story_id):
    story = repo.get_story(story_id)
    scenes = repo.list_scenes(story_id)
    return story, scenes, effective_structure(story, scenes)


def test_split_book_plan_finds_parts_and_arc_lines():
    preamble, sections, found = split_book_plan(PLAN, 'Сцена')
    assert found
    assert [(s.part_title, s.arc_title) for s in sections] == [('Дім', 'Ранок'), ('Дім', 'Ранок'), ('Дорога', None)]
    texts = ''.join(s.section.text for s in sections)
    assert 'Частина' not in texts and 'Арка' not in texts
    assert [s.section.author_scene_number for s in sections] == [1, 2, 3]


def test_split_book_plan_without_markers_matches_split_plan():
    from storygen.plan_sections import split_plan
    text = '# План\n\nСцена 1: Лист\nАнна знаходить лист.\nСцена 2: Відповідь\nАнна пише.\n'
    preamble, sections, found = split_book_plan(text, 'Сцена')
    assert not found
    assert (preamble, [s.section for s in sections]) == split_plan(text, 'Сцена')


def test_part_heading_at_scene_level_is_a_scene():
    _, sections, found = split_book_plan('## Частина перша\nТекст.\n\n## Сцена 2: Далі\nЩе.\n', 'Сцена')
    assert not found and len(sections) == 2


def test_import_creates_parts_arcs_and_clean_plans(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    result = run(repo, story, PLAN)
    assert len(result.created_scene_ids) == 3
    story, scenes, structure = book(repo, story.id)
    assert structure.explicit and structure.kind == 'structured'
    assert [p.title for p in structure.parts] == ['Дім', 'Дорога']
    assert [[a.title for a in p.arcs] for p in structure.parts] == [['Ранок'], ['']]
    arcs = [structure.arc_of[s.id] for s in scenes]
    assert arcs[0] == arcs[1] != arcs[2]
    for scene in scenes:
        plan = repo.list_versions(story.id, scene.id, 'scene_plan')[0]
        text = repo.context_view(story.id).read_text(plan.id)
        assert 'Частина' not in text and 'Арка' not in text


def test_additive_import_continues_the_last_part_by_title(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    run(repo, story, PLAN)
    run(repo, repo.get_story(story.id), MORE)
    story, scenes, structure = book(repo, story.id)
    assert [p.title for p in structure.parts] == ['Дім', 'Дорога']
    assert [a.title for a in structure.parts[1].arcs] == ['', 'Міст']
    assert structure.arc_of[scenes[-1].id] == structure.parts[1].arcs[1].id


def test_flat_book_with_scenes_gets_them_in_the_first_part(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    old = repo.create_scene(story.id, SceneCreate(title='Стара'))
    run(repo, repo.get_story(story.id), PLAN)
    story, scenes, structure = book(repo, story.id)
    assert [p.title for p in structure.parts] == ['', 'Дім', 'Дорога']
    assert structure.arc_of[old.id] == structure.parts[0].arcs[0].id
    assert len(scenes) == 4


def test_plan_without_markers_keeps_implicit_structure(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    run(repo, story, 'Сцена 1: Лист\nАнна знаходить лист.\n')
    story, _, structure = book(repo, story.id)
    assert story.book_structure is None and structure.kind == 'flat'


def test_plain_plan_into_structured_book_appends_to_last_arc(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    run(repo, story, PLAN)
    run(repo, repo.get_story(story.id), 'Сцена 9: Кінець\nВсе.\n')
    story, scenes, structure = book(repo, story.id)
    assert structure.arc_of[scenes[-1].id] == structure.arc_of[scenes[-2].id]


def test_store_edition_imports_markers_as_text(tmp_path, store_edition):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    run(repo, story, PLAN)
    story, scenes, structure = book(repo, story.id)
    assert story.book_structure is None
    view = repo.context_view(story.id)
    texts = ''.join(view.read_text(repo.list_versions(story.id, s.id, 'scene_plan')[0].id) for s in scenes)
    assert 'Арка: Ранок' in texts and 'Частина 2' in texts


def test_import_may_interleave_arcs_of_a_part(tmp_path):
    # Project 2: arcs of a part may interleave, so going back to an earlier arc of the continued part is accepted.
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    run(repo, story, PLAN)
    before = repo.get_story(story.id)
    mixed = '# Частина 2: Дорога\n\n## Сцена 5: А\nАрка: Ліс\nТекст.\n\n## Сцена 6: Б\nАрка: \nТекст.\n'
    run(repo, before, mixed)
    assert len(repo.list_scenes(story.id)) == 5


def test_parts_with_equal_or_empty_titles_stay_separate(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    text = '''# План

# Частина 1: Інтерлюдія

## Сцена 1: А
Текст.

# Частина 2: Інтерлюдія

## Сцена 2: Б
Текст.

# Частина 3:

## Сцена 3: В
Текст.

# Частина 4:

## Сцена 4: Г
Текст.
'''
    run(repo, story, text)
    story, scenes, structure = book(repo, story.id)
    assert [p.title for p in structure.parts] == ['Інтерлюдія', 'Інтерлюдія', '', '']
    assert len({structure.part_of_arc[structure.arc_of[s.id]] for s in scenes}) == 4


def test_first_structured_import_keeps_no_markers_in_the_source_plan(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    run(repo, story, PLAN)
    view = repo.context_view(story.id)
    text = view.read_text(view.active_source(story.id, 'source_plan').id)
    assert 'Герой прокидається' in text and 'Частина' not in text and 'Арка' not in text
