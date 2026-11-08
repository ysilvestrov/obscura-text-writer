import itertools

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StageAttempt, StoryCreate, new_id
from storygen.run_models import Run, RunRequest
from storygen.web.app import create_app

KEYS = ('copyedit_proposal', 'rewrite_proposal')
VARIANTS = [{'x': 1}, {}, None, 'missing']
STATES = ['completed', 'needs_review', 'alternative', 'failed']


def _seed(repo):
    stories = []
    for t in range(2):
        story = repo.create_story(StoryCreate(title=f'Твір {t}'))
        scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {i}')) for i in range(2)]
        runs = []
        for r in range(2):
            run = Run(id=new_id(), story_id=story.id, request_id=f'{story.id}-{r}',
                      request=RunRequest(story_id=story.id, mode='prepare'), tasks=[])
            runs.append(repo.enqueue_run(run)[0])
        stories.append((story, scenes, runs))
    n = 0
    for story, scenes, runs in stories:
        for scene, run_id, ce, rw, state in itertools.product(
                scenes, [None, runs[0].id, runs[1].id], VARIANTS, VARIANTS, STATES):
            ctx = {}
            if ce != 'missing':
                ctx['copyedit_proposal'] = ce
            if rw != 'missing':
                ctx['rewrite_proposal'] = rw
            n += 1
            repo.save_attempt(StageAttempt(id=f'a{n:05d}', run_id=run_id, story_id=story.id, scene_id=scene.id,
                                           stage='copyedit', state=state, context=ctx, partial_path='p.txt'))
        repo.save_attempt(StageAttempt(id=f'n{story.id}', story_id=story.id, scene_id=None, stage='brief',
                                       state='failed', context={}, partial_path='p.txt'))
    return stories


def test_sql_filters_match_python_filters(tmp_path):
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    stories = _seed(repo)
    checked = 0
    for story, scenes, runs in stories:
        full = repo.list_attempts(story.id)
        assert full
        for run_id in [None, runs[0].id, runs[1].id, 'absent']:
            for scene_id in [None, scenes[0].id, scenes[1].id, 'absent']:
                for key in [None, *KEYS]:
                    expected = [a.id for a in full if (run_id is None or a.run_id == run_id)
                                and (scene_id is None or a.scene_id == scene_id)
                                and (key is None or a.context.get(key) is not None)]
                    got = repo.list_attempts(story.id, run_id, scene_id=scene_id, context_key=key)
                    assert [a.id for a in got] == expected
                    assert repo.list_attempts(story.id, run_id=run_id, scene_id=scene_id, context_key=key) == got
                    checked += 1
    assert checked == 2 * 4 * 4 * 3


def test_falsy_proposals_are_removed_by_route_filters_as_before(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    stories = _seed(repo)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        for story, scenes, _ in stories:
            full = repo.list_attempts(story.id)
            for scene in scenes:
                old_ce = [a.id for a in full if a.scene_id == scene.id and a.context.get('copyedit_proposal')
                          and a.state in {'completed', 'needs_review', 'alternative'}]
                old_rw = [a.id for a in full if a.scene_id == scene.id and a.context.get('rewrite_proposal')]
                assert old_ce and old_rw
                # Failed attempts with a non-empty proposal exist for this scene and the copyedit route drops them.
                failed = [a.id for a in full if a.scene_id == scene.id and a.state == 'failed'
                          and a.context.get('copyedit_proposal')]
                assert failed and not set(failed) & set(old_ce)
                r = client.get(f'/api/scenes/{scene.id}/copyedits')
                assert r.status_code == 200
                assert [a['id'] for a in r.json()['attempts']] == old_ce
                r = client.get(f'/api/scenes/{scene.id}/rewrites')
                assert [a['id'] for a in r.json()['attempts']] == old_rw


def test_routes_return_same_attempts_as_before(tmp_path):
    test_falsy_proposals_are_removed_by_route_filters_as_before(tmp_path)


def test_routes_filter_in_sql(tmp_path, monkeypatch):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='SQL'))
    scene = repo.create_scene(story.id, SceneCreate(title='С'))
    calls = []
    original = type(repo).list_attempts

    def spy(self, story_id, run_id=None, **kw):
        calls.append(kw)
        return original(self, story_id, run_id, **kw)
    monkeypatch.setattr(type(repo), 'list_attempts', spy)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        client.get(f'/api/scenes/{scene.id}/copyedits')
        client.get(f'/api/scenes/{scene.id}/rewrites')
    assert calls == [{'scene_id': scene.id, 'context_key': 'copyedit_proposal'},
                     {'scene_id': scene.id, 'context_key': 'rewrite_proposal'}]


def test_unknown_context_key_is_rejected(tmp_path):
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ключ'))
    for bad in ['x', "a') OR 1=1 --", '', 'dependency_snapshot']:
        with pytest.raises(ValueError):
            repo.list_attempts(story.id, context_key=bad)


def test_list_runs_filters_by_story_in_sql(tmp_path):
    from storygen.storage.repository import Repository
    repo = Repository(tmp_path)
    stories = _seed(repo)
    everything = repo.list_runs()
    assert len(everything) == 4
    for story, _, runs in stories:
        got = repo.list_runs(story.id)
        assert [r.id for r in got] == [r.id for r in everything if r.story_id == story.id] == [r.id for r in runs]
    assert repo.list_runs('absent') == []
