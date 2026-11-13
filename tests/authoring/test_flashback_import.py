"""STORY-TIME-S03, S07: the plan line «Спогад: так|ні» is cut from the scene plan and sets the field in every edition (neutral examples)."""
from storygen.authoring.imports import SourceFile, import_sources
from storygen.domain import StoryCreate
from storygen.plan_sections import cut_flashback_line
from storygen.storage.repository import Repository


def plan(*lines):
    return ''.join(f'## Сцена {n}: Подія {n}\n{line}Анна йде містом.\n\n' for n, line in enumerate(lines, 1))


def imported(tmp_path, text):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Оповідання'))
    result = import_sources(repo, story.id, [SourceFile(name='plan.md', raw=text.encode(), kind='source_plan')])
    return repo, story, repo.list_scenes(story.id), [w for f in result.files for w in f.warnings]


def test_flashback_line_is_cut_and_sets_the_field():
    assert cut_flashback_line('Спогад: так\nАнна йде містом.\n') == ('Анна йде містом.\n', True, False)
    assert cut_flashback_line('**Flashback:** no\nText\n') == ('Text\n', False, False)
    assert cut_flashback_line('Спогад: можливо\nText\n') == ('Text\n', None, True)
    assert cut_flashback_line('Text\n') == ('Text\n', None, False)


def test_import_sets_the_flag(tmp_path):
    repo, story, scenes, warnings = imported(tmp_path, plan('Спогад: так\n', ''))
    assert [s.flashback for s in scenes] == [True, False]
    assert 'Спогад' not in scenes[0].beats
    assert 'Спогад:' not in repo.read_text(repo.active_source(story.id, 'source_plan').id)


def test_import_sets_the_flag_in_an_edition_without_long_prose(tmp_path, store_edition):
    _, _, scenes, warnings = imported(tmp_path, plan('Flashback: yes\n', 'Спогад: можливо\n'))
    assert [s.flashback for s in scenes] == [True, False]
    assert any('«Спогад:»' in w for w in warnings)
