"""Explicit review basis; current consistency never backfills creation history."""
from ..impact.models import ImpactPlan,fingerprint
from ..impact.planning import capture_target
from ..storage.snapshots import build_author_baseline

MODES={'historical_delta','current_consistency'}


def mode_for(view,version_id):
    root=view.acceptances[version_id].baseline if version_id in view.acceptances else view.versions[version_id].dependency_snapshot
    return 'historical_delta' if root is not None else 'current_consistency'


def capture(view,version_id,mode=None):
    mode=mode or mode_for(view,version_id)
    if mode not in MODES:raise ValueError('Невідомий режим бази перевірки')
    if mode=='historical_delta':return capture_target(view,version_id)
    scene_id=view.versions[version_id].scene_id
    baseline=build_author_baseline(view,scene_id)
    if view.versions[version_id].kind!='brief':
        from ..dependency_models import DependencySelector
        brief=view.peek_scene(scene_id).heads.get('brief')
        baseline.selectors.append(DependencySelector(kind='head',owner_id=scene_id,field='brief',expected=brief))
        if brief:baseline.refs[brief]=view.versions[brief].sha256
    return capture_target(view,version_id,baseline_override=baseline,current_sources_only=True)


def modes_for(view,targets):return {t.version_id:mode_for(view,t.version_id) for t in targets}


def plan_review(view):
    targets=[]
    for scene in view.peek_scenes(view.story.id):
        for material in ['brief','prose']:
            id=scene.heads.get(material)
            if not id:continue
            view.peek_version(id)  # The same KeyError as get_version for an absent head; no copy.
            if not (view.is_stale(id) or material=='prose' and view.effective_scene(scene.id).needs_review):continue
            t=capture(view,id)
            if t.text.strip():targets.append(t)
    return ImpactPlan(story_id=view.story.id,targets=targets,fingerprint=fingerprint([t.fingerprint for t in targets]))


def for_report(view,version_id,report):
    material='brief' if view.versions[version_id].kind=='brief' else 'prose'
    original=next(t for t in report.targets if t.material==material)
    mode=report.coverage.get('plan',{}).get('basis_modes',{}).get(original.version_id,'historical_delta')
    return capture(view,version_id,mode)


def validate_basis(plan):
    if 'basis_modes' not in plan:return  # Frozen older protocol3, no new interpretation.
    modes=plan['basis_modes']
    if not isinstance(modes,dict) or set(modes)!={t['version_id'] for t in plan['targets']} or any(not isinstance(m,str) or m not in MODES for m in modes.values()):raise ValueError('Некоректна карта баз перевірки')
    for t in plan['targets']:
        if modes[t['version_id']]=='current_consistency' and any(c['changed'] or c['old_text']!=c['new_text'] or c['old_ref']!=c['new_ref'] for c in t['changes']):
            raise ValueError('Поточна перевірка не може видавати невідому історію за дельту')
