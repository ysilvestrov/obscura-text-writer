"""STORY-TIME-S05: the past of other arcs — facts of foreign flashbacks earlier than the start of the scene's arc (neutral)."""
import threading

from storygen.generation.context import build_context
from storygen.generation.models import WritersBrief
from storygen.generation.stages import execute_stage
from storygen.memory.flashbacks import foreign_flashbacks
from storygen.memory.journal import MemoryJournal
from storygen.providers.streaming import GenerationEvent
from tests.memory.merge_helpers import arc_book, fact, save_scene_journal, write_memory
from tests.memory.test_core_review import role

HEADER = 'МИНУЛЕ ІНШИХ АРОК'


class Gateway:
    def stream(self, *_):
        yield GenerationEvent(type='delta', text=WritersBrief(objective='o', beats=['b']).model_dump_json())
        yield GenerationEvent(type='terminal', finish_reason='stop')


def brief_text(repo, scene):
    return build_context(repo, scene.id, 'brief', role()).user_text


def write_brief(repo, scene):
    context = build_context(repo, scene.id, 'brief', role())
    attempt = execute_stage(repo, scene.id, 'brief', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed', attempt.error
    return attempt.result_version_id


def two_arcs(tmp_path, flashback='Початок: Рік -5 (спогад)', present='Початок: Рік 1', **kw):
    """Interleaved arcs A B A: scene 2 (arc B) has an empty lineage, so scene 1 (arc A) is foreign to it."""
    return arc_book(tmp_path, 'A B A', [['A', 'B']], beats=[flashback, present, 'Анна йде містом.'], **kw)


def section_of(text):
    return text.split(HEADER, 1)[1].split('\n\n', 1)[0]


def test_foreign_flashback_before_arc_start_is_shown(tmp_path):
    repo, story, scenes = two_arcs(tmp_path)
    context = build_context(repo, scenes[1].id, 'brief', role())
    assert HEADER in context.user_text
    section = section_of(context.user_text)
    assert 'Сцена 1 (рік -5):' in section and '- Подія сцени 1' in section
    assert 'Частина 1' not in section and ' A' not in section and ' B' not in section
    assert scenes[0].heads['memory'] in context.input_refs


def test_section_is_in_english_for_an_english_story(tmp_path):
    repo, story, scenes = two_arcs(tmp_path)
    repo.update_story_language(story.id, 'en', story.revision)
    text = brief_text(repo, scenes[1])
    assert 'THE PAST OF OTHER ARCS' in text and 'Scene 1 (year -5):' in text


def test_not_shown_when_below_later_unknown_or_arc_start_unknown(tmp_path):
    repo, story, scenes = arc_book(tmp_path / 'below', 'B A B', [['A', 'B']], beats=['Початок: Рік 1', 'Початок: Рік -5 (спогад)', 'Анна.'])
    assert HEADER not in brief_text(repo, scenes[0])
    for name, flashback, present in [('later', 'Початок: Рік 3 (спогад)', 'Початок: Рік 1'),
                                     ('unknown', 'Початок: невідомо (спогад)', 'Початок: Рік 1'),
                                     ('start', 'Початок: Рік -5 (спогад)', 'Анна йде містом.'),
                                     ('kinds', 'Початок: Рік -5 (спогад)', 'Початок: 01.03.2024, 08:00')]:
        repo, story, scenes = two_arcs(tmp_path / name, flashback, present)
        assert HEADER not in brief_text(repo, scenes[1]), name


def test_meeting_scene_shows_a_fact_once(tmp_path):
    beats = ['Початок: Рік 1', 'Початок: Рік 1', 'Початок: Рік -5 (спогад)', 'Початок: Рік 2', 'Анна.']
    repo, story, scenes = arc_book(tmp_path, 'A B C A+B C', [['A', 'B', 'C']], beats=beats)
    view = repo.context_view(story.id)
    items = foreign_flashbacks(view, view.get_story(story.id), view.list_scenes(story.id), view.get_scene(scenes[3].id), 'uk')
    assert [(item.scene_id, item.facts) for item in items] == [(scenes[2].id, ('Подія сцени 3',))]


def test_lineage_flashback_is_not_foreign(tmp_path):
    beats = ['Початок: Рік -5 (спогад)', 'Початок: Рік 1', 'Початок: Рік 1']
    repo, story, scenes = arc_book(tmp_path, 'A B A', [['A', 'B']], beats=beats)
    assert HEADER in brief_text(repo, scenes[1])
    text = brief_text(repo, scenes[2])
    assert HEADER not in text and 'Подія сцени 1' in text


def test_limit_of_forty_facts_warns(tmp_path):
    def events(n, prose, previous):
        return [fact(f'Факт {n}.{i}', prose) for i in range(1, 7)] if n < 8 else [fact('Подія', prose)]
    beats = [f'Початок: Рік -{10 - n} (спогад)' for n in range(1, 8)] + ['Початок: Рік 1', 'Анна.']
    repo, story, scenes = arc_book(tmp_path, 'A A A A A A A B A', [['A', 'B']], events, beats=beats)
    context = build_context(repo, scenes[7].id, 'brief', role())
    section = section_of(context.user_text)
    assert section.count('\n- ') == 40
    assert 'Факт 7.1' in section and 'Факт 1.4' in section and 'Факт 1.5' not in section
    assert any('показано 40 фактів із 42' in w for w in context.context_warnings)


def test_flashback_without_fresh_memory_is_skipped_then_stales_the_scene(tmp_path):
    repo, story, scenes = two_arcs(tmp_path, only={2})
    assert HEADER not in brief_text(repo, scenes[1])
    brief = write_brief(repo, scenes[1])
    assert not repo.get_version(brief).stale
    write_memory(repo, story.id, only={1, 3})
    assert repo.get_version(brief).stale


def test_new_flashback_memory_stales_the_scene(tmp_path):
    repo, story, scenes = two_arcs(tmp_path)
    brief = write_brief(repo, scenes[1])
    assert not repo.get_version(brief).stale
    save_scene_journal(repo, repo.get_scene(scenes[0].id), MemoryJournal(), [fact('Інша давня подія', scenes[0].heads['prose'])])
    assert repo.get_version(brief).stale


def test_unset_flag_stales_the_scene(tmp_path):
    repo, story, scenes = two_arcs(tmp_path, flashback='Початок: Рік -5')
    first = repo.update_scene_metadata(scenes[0].id, {'flashback': True}, scenes[0].revision)
    brief = write_brief(repo, scenes[1])
    assert HEADER in brief_text(repo, scenes[1]) and not repo.get_version(brief).stale
    repo.update_scene_metadata(first.id, {'flashback': False}, first.revision)
    assert repo.get_version(brief).stale


def test_flag_set_later_stales_an_old_snapshot(tmp_path):
    repo, story, scenes = two_arcs(tmp_path, flashback='Початок: Рік -5')
    brief = write_brief(repo, scenes[1])
    assert not any(s.field == 'flashback_facts' for s in repo.get_version(brief).dependency_snapshot.selectors)
    repo.update_scene_metadata(scenes[0].id, {'flashback': True}, scenes[0].revision)
    assert repo.get_version(brief).stale


def test_moment_change_inside_visibility_stales_the_scene(tmp_path):
    from storygen.memory.flashbacks import flashback_facts_value
    repo, story, scenes = two_arcs(tmp_path)
    view = repo.context_view(story.id)
    before = flashback_facts_value(view, view.get_story(story.id), view.list_scenes(story.id), view.get_scene(scenes[1].id))
    assert before == [f"{scenes[0].id}|{scenes[0].heads['memory']}|рік -5"]
    scene = repo.get_scene(scenes[0].id)
    moved = scene.model_copy(update={'beats': 'Початок: Рік -4 (спогад)'})
    after = flashback_facts_value(view, view.get_story(story.id), [moved] + view.list_scenes(story.id)[1:], view.get_scene(scenes[1].id))
    assert after == [f"{scenes[0].id}|{scenes[0].heads['memory']}|рік -4"]
