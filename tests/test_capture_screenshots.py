import pytest

from scripts.capture_screenshots import STORIES, seed
from storygen.storage.repository import Repository


@pytest.mark.req('DOCS-SITE')
def test_seed_creates_neutral_stories_in_both_languages(tmp_path):
    ids=seed(tmp_path/'data')
    repo=Repository(tmp_path/'data')
    assert set(ids)=={'uk','en'}
    for lang,spec in STORIES.items():
        story=repo.get_story(ids[lang]['story_id'])
        assert story.title==spec['title'] and story.language==lang
        scene=repo.get_scene(ids[lang]['scene_id'])
        assert scene.heads.get('draft') and scene.heads.get('brief')
