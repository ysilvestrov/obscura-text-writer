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
