import math
from typing import Literal

from pydantic import Field

from ..domain import DomainModel, StageAttempt, new_id
from ..generation.worker import RunRequest
from .gateway import GatewayFailure
from .models import Coverage, Document, EvaluationCase, EvaluationOutcome, EvaluatorConfig, ScoringProfile
from .prompting import build_request, load_rubric
from .runner import evaluate, evaluator_fingerprint, fingerprint_inputs, digest


class EvaluationSettings(DomainModel):
    config: EvaluatorConfig
    context_tokens: int = Field(default=32768,ge=1024)
    profile: ScoringProfile = Field(default_factory=lambda:ScoringProfile(version='candidate-v1'))
    policy: Literal['off','report','pause_on_failure'] = 'report'


def save_evaluation_settings(repo,story_id,settings):
    repo.get_story(story_id)
    if settings.profile.calibrated:
        # Calibration is installed by the server only after independently checking full reports.
        with repo.db.connection() as db:
            row=db.execute('SELECT payload FROM app_settings WHERE key=?',('calibration:'+settings.profile.calibration_fingerprint,)).fetchone()
        import json
        if not row or json.loads(row[0]).get('profile')!=settings.profile.model_dump() or settings.profile.evaluator_fingerprint!=evaluator_fingerprint(settings.config,load_rubric()):
            raise ValueError('Немає перевіреного повного калібрування для цього оцінювача')
    if settings.policy=='pause_on_failure' and not settings.profile.calibrated:
        raise ValueError('Потрібен профіль успішного калібрування')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        repo._active_story(db,story_id)
        db.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)',('evaluation:'+story_id,settings.model_dump_json()))


def get_evaluation_settings(repo,story_id):
    with repo.db.connection() as db:
        row=db.execute('SELECT payload FROM app_settings WHERE key=?',('evaluation:'+story_id,)).fetchone()
    if not row:
        raise ValueError('Оцінювач не налаштовано')
    return EvaluationSettings.model_validate_json(row[0])


def install_calibration(repo,config: EvaluatorConfig,outcomes: list) -> ScoringProfile:
    import json
    from .calibration import calibrate
    from .inputs import parse_json
    from .prompting import resource_text
    from .runner import digest
    suite=parse_json(resource_text('calibration_suite_v1.json'))
    cases=[EvaluationCase.model_validate(c) for c in suite['cases']]
    metrics=calibrate(cases,suite['expectations'],outcomes,required_repeats=3)
    fingerprint=evaluator_fingerprint(config,load_rubric())
    if not config.model or not metrics['eligible'] or any(o.metadata['evaluator_fingerprint']!=fingerprint for o in outcomes):
        raise ValueError('Повний контрольний набір не пройшов критерії калібрування')
    candidate=ScoringProfile.model_validate(outcomes[0].metadata['snapshots']['profile'])
    if candidate.calibrated:raise ValueError('Контрольний набір має оцінювати початковий candidate-профіль')
    calibration_id=digest({'expectations':suite['expectations'],'outcomes':[o.model_dump() for o in outcomes]})
    profile=candidate.model_copy(update={'calibrated':True,'evaluator_fingerprint':fingerprint,'calibration_fingerprint':calibration_id})
    payload={'profile':profile.model_dump(),'metrics':metrics,'run_ids':[o.metadata['run_id'] for o in outcomes]}
    repo.files.write('calibrations/'+calibration_id+'.json',json.dumps({'registration':payload,'outcomes':[o.model_dump() for o in outcomes]},ensure_ascii=False).encode())
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)',('calibration:'+calibration_id,json.dumps(payload,ensure_ascii=False)))
    return profile


def build_evaluation_case(repo,story_id: str,scene_id: str | None,mode: str) -> EvaluationCase:
    story=repo.get_story(story_id)
    scenes=repo.list_scenes(story_id)
    docs=[];targets=[];unchecked=[]
    def add(id,kind):
        if id not in {d.id for d in docs}:
            ref=repo.get_version(id)
            if ref.stale:unchecked.append('Застаріле джерело: '+id)
            docs.append(Document(id=id,version=id,kind=kind,text=repo.read_text(id)))
    if story.canon_version_id:add(story.canon_version_id,'canon')
    if story.style_version_id:add(story.style_version_id,'canon')
    if story.characters_version_id:
        add(story.characters_version_id,'canon')
    else:
        source=repo.active_source(story.id,'source_characters')
        if source:add(source.id,'canon')
    if mode=='story':
        expected=[]
        for scene in scenes:
            if scene.heads.get('plan'):add(scene.heads['plan'],'plan')
            else:unchecked.append('Немає версійованого плану сцени '+scene.id)
            id=scene.heads.get('prose')
            expected.append(id or scene.id)
            if id:add(id,'scene');targets.append(id)
            else:unchecked.append('Немає поточної прози сцени '+scene.id)
    else:
        scene=next((s for s in scenes if s.id==scene_id),None)
        if not scene or not scene.heads.get('prose'):
            raise ValueError('Потрібна вибрана проза сцени цього твору')
        if scene.heads.get('plan'):add(scene.heads['plan'],'plan')
        else:unchecked.append('Немає версійованого плану сцени '+scene.id)
        if scene.heads.get('brief'):add(scene.heads['brief'],'brief')
        if mode=='edit_pair':
            if not scene.heads.get('draft'):raise ValueError('Немає чернетки для порівняння')
            add(scene.heads['draft'],'draft');targets.append(scene.heads['draft'])
        previous=[s for s in scenes if s.position<scene.position]
        if previous and previous[-1].heads.get('prose'):add(previous[-1].heads['prose'],'scene')
        add(scene.heads['prose'],'revision' if mode=='edit_pair' else 'scene');targets.append(scene.heads['prose'])
        expected=targets.copy()
    if not targets:raise ValueError('Немає текстів для оцінювання')
    identity=digest({'story_id':story_id,'scene_id':scene_id,'mode':mode,'versions':[d.version for d in docs]})
    return EvaluationCase(id='story-'+identity,mode={'edit_pair':'revision'}.get(mode,mode),documents=docs,target_ids=targets,coverage=Coverage(expected_scene_ids=expected,unchecked_links=unchecked))


def plan_evaluation_windows(repo,story_id: str,config: EvaluatorConfig):
    whole=build_evaluation_case(repo,story_id,None,'story')
    if sum(len(m['content']) for m in build_request(whole,load_rubric(),config).messages)<=config.max_input_chars:
        return [whole]
    windows=[]
    for scene in repo.list_scenes(story_id):
        if not scene.heads.get('prose'):continue
        case=build_evaluation_case(repo,story_id,scene.id,'scene')
        case.coverage.unchecked_links.append('Перевірено вікно: далекі міжсценові зв’язки й увесь твір разом не перевірено')
        windows.append(case)
    return windows


def queue_evaluation(coordinator,story_id,scene_id,mode,request_id):
    return coordinator.enqueue(RunRequest(story_id=story_id,scene_id=scene_id,mode='evaluate',evaluation_mode=mode),request_id)


def execute_evaluation(coordinator,run):
    repo=coordinator.repo
    settings=get_evaluation_settings(repo,run.story_id)
    if settings.policy=='off':raise ValueError('Оцінювання вимкнено')
    task=run.tasks[run.cursor]
    scene_id=task.get('scene_id')
    mode=task.get('evaluation_mode',run.request.evaluation_mode)
    cases=plan_evaluation_windows(repo,run.story_id,settings.config) if mode=='story' else [build_evaluation_case(repo,run.story_id,scene_id,mode)]
    refs=[];outcomes=[]
    disabled=False
    gateway=None
    try:
        for index,case in enumerate(cases):
            if coordinator.cancel_event.is_set():break
            if get_evaluation_settings(repo,run.story_id).policy=='off':
                disabled=True
                coordinator.event(run.id,'evaluation_skipped',{'reason':'Оцінювач вимкнено; наступні вікна не надсилаються','completed_windows':len(outcomes)})
                break
            request=build_request(case,load_rubric(),settings.config)
            estimate=math.ceil(sum(len(m['content'].encode('utf-8')) for m in request.messages)/2)+64
            if estimate+settings.config.max_output_tokens>settings.context_tokens:
                raise ValueError('Оцінювачеві бракує контексту; змініть модель або явний бюджет')
            revision=repo.get_story(run.story_id).revision
            fingerprint=fingerprint_inputs(case,load_rubric(),settings.profile,settings.config)
            checkpoint=digest({'cursor':run.cursor,'window':index,'fingerprint':fingerprint})
            prior=next((a for a in reversed(repo.list_attempts(run.story_id,run.id)) if a.stage=='evaluate' and a.context.get('checkpoint_key')==checkpoint and a.state=='completed' and a.result_version_id and not repo.get_version(a.result_version_id).stale),None)
            if prior:
                outcome=EvaluationOutcome.model_validate_json(repo.read_text(prior.result_version_id))
                outcomes.append(outcome);refs.append(prior.result_version_id)
                coordinator.event(run.id,'reused',{'attempt_id':prior.id,'stage':'evaluate','window':index})
                continue
            id=new_id()
            attempt=StageAttempt(id=id,run_id=run.id,story_id=run.story_id,scene_id=scene_id,stage='evaluate',partial_path=f'stories/{run.story_id}/runs/{id}/partial.txt',context={'story_revision':revision,'run_cursor':run.cursor,'checkpoint_key':checkpoint,'fingerprint':fingerprint,'window_index':index,'case':case.model_dump(),'config':settings.config.model_dump(),'profile':settings.profile.model_dump(),'request':request.model_dump()})
            repo.save_attempt(attempt)
            repo.files.write(attempt.partial_path,b'')
            coordinator.event(run.id,'stage_started',{'stage':'evaluate','model':settings.config.model,'provider':settings.config.provider,'estimated_tokens':estimate})
            if gateway is None:gateway=coordinator.evaluator_factory(settings.config)
            class RecordingGateway:
                def complete(self,request):
                    try:
                        result=gateway.complete(request)
                    except GatewayFailure as exc:
                        if exc.result is not None:repo.files.write(attempt.partial_path,(exc.result.text or exc.result.refusal or '').encode())
                        raise
                    repo.files.write(attempt.partial_path,(result.text or result.refusal or '').encode())
                    return result
            outcome=evaluate(case,load_rubric(),settings.profile,settings.config,RecordingGateway(),repo.root/'stories'/run.story_id/'runs'/run.id/'evaluations')
            inputs=[d.version for d in case.documents]
            ref=repo.save_version(run.story_id,scene_id,'evaluation',outcome.model_dump_json(),inputs,run.id)
            # Changes during the model call must stale this report even if invalidation happened before its insert.
            if any(repo.get_version(id).stale for id in inputs) or repo.get_story(run.story_id).revision!=revision:
                ref.stale=True
                with repo.db.connection() as db:db.execute('UPDATE versions SET payload=? WHERE id=?',(ref.model_dump_json(),ref.id))
            refs.append(ref.id);outcomes.append(outcome)
            repo.files.write(attempt.partial_path,outcome.metadata['raw_response'].encode())
            attempt.result_version_id=ref.id
            attempt.usage=outcome.metadata.get('usage',{})
            attempt.state='alternative' if ref.stale else 'failed' if outcome.status=='error' else 'completed'
            attempt.error='Оцінка неповна через помилку провайдера' if attempt.state=='failed' else None
            repo.save_attempt(attempt)
            coordinator.event(run.id,'evaluation_finished',{'version_id':ref.id,'status':outcome.status,'stale':ref.stale,'coverage':case.coverage.model_dump()})
            if attempt.state in {'failed','alternative'}:break
    finally:
        if gateway and hasattr(gateway,'close'):gateway.close()
    with coordinator.condition:
        current=coordinator.get_run(run.id)
        if coordinator.cancel_event.is_set():current.state='cancelled'
        elif disabled:current.state='running';current.cursor+=1
        elif len(outcomes)!=len(cases) or any(o.status=='error' for o in outcomes):current.state='failed'
        elif any(repo.get_version(id).stale for id in refs):current.state='alternative'
        elif settings.policy=='pause_on_failure' and any(o.status!='passed' for o in outcomes):current.state='paused';current.cursor+=1
        elif current.state=='pause_requested':current.state='paused';current.cursor+=1
        else:current.state='running';current.cursor+=1
        coordinator._save(current);coordinator.event(run.id,'state',{'state':current.state})
