import json
import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.application.exports import export_story


def test_export_contains_selected_versions_in_scene_order(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='../Двері'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(2)]
    for scene in scenes:save_manual_prose(repo,scene.id,'Текст '+str(scene.position),0)
    path=export_story(repo,story.id,'md')
    assert path.is_relative_to(tmp_path) and path.name.endswith('.md')
    assert path.read_text(encoding='utf-8').index('Текст 0')<path.read_text(encoding='utf-8').index('Текст 1')
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['scenes'])==2 and manifest['complete']


def test_export_blocks_partial_stale_or_missing_scene_by_default(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'));repo.create_scene(story.id,SceneCreate(title='Без тексту'))
    with pytest.raises(ValueError):export_story(repo,story.id,'txt')
    path=export_story(repo,story.id,'txt',allow_incomplete=True)
    assert 'НЕЗАВЕРШЕНО' in path.read_text(encoding='utf-8')
