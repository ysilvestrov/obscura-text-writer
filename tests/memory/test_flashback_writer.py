"""STORY-TIME-S04: the writer of a flashback and the day-change signal (neutral examples)."""
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context, writer_day_change
from storygen.generation.context_labels import label
from storygen.memory.journal import _add_event
from storygen.memory.story_time import comparison_scene
from storygen.storage.repository import Repository
from tests.memory.merge_helpers import arc_book
from tests.memory.test_core_review import role, two_scenes


def test_short_prose_flashback_writer_has_no_memory(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    assert label('memory_header', 'uk') in build_context(repo, s2.id, 'brief', role()).user_text
    repo.update_scene_metadata(s2.id, {'flashback': True}, s2.revision)
    context = build_context(repo, s2.id, 'brief', role())
    assert label('memory_header', 'uk') not in context.user_text
    assert 'Халат' not in context.user_text and 'Хто стукав?' not in context.user_text


def test_book_flashback_writer_has_no_core_or_states(tmp_path):
    def events(n, prose, previous):
        return [_add_event('character_states', 'Халат', prose, 'Анна йде містом', 0, ['c1']),
                _add_event('facts', 'Ключ лежить під килимком', prose, 'Анна йде містом', 0)] if n == 1 else []
    repo, story, scenes = arc_book(tmp_path, 'A B A', [['A', 'B']], events)
    assert 'Халат' in build_context(repo, scenes[2].id, 'brief', role()).user_text
    repo.update_scene_metadata(scenes[2].id, {'flashback': True}, scenes[2].revision)
    context = build_context(repo, scenes[2].id, 'brief', role())
    assert 'Ключ лежить під килимком' in context.user_text and 'Халат' not in context.user_text


def test_flashback_neither_gives_nor_breaks_the_day_signal(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Дні'))
    for n, beats in enumerate(['Початок: День 1', 'Початок: Рік -5 (спогад)', 'Початок: День 2'], 1):
        repo.create_scene(story.id, SceneCreate(title=f'С{n}', beats=beats, character_ids=['A']))
    story, scenes = repo.get_story(story.id), repo.list_scenes(story.id)
    assert writer_day_change(scenes[1], scenes, ['A'], {'A': 'Анна'}, 'uk', story) is None
    assert comparison_scene(scenes, scenes[2], 'A', story).id == scenes[0].id
    note = writer_day_change(scenes[2], scenes, ['A'], {'A': 'Анна'}, 'uk', story)
    assert note and 'день 1' in note and 'день 2' in note
