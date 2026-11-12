"""MCP-BRIDGE package 3: a chat client writes the brief, edit and memory stages with the pipeline's own instructions,
and its answer goes through the same `execute_stage` as a model answer. No provider is called and nothing is billed."""
from ..generation.pipeline import STAGE_ROLES
from ..providers.models import ProviderSettings, RoleSettings

CHAT_STAGES=('brief','edit','memory')
# A typical chat window: the standard role default (8192 tokens) would not hold the edit of a long scene.
CHAT_CONTEXT_TOKENS=131072
CHAT_MAX_OUTPUT_TOKENS=8192


def chat_role_settings(repo,story_id: str,stage: str) -> RoleSettings:
    """The role settings the pipeline would use for this scene stage, or chat defaults for a role nobody configured."""
    if stage not in {'brief','draft','edit','memory'}:
        raise ValueError(f'Невідомий етап сцени: {stage}')
    from ..authoring.blueprints import get_role_settings
    role=get_role_settings(repo,story_id).get(STAGE_ROLES[stage])
    if role is not None:
        return role
    return RoleSettings(provider=ProviderSettings(model='external-chat'),memory_mode='evidence_delta',
                        context_tokens=CHAT_CONTEXT_TOKENS,max_output_tokens=CHAT_MAX_OUTPUT_TOKENS)

STALE_TASK='Завдання застаріло — візьміть його знову (get_stage_task)'
ALTERNATIVE='Сцену змінено під час запису; версія збережена в історії непоточною'
APPROVAL_REQUIRED='Попередня пам’ять потребує вашого підтвердження в Obscura: відкрийте сцену й підтвердьте використання пам’яті'
WARNING_KEYS=('memory_warnings','planner_warnings','editor_warnings','language_warnings')


class ExternalTextGateway:
    """Stands in for a provider: streams the chat's answer as one delta and stops. No `bind_accounting`, so nothing
    is billed; no usage, so no token observation."""

    def __init__(self,text: str):
        self.text=text

    def stream(self,context,cancel):
        from ..providers.streaming import GenerationEvent
        yield GenerationEvent(type='delta',text=self.text)
        yield GenerationEvent(type='terminal',finish_reason='stop')


class ChatStageRejected(ValueError):
    """The answer failed the stage's own parsing or checks; nothing became a version."""

    def __init__(self,message: str,details: dict):
        super().__init__(message)
        self.details=details


def _context(repo,scene_id: str,stage: str):
    if stage not in CHAT_STAGES:
        raise ValueError(f'Невідомий етап для чату: {stage}; оберіть один із {", ".join(CHAT_STAGES)}')
    from ..generation.context import build_context
    from ..memory.reuse import MemoryApprovalRequired
    from ..domain import RevisionConflict
    scene=repo.get_scene(scene_id)
    try:
        return build_context(repo,scene_id,stage,chat_role_settings(repo,scene.story_id,stage))
    except MemoryApprovalRequired as exc:
        raise RevisionConflict(APPROVAL_REQUIRED) from exc


def task_fingerprint(context) -> str:
    """The context fingerprint plus the target head (CAS): a second answer to the same task after the head moved is stale."""
    import hashlib
    target=context.target_cas.model_dump_json() if context.target_cas else ''
    return hashlib.sha256((context.fingerprint+'|'+target).encode('utf-8')).hexdigest()


def stage_task(repo,scene_id: str,stage: str,offset: int=0,max_chars: int=20000) -> dict:
    """MCP-BRIDGE-S40: the instructions and material of a stage exactly as the model would get them, in parts."""
    import hashlib
    context=_context(repo,scene_id,stage)
    material=context.user_text
    if offset<0 or offset>len(material):
        raise ValueError(f'Зсув поза матеріалом: 0…{len(material)}')
    end=min(len(material),offset+max_chars)
    return {'scene_id':scene_id,'stage':stage,'revision':context.scene_revision,'task_fingerprint':task_fingerprint(context),
            'instructions':context.system_text,'material':material[offset:end],'offset':offset,
            'next_offset':end if end<len(material) else None,'total_chars':len(material),
            'content_sha256':hashlib.sha256(material.encode('utf-8')).hexdigest(),
            'result_format':context.settings.edit_mode if stage=='edit' else 'json','warnings':list(context.context_warnings)}


def stage_result(repo,scene_id: str,stage: str,expected_fingerprint: str,text: str,external_origin) -> dict:
    """MCP-BRIDGE-S41–S44: the chat's answer through the same `execute_stage` as a model answer."""
    import threading
    from ..domain import RevisionConflict
    from ..generation.stages import execute_stage
    context=_context(repo,scene_id,stage)
    if task_fingerprint(context)!=expected_fingerprint:
        raise RevisionConflict(STALE_TASK)
    context=context.model_copy(update={'api_request':{}})
    attempt=execute_stage(repo,scene_id,stage,context,ExternalTextGateway(text),threading.Event(),lambda _:None,
                          external_origin=external_origin)
    warnings=[item for key in WARNING_KEYS for item in attempt.context.get(key) or []]
    if attempt.state=='failed':
        details={'warnings':warnings}
        for key in ('memory_violations','editor_failure','planner_failure'):
            if attempt.context.get(key):details[key]=attempt.context[key]
        raise ChatStageRejected(attempt.error or 'Відповідь не прийнято',details)
    if attempt.state=='alternative':
        raise RevisionConflict(ALTERNATIVE)
    scene=repo.get_scene(scene_id)
    result={'state':attempt.state,'version_id':attempt.result_version_id,'revision':scene.revision,'warnings':warnings}
    if attempt.state=='needs_review':
        result['message']=attempt.error
    return result
