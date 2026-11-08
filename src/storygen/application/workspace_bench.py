"""Workspace response benchmark: synthetic story, timings and a content digest.

Only the public Repository API, readiness.preview and impact.presentation.scene_status
are used. The digest covers outputs only (never timings), so a before/after comparison
proves that a speed change did not change results.
"""
import contextlib
import hashlib
import json
import time
from pathlib import Path

from pydantic import BaseModel

from ..authoring.blueprints import get_role_settings, save_role_settings
from ..domain import SceneCreate, StoryCreate
from ..generation.dependencies import save_manual_prose
from ..generation.pipeline import STAGES
from ..impact.presentation import scene_status
from ..memory.service import save_scene_memory
from ..providers.models import RoleSettings
from ..run_models import RunRequest
from ..storage.repository import Repository

OPERATIONS = ('prepare', *STAGES, 'scene', 'remaining', 'rebuild_memory', 'edit_loop')
SYNTHETIC_TITLE = 'Synthetic workspace bench'
BENCH_ROLES = ('planner', 'writer', 'editor', 'memory')
# Local provider with builtin prompts: readiness stays offline and needs no budget limit. The window is
# wide enough for a 300-scene memory and plan, so preview reaches build_context and returns ready=True.
BENCH_ROLE = dict(provider=dict(provider='local', model='bench-local'), context_tokens=262144,
                  max_output_tokens=4096, max_input_chars=2_000_000)


@contextlib.contextmanager
def _shallow_model_copy(enabled):
    original = BaseModel.model_copy
    if enabled:
        BaseModel.model_copy = lambda self, *, update=None, deep=False: original(self, update=update, deep=False)
    try:
        yield
    finally:
        BaseModel.model_copy = original


def build_story(repo: Repository, scenes: int, shallow_copies: bool = False) -> str:
    """Create a story with `scenes` scenes, each with a plan, manual prose and memory (one fact per scene).

    shallow_copies swaps pydantic deep copies for shallow ones while the data is written: the baseline
    code pays O(n^2) deep copies per write, which makes a 300-scene build take hours. Only the setup of
    the synthetic data is affected; measure() always runs the real code.
    """
    with _shallow_model_copy(shallow_copies):
        return _build_story(repo, scenes)


def configure_roles(repo: Repository, story_id: str) -> None:
    """Save the bench roles (planner, writer, editor, memory) so readiness checks the full path."""
    role = RoleSettings.model_validate(BENCH_ROLE)
    for name in BENCH_ROLES:
        save_role_settings(repo, story_id, name, role, repo.get_story(story_id).revision)


def _build_story(repo, scenes):
    story = repo.create_story(StoryCreate(title=SYNTHETIC_TITLE))
    sources, facts = [], []
    for i in range(scenes):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Scene {i + 1}', beats=f'Plan beat {i + 1}'))
        repo.update_scene_plan(scene.id, scene.beats, scene.revision)
        scene = repo.get_scene(scene.id)
        text = f'Synthetic detail number {i + 1}.'
        save_manual_prose(repo, scene.id, text, scene.revision)
        scene = repo.get_scene(scene.id)
        sources.append(scene.heads['prose'])
        facts.append(dict(text=text, source_version_id=sources[-1], quote=text))
        save_scene_memory(repo, scene.id, json.dumps(dict(source_prose_ids=list(sources), facts=list(facts))), scene.revision)
    # Roles are saved last, so their presence marks a completed build (see _check_synthetic).
    configure_roles(repo, story.id)
    return story.id


def _check_synthetic(repo, story_id, scenes):
    """Refuse to measure a reused synthetic story that is not the requested, completed workload."""
    found = len(repo.context_view(story_id).list_scenes(story_id))
    if found != scenes:
        raise ValueError(f'synthetic_mismatch: workdir story has {found} scenes, requested {scenes}; use a new --workdir')
    roles = get_role_settings(repo, story_id)
    if any(name not in roles for name in BENCH_ROLES):
        raise ValueError('synthetic_incomplete: workdir story has no bench roles (interrupted or old build); '
                         'use a new --workdir')


def _request(story_id, scene_id, name):
    # Mirrors RunCoordinator.readiness: model_construct permits an unselected scene.
    return RunRequest.model_construct(
        story_id=story_id, scene_id=scene_id,
        mode='stage' if name in STAGES else name,
        stage=name if name in STAGES else None,
        edit_workflow='loop' if name in {'scene', 'remaining'} else 'single',
        editor_source_head=None, editor_source_version_id=None)


def _story_view(repo, story_id):
    # Same repository calls as routes_stories.story_view.
    view = repo.context_view(story_id)
    story = view.get_story(story_id)
    return {'impact_status': scene_status(view), 'story': story,
            'scenes': [view.effective_scene(s.id) for s in view.list_scenes(story_id)]}


def _scene_attempts(repo, story_id, scene_id):
    # Same calls and filters as routes_versions.list_copyedit_proposals and routes_rewrites.list_rewrites.
    copyedits = [a.id for a in repo.list_attempts(story_id, scene_id=scene_id, context_key='copyedit_proposal')
                 if a.context.get('copyedit_proposal') and a.state in {'completed', 'needs_review', 'alternative'}]
    rewrites = [a.id for a in repo.list_attempts(story_id, scene_id=scene_id, context_key='rewrite_proposal')
                if a.context.get('rewrite_proposal')]
    return copyedits, rewrites


def _timed(timings, key, fn):
    start = time.perf_counter()
    result = fn()
    timings[key] = timings.get(key, 0.0) + time.perf_counter() - start
    return result


def _default(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode='json')
    return str(value)


def measure(repo: Repository, story_id: str) -> dict:
    from ..generation.readiness import preview
    repo.get_story(story_id)
    scenes = repo.context_view(story_id).list_scenes(story_id)
    middle = scenes[len(scenes) // 2].id if scenes else None
    timings, outputs = {}, {}
    for name in OPERATIONS:
        outputs['readiness:' + name] = _timed(timings, 'readiness:' + name,
                                              lambda name=name: preview(repo, _request(story_id, middle, name)))
    outputs['story_view'] = _timed(timings, 'story_view', lambda: _story_view(repo, story_id))
    outputs['attempts'] = _timed(timings, 'list_attempts', lambda: _scene_attempts(repo, story_id, middle))
    runs = _timed(timings, 'list_runs', lambda: repo.list_runs(story_id))
    outputs['run_ids'] = [r.id for r in runs]

    def select():
        # Scene selection in the UI: the repository calls behind versions, copyedits, rewrites,
        # readiness?operation=brief, runs, run detail and the story view.
        scene = repo.get_scene(middle)
        repo.list_versions(scene.story_id, middle)
        repo.list_acceptances(scene.story_id)
        _scene_attempts(repo, story_id, middle)
        preview(repo, _request(story_id, middle, 'brief'))
        listed = repo.list_runs(story_id)
        if listed:
            repo.get_run(listed[-1].id)
            repo.list_attempts(story_id, listed[-1].id)
        _story_view(repo, story_id)
    _timed(timings, 'scene_select', select)
    canonical = json.dumps(outputs, sort_keys=True, ensure_ascii=False, default=_default)
    return {'story': story_id[:8], 'scenes': len(scenes),
            'timings': {k: round(v, 6) for k, v in timings.items()},
            'digest': hashlib.sha256(canonical.encode('utf-8')).hexdigest()}


def run(data=None, story=None, synthetic=None, workdir=None) -> dict:
    """Open a data directory (or a synthetic workdir, reused only when it holds the same completed workload) and measure."""
    repo = Repository(Path(workdir if synthetic else data))
    if synthetic:
        existing = [s for s in repo.list_stories() if s.title == SYNTHETIC_TITLE]
        if len(existing) > 1:
            raise ValueError('synthetic_ambiguous: workdir holds several synthetic stories; use a new --workdir')
        if existing:
            story_id = existing[0].id
            _check_synthetic(repo, story_id, synthetic)
        else:
            story_id = build_story(repo, synthetic, shallow_copies=True)
    else:
        chosen = [s for s in repo.list_stories() if story is None or s.id.startswith(story)]
        if not chosen:
            raise LookupError('story_not_found')
        story_id = chosen[0].id
    return measure(repo, story_id)
