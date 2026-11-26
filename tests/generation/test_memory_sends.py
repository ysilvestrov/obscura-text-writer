"""R-49 (MANUSCRIPT-IMPORT-S16): the memory build says what the memory model receives, derived from the sections of the request."""
import pytest

from storygen.domain import ContentRating
from storygen.generation.context import build_context
from storygen.generation.memory_build import SECTION_CATEGORIES, is_local_provider, memory_sends, request_sections
from storygen.providers.models import ProviderSettings
from tests.generation.test_location_context import memory_scene, role
from tests.link_helpers import approve_links


def rated(tmp_path, beats):
    repo, story, scene = memory_scene(tmp_path, beats)
    repo.update_story_rating(story.id, ContentRating(sexual=0, violence=0, themes=0), repo.get_story(story.id).revision)
    approve_links(repo, story.id)
    return repo, repo.get_story(story.id), repo.get_scene(scene.id)


@pytest.mark.req('MANUSCRIPT-IMPORT')
def test_sends_cover_every_section_of_the_memory_request(tmp_path):
    repo, story, scene = rated(tmp_path, 'Локація: Дім / кухня')
    context = build_context(repo, scene.id, 'memory', role())
    sections = request_sections(context)
    assert sections and sections <= set(SECTION_CATEGORIES), sections - set(SECTION_CATEGORIES)
    keys = [item['key'] for item in memory_sends(repo, ProviderSettings(model='m'), [scene], context)['items']]
    assert keys == ['prose', 'memory_catalog', 'places']


@pytest.mark.req('MANUSCRIPT-IMPORT')
def test_sends_words_sum_the_prose_of_target_scenes(tmp_path):
    repo, story, scene = rated(tmp_path, 'Вдома')
    context = build_context(repo, scene.id, 'memory', role())
    prose = memory_sends(repo, ProviderSettings(model='m'), [scene], context)['items'][0]
    assert prose == {'key': 'prose', 'scenes': 1, 'words': 2}  # «Анна вдома.»


@pytest.mark.req('MANUSCRIPT-IMPORT')
def test_sends_omit_places_and_series_when_absent(tmp_path):
    repo, story, scene = rated(tmp_path, 'Вдома')
    context = build_context(repo, scene.id, 'memory', role())
    keys = {item['key'] for item in memory_sends(repo, ProviderSettings(model='m'), [scene], context)['items']}
    assert 'places' not in keys and 'series_facts' not in keys


@pytest.mark.req('MANUSCRIPT-IMPORT')
def test_local_endpoint_is_flagged():
    for url in ('http://localhost:1234/v1', 'http://127.0.0.1:11434/v1', 'http://[::1]:8080/v1'):
        assert is_local_provider(ProviderSettings(provider='local', model='m', base_url=url)), url
    assert not is_local_provider(ProviderSettings(provider='openrouter', model='m'))


@pytest.mark.req('MANUSCRIPT-IMPORT')
def test_memory_build_preview_says_what_the_model_receives(tmp_path):
    from storygen.billing.service import set_limit
    from storygen.generation.readiness import preview
    from tests.generation.test_memory_build import cloud_role, rebuild, written_book
    repo, story, scenes = written_book(tmp_path, ['Перша сцена тут.', 'Друга.'], memory_role=cloud_role(80000))
    set_limit(repo, 'story:' + story.id, '10', 0)
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['ready'] is True, result['reason']
    assert result['sends']['local'] is False
    assert result['sends']['items'][0] == {'key': 'prose', 'scenes': 2, 'words': 4}


@pytest.mark.req('MANUSCRIPT-IMPORT')
def test_places_count_for_any_target_not_only_the_first_request(tmp_path):
    """Final review: the first scene's request may carry no places while a later target sends its place paths."""
    from types import SimpleNamespace
    repo, story, scene = rated(tmp_path, 'Локація: Дім / кухня')
    context = build_context(repo, scene.id, 'memory', role())
    first_without_places = SimpleNamespace(user_text='\n\n'.join(
        part for part in context.user_text.split('\n\n') if not part.lstrip().startswith('ДОЗВОЛЕНІ LOCATION_IDS')))
    assert 'places' not in request_sections(first_without_places) and scene.location_ids
    keys = [item['key'] for item in memory_sends(repo.context_view(story.id), ProviderSettings(model='m'), [scene], first_without_places)['items']]
    assert 'places' in keys
