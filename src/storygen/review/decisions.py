"""Explicit author decisions with preview CAS and idempotent operation records."""
from ..domain import RevisionConflict
from ..impact.models import fingerprint
from .capture import for_report
from .store import publish_scene


def _preview(repo,view,run):
    if run.story_id!=view.story.id or not run.impact or run.impact.get('protocol')!=3:raise ValueError('Запуск належить іншому твору або протоколу')
    data=run.impact
    report=view.review_reports.get(data.get('current_report_id'))
    if not report:return dict(run_id=run.id,state=run.state,phase=data['phase'],report=None,fingerprint=None)
    if report.run_id!=run.id:raise ValueError('Звіт належить іншому запуску')
    scene=view.get_scene(report.scene_id)
    if data['scene_cursor']>=len(data['scene_order']) or data['scene_order'][data['scene_cursor']]!=scene.id:raise RevisionConflict('Поточна сцена змінилася')
    if [s.id for s in view.list_scenes(run.story_id)]!=data['scene_order']:raise RevisionConflict('Порядок сцен змінився')
    targets=[]
    for old in report.targets:
        id=scene.heads.get(old.material)
        if not id:raise ValueError('Матеріал сцени відсутній')
        t=for_report(view,id,report)
        if t.blockers:raise ValueError('; '.join(t.blockers))
        targets.append(t)
    basis=dict(report_id=report.id,phase=data['phase'],scene_cursor=data['scene_cursor'],targets=[t.fingerprint for t in targets],dispositions=data.get('dispositions',{}))
    changed=data['phase']=='awaiting_author' and [t.fingerprint for t in targets]!=[t.fingerprint for t in report.targets]
    if report.schema_version==4:
        from ..storage.review_authority import revision
        changed=changed or any(revision(view,scene.id,t.material)!=report.authority_revisions.get(t.material,0) for t in targets)
    return dict(run_id=run.id,state=run.state,phase=data['phase'],scene_id=scene.id,report=report.model_dump(),targets=[t.model_dump() for t in targets],dispositions=data.get('dispositions',{}),fingerprint=fingerprint(basis),changed_while_waiting=changed,automatic_acceptance_allowed=report.schema_version==3)


def preview(repo,story_id,run_id):
    run=repo.get_run(run_id)
    if run.story_id!=story_id:raise ValueError('Запуск належить іншому твору')
    return _preview(repo,repo.context_view(story_id),run)


def _saved(repo,story_id,operation_id,command):
    data=repo.review('operation',story_id=story_id,operation_id=operation_id)
    if data is None:return None
    if data.get('command')!=command:raise ValueError('ID рішення вже використаний з іншими даними')
    return dict(state='queued',**data['result']) if data['result'].get('acceptances') else data['result']


def _command(worker,story_id,run_id,expected,operation_id,choices,action):
    if not operation_id or len(operation_id)>200:raise ValueError('Потрібен ID рішення до 200 символів')
    repo=worker.repo;run=repo.get_run(run_id)
    if run.story_id!=story_id:raise ValueError('Запуск належить іншому твору')
    command=dict(run_id=run_id,expected=expected,choices=choices,action=action)
    saved=_saved(repo,story_id,operation_id,command)
    if saved is not None:return saved
    with worker.condition:
        p=preview(repo,story_id,run_id)
        if p['fingerprint']!=expected:raise RevisionConflict('Матеріали або рішення змінилися; перегляньте актуальну сцену')
        if p['state']!='needs_review' or p['phase'] not in {'awaiting_author','author_editing'}:raise ValueError('Перевірка не очікує авторського рішення')
        if p.get('changed_while_waiting'):raise RevisionConflict('Передумови або текст поточної сцени змінилися; створіть нову перевірку')
        ids={c['id'] for c in p['report']['concerns']}
        if action=='decide':
            if set(choices)!=ids or any(v not in {'reject','fix'} for v in choices.values()):raise ValueError('Оберіть рішення для кожного зауваження')
        elif action=='finish':
            if p['phase']!='author_editing':raise ValueError('Спершу оберіть зауваження для виправлення')
            choices=p['dispositions']
        if action=='decide' and any(v=='fix' for v in choices.values()):
            return repo.review('save_dispositions',run_id=run_id,expected=expected,operation_id=operation_id,command=command,choices=choices)
        from .models4 import report_model
        from ..impact.models import ImpactTarget
        result=publish_scene(repo,run_id,report_model(p['report']).model_validate(p['report']),'author_revised' if action=='finish' else 'author_rejected',operation_id,
            accepted_targets=[ImpactTarget.model_validate(t) for t in p['targets']],dispositions=choices,command=command)
        worker.event(run_id,'state',dict(state='queued'));worker.condition.notify_all()
        return dict(state='queued',**result)


def decide(worker,story_id,run_id,expected,operation_id,choices):
    return _command(worker,story_id,run_id,expected,operation_id,choices,'decide')


def finish(worker,story_id,run_id,expected,operation_id):
    return _command(worker,story_id,run_id,expected,operation_id,{},'finish')
