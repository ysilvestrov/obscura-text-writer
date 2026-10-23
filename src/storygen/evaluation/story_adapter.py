from typing import Literal

from pydantic import Field

from ..domain import DomainModel, StageAttempt, new_id
from ..generation.worker import RunRequest
from .models import Coverage, Document, EvaluationCase, EvaluationOutcome, EvaluatorConfig, ScoringProfile
from .prompting import build_request, load_rubric
from .runner import evaluate, evaluator_fingerprint, fingerprint_inputs, digest
from .blocks import get_block, block_evaluator, blocked_message, require_available
from ..run_models import merge_warnings


class EvaluationSettings(DomainModel):
    config: EvaluatorConfig
    context_tokens: int = Field(default=32768,ge=1024)
    profile: ScoringProfile = Field(default_factory=lambda:ScoringProfile(version='candidate-v1'))
    policy: Literal['off','report','pause_on_failure'] = 'report'


def save_evaluation_settings(repo,story_id,settings):
    repo.get_story(story_id)
    validate_evaluation_settings(repo,settings)
    repo.write_evaluator_settings(story_id,settings.model_dump())


def validate_evaluation_settings(repo,settings):
    if settings.profile.calibrated:
        # Calibration is installed by the server only after independently checking full reports.
        registration=repo.read_calibration(settings.profile.calibration_fingerprint)
        if not registration or registration.get('profile')!=settings.profile.model_dump():
            raise ValueError('Немає перевіреного повного калібрування для цього оцінювача')
        if settings.profile.evaluator_fingerprint!=evaluator_fingerprint(settings.config,load_rubric()):
            settings.profile = settings.profile.model_copy(update={'calibrated': False})
    if settings.policy=='pause_on_failure' and not settings.profile.calibrated:
        raise ValueError('Потрібен профіль успішного калібрування')
    return settings


def get_evaluation_settings(repo,story_id):
    payload=repo.read_evaluator_settings(story_id)
    if payload is None:
        raise ValueError('Оцінювач не налаштовано')
    settings = EvaluationSettings.model_validate(payload)
    if settings.profile.calibrated and settings.profile.evaluator_fingerprint != evaluator_fingerprint(settings.config, load_rubric()):
        settings.profile = settings.profile.model_copy(update={'calibrated': False})
    return settings


def install_calibration(repo,config: EvaluatorConfig,outcomes: list) -> ScoringProfile:
    import json
    from .calibration import calibrate
    from .inputs import parse_json
    from .prompting import resource_text
    from .runner import digest
    from .suites import canonical_suite, canonical_suite_hash
    suite=canonical_suite()
    cases=[EvaluationCase.model_validate(c) for c in suite['cases']]
    metrics=calibrate(cases,suite['expectations'],outcomes,required_repeats=3)
    fingerprint=evaluator_fingerprint(config,load_rubric())
    if not config.model or not metrics['eligible'] or any(o.metadata['evaluator_fingerprint']!=fingerprint for o in outcomes):
        raise ValueError('Повний контрольний набір не пройшов критерії калібрування')
    candidate=ScoringProfile.model_validate(outcomes[0].metadata['snapshots']['profile'])
    if candidate.calibrated:raise ValueError('Контрольний набір має оцінювати початковий candidate-профіль')
    calibration_id=digest({'expectations':suite['expectations'],'outcomes':[o.model_dump() for o in outcomes]})
    profile=candidate.model_copy(update={'calibrated':True,'evaluator_fingerprint':fingerprint,'calibration_fingerprint':calibration_id})
    payload={'profile':profile.model_dump(),'metrics':metrics,'run_ids':[o.metadata['run_id'] for o in outcomes],
        'suite_version': suite['version'], 'suite_hash': canonical_suite_hash(), 'categories': suite['categories'],
        'evaluator_fingerprint': fingerprint, 'required_repeats': 3}
    repo.files.write('calibrations/'+calibration_id+'.json',json.dumps({'registration':payload,'outcomes':[o.model_dump() for o in outcomes]},ensure_ascii=False).encode())
    repo.register_calibration(calibration_id,payload)
    return profile


def build_evaluation_case(repo,story_id: str,scene_id: str | None,mode: str) -> EvaluationCase:
    if hasattr(repo,'context_view'):
        repo=repo.context_view(story_id)
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
    from ..characters.context import character_material
    cast_scenes=scenes if mode=='story' else [s for s in scenes if s.id==scene_id]
    cast_text=[]
    for cast_scene in cast_scenes:
        text,warnings,_=character_material(repo,story,cast_scene)
        unchecked.extend(w for w in warnings if w not in unchecked)
        if text and text not in cast_text:cast_text.append(text)
    if cast_text:
        docs.append(Document(id=story.characters_version_id,version=story.characters_version_id,
            kind='canon',text='\n\n'.join(cast_text)))
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
    if hasattr(repo,'context_view'):
        repo=repo.context_view(story_id)
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
    existing_block = get_block(repo, run.story_id, settings.config)
    if existing_block:
        with coordinator.condition:
            current = coordinator.get_run(run.id)
            current.error = blocked_message(existing_block)
            current.warning = merge_warnings(current.warning,[current.error])
            if settings.policy == 'report':
                current.cursor += 1
                current.state = 'running'
            else:
                current.state = 'paused'
            coordinator._save(current)
            coordinator.event(run.id, 'evaluation_skipped', {'reason': current.error, 'block': existing_block})
            coordinator.event(run.id, 'state', {'state': current.state, 'warning': current.error})
        return
    task=run.tasks[run.cursor]
    scene_id=task.get('scene_id')
    mode=task.get('evaluation_mode',run.request.evaluation_mode)
    view=repo.context_view(run.story_id)
    cases=plan_evaluation_windows(view,run.story_id,settings.config) if mode=='story' else [build_evaluation_case(view,run.story_id,scene_id,mode)]
    refs=[];outcomes=[]
    disabled=False
    blocked=False
    gateway=None
    try:
        for index,case in enumerate(cases):
            if coordinator.cancel_event.is_set():break
            current_block = get_block(repo, run.story_id, settings.config)
            if current_block:
                blocked = True
                coordinator.event(run.id, 'evaluation_skipped', {'reason': blocked_message(current_block), 'unchecked_windows': len(cases)-index})
                break
            if get_evaluation_settings(repo,run.story_id).policy=='off':
                disabled=True
                coordinator.event(run.id,'evaluation_skipped',{'reason':'Оцінювач вимкнено; наступні вікна не надсилаються','completed_windows':len(outcomes)})
                break
            request=build_request(case,load_rubric(),settings.config)
            from ..providers.requests import evaluation_request
            from ..token_budget.service import token_estimate,record_usage
            api_request=evaluation_request(settings.config,request)
            # Source texts stay frozen, but each next window sees drift/activation updates.
            prediction=token_estimate(repo,settings.config.provider,settings.config.base_url,api_request)
            estimate=prediction['input_tokens']
            if estimate+settings.config.max_output_tokens>settings.context_tokens:
                raise ValueError('Оцінювачеві бракує контексту; змініть модель або явний бюджет')
            from ..storage.snapshots import build_evaluation_snapshot
            windowed=mode=='story' and case.mode!='story'
            target_scene=next((view.get_version(id).scene_id for id in case.target_ids if view.get_version(id).scene_id),None) if windowed else scene_id
            snapshot=build_evaluation_snapshot(view,target_scene,case,'scene' if windowed else mode)
            revision=view.get_story(run.story_id).revision
            fingerprint=fingerprint_inputs(case,load_rubric(),settings.profile,settings.config)
            checkpoint=digest({'cursor':run.cursor,'window':index,'fingerprint':fingerprint})
            prior=next((a for a in reversed(repo.list_attempts(run.story_id,run.id)) if a.stage=='evaluate' and a.context.get('checkpoint_key')==checkpoint and a.state=='completed' and a.result_version_id and not repo.get_version(a.result_version_id).stale),None)
            if prior:
                outcome=EvaluationOutcome.model_validate_json(repo.read_text(prior.result_version_id))
                outcomes.append(outcome);refs.append(prior.result_version_id)
                coordinator.event(run.id,'reused',{'attempt_id':prior.id,'stage':'evaluate','window':index})
                continue
            id=new_id()
            attempt=StageAttempt(id=id,run_id=run.id,story_id=run.story_id,scene_id=scene_id,stage='evaluate',partial_path=f'stories/{run.story_id}/runs/{id}/partial.txt',context={'story_revision':revision,'dependency_snapshot':snapshot.model_dump(),'run_cursor':run.cursor,'checkpoint_key':checkpoint,'fingerprint':fingerprint,'window_index':index,'case':case.model_dump(),'config':settings.config.model_dump(),'profile':settings.profile.model_dump(),'request':request.model_dump()})
            attempt.context.update(api_request=api_request,token_estimate=prediction)
            repo.save_attempt(attempt)
            repo.files.write(attempt.partial_path,b'')
            coordinator.event(run.id,'stage_started',{'stage':'evaluate','scene_id':scene_id,'run_cursor':run.cursor,'model':settings.config.model,'provider':settings.config.provider,'estimated_tokens':estimate})
            class LazyGateway:
                def complete(self,request):
                    nonlocal gateway
                    require_available(repo, run.story_id, settings.config)
                    if gateway is None:gateway=coordinator.evaluator_factory(settings.config)
                    if hasattr(gateway,'bind_accounting'):
                        from ..providers.accounting import CallAccounting
                        gateway.bind_accounting(CallAccounting(repo,'story:'+run.story_id,run.id,attempt.id,attempt.id,run.request.budget_limit_usd))
                    return gateway.complete(request)
            outcome=evaluate(case,load_rubric(),settings.profile,settings.config,LazyGateway(),repo.root/'stories'/run.story_id/'runs'/run.id/'evaluations',
                on_refusal=lambda failure: block_evaluator(repo, run.story_id, settings.config, failure, run.id, attempt.id),
                on_raw=lambda raw: repo.files.write(attempt.partial_path, raw.encode('utf-8')),token_prediction=prediction)
            if outcome.status == 'refused':
                blocked = True
            inputs=[d.version for d in case.documents]
            ref=repo.save_version(run.story_id,scene_id,'evaluation',outcome.model_dump_json(),inputs,run.id)
            ref=repo.publish_evaluation(ref.id,revision,inputs,snapshot=snapshot)
            refs.append(ref.id);outcomes.append(outcome)
            attempt.result_version_id=ref.id
            attempt.usage=outcome.metadata.get('usage',{})
            if settings.config.provider!='codex_cli':
                try:
                    record_usage(repo,settings.config.provider,settings.config.base_url,api_request,attempt.usage,attempt.id)
                except Exception:
                    attempt.context['token_observation_warning']='Не вдалося зберегти token usage; первинні дані лишилися у спробі.'
            attempt.state='alternative' if ref.stale else 'completed'
            attempt.error=outcome.failure.message if outcome.failure else None
            repo.save_attempt(attempt)
            coordinator.event(run.id,'evaluation_finished',{'version_id':ref.id,'status':outcome.status,'stale':ref.stale,'coverage':case.coverage.model_dump()})
            if outcome.status in {'refused', 'error', 'incomplete'}:
                coordinator.event(run.id, 'evaluation_warning', {'status': outcome.status, 'failure': outcome.failure.model_dump() if outcome.failure else None, 'reasons': outcome.reasons})
            if attempt.state=='alternative' or blocked:break
    finally:
        if gateway and hasattr(gateway,'close'):gateway.close()
    with coordinator.condition:
        current=coordinator.get_run(run.id)
        warnings = [o.failure.message if o.failure else '; '.join(o.reasons) for o in outcomes if o.status in {'error', 'refused', 'incomplete'}]
        if warnings:
            current.warning = merge_warnings(current.warning,['Оцінювання не підтверджене: ' + '; '.join(dict.fromkeys(warnings))])
        if coordinator.cancel_event.is_set():current.state='cancelled'
        elif disabled:current.state='running';current.cursor+=1
        elif any(repo.get_version(id).stale for id in refs):current.state='alternative'
        elif blocked:
            current.error=blocked_message(get_block(repo, run.story_id, settings.config))
            current.state='paused' if settings.policy=='pause_on_failure' else 'running'
            if current.state=='running':current.cursor+=1
            coordinator.event(run.id, 'evaluation_skipped', {'reason': current.error, 'unchecked_windows': len(cases)-len(outcomes)})
        elif len(outcomes)!=len(cases):current.state='failed'
        elif settings.policy=='pause_on_failure' and any(o.status!='passed' for o in outcomes):current.state='paused';current.cursor+=1
        elif current.state=='pause_requested':current.state='paused';current.cursor+=1
        else:current.state='running';current.cursor+=1
        coordinator._save(current);coordinator.event(run.id,'state',{'state':current.state, 'warning': current.warning})
