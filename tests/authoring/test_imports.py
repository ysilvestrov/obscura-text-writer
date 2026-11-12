import hashlib
from pathlib import Path

import pytest

from storygen.authoring.imports import SourceFile, import_sources, suggest_scene_sections
from storygen.authoring.service import reorder_scenes
from storygen.domain import StoryCreate
from storygen.storage.repository import Repository


def test_wrong_doors_import_proposes_seven_scenes(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title="Двері"))
    text=Path("tests/fixtures/prototype/plan.md").read_bytes()
    result=import_sources(repo,story.id,[SourceFile(name="plan.md",raw=text)])
    assert len(result.proposed_scenes)==7
    assert len(repo.list_scenes(story.id))==7
    assert "Наскрізні символи" in repo.read_text(result.version_ids[0])


def test_sources_preserved_byte_for_byte_and_filename_cannot_escape(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title="Твір"))
    raw=b'\xef\xbb\xbf'+"Український план".encode("utf-8")
    result=import_sources(repo,story.id,[SourceFile(name="../plan.md",raw=raw)])
    source=result.sources[0]
    assert repo.files.read(source["relative_path"],source["sha256"])==raw
    assert source["sha256"]==hashlib.sha256(raw).hexdigest()
    assert repo.read_text(result.version_ids[0])=="Український план"
    assert not (tmp_path.parent/"plan.md").exists()


def test_unknown_structure_remains_editable():
    sections=suggest_scene_sections("Увесь план без заголовків.")
    assert len(sections)==1
    assert sections[0].beats=="Увесь план без заголовків."


def test_reorder_rejects_foreign_or_duplicate_ids(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title="Твір"))
    result=import_sources(repo,story.id,[SourceFile(name="plan.md",raw="Сцена 1. Ранок\nПочаток\nСцена 2. Вечір\nКінець".encode())])
    scenes=repo.list_scenes(story.id)
    revision=repo.get_story(story.id).revision
    reorder_scenes(repo,story.id,[s.id for s in reversed(scenes)],revision)
    assert repo.list_scenes(story.id)[0].id==scenes[1].id
    with pytest.raises(ValueError):
        reorder_scenes(repo,story.id,[scenes[0].id,scenes[0].id],repo.get_story(story.id).revision)


TITLED_PLAN="""# План: Маяк на пристані

Сцена 1: Лист у скриньці
Хто бере участь: Анна.
Анна знаходить лист без зворотної адреси.

Сцена 2: Пристань уночі
Хто бере участь: Борис, Анна.
Анна йде з ліхтарем до старої пристані.
"""
TWO_CARDS="# Персонажі\n\n## Анна\nДоглядачка маяка, 34 роки.\n\n## Борис\nРибалка, 50 років.\n"


def _plan_and_cards(order):
    files={'plan':SourceFile(name='plan.md',raw=TITLED_PLAN.encode('utf-8')),
           'cards':SourceFile(name='characters.md',raw=TWO_CARDS.encode('utf-8'),kind='source_characters')}
    return [files[key] for key in order]


def test_plan_title_before_plain_scene_lines_is_not_imported_as_a_scene(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Маяк',target_words=7000))
    result=import_sources(repo,story.id,_plan_and_cards(['plan']))
    scenes=repo.list_scenes(story.id)
    assert [(s.author_scene_number,s.title,s.target_words) for s in scenes]==[(1,'Лист у скриньці',3500),(2,'Пристань уночі',3500)]
    assert result.warnings==[]
    again=import_sources(repo,story.id,_plan_and_cards(['plan']))
    assert again.created_scene_ids==[] and len(repo.list_scenes(story.id))==2


@pytest.mark.parametrize('order',[['plan','cards'],['cards','plan']])
def test_import_report_shows_the_stored_cast(tmp_path,order):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Маяк'))
    result=import_sources(repo,story.id,_plan_and_cards(order))
    stored=[scene.character_ids for scene in repo.list_scenes(story.id)]
    assert [len(ids) for ids in stored]==[1,2] and stored[1][1]==stored[0][0]
    assert [scene.character_ids for scene in result.proposed_scenes]==stored
