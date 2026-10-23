"""Portable configuration templates; never execute provider calls."""
import json
import re
from typing import Literal

from pydantic import Field, model_validator

from .domain import DomainModel, PromptContract, RevisionConflict
from .providers.models import RoleSettings
from .prompt_contracts import expected_contract, validate_role_prompt
from .evaluation.story_adapter import EvaluationSettings, validate_evaluation_settings

ROLES=('planner','writer','editor','memory')
STAGES=dict(zip(ROLES,('brief','draft','edit','memory')))
MAX_BYTES=2*1024*1024


class PortablePrompt(DomainModel):
    text: str | None = Field(default=None,max_length=100000)
    contract: PromptContract

    @model_validator(mode='after')
    def nonempty(self):
        if self.text is not None and not self.text.strip():
            raise ValueError('Власний промпт не може бути порожнім')
        return self


class PortableRole(DomainModel):
    settings: RoleSettings
    prompt: PortablePrompt
    prepare_prompt: PortablePrompt | None = None


class ProfileDocument(DomainModel):
    format: Literal['obscura-role-profile']='obscura-role-profile'
    schema_version: Literal[1]=1
    name: str = Field(min_length=1,max_length=100)
    roles: dict[str,PortableRole]
    evaluator: EvaluationSettings | None = None

    @model_validator(mode='after')
    def portable(self):
        self.name=self.name.strip()
        if not self.name or set(self.roles)!=set(ROLES):
            raise ValueError('Потрібна назва і рівно чотири основні ролі')
        providers=[]
        for name,role in self.roles.items():
            settings=role.settings
            if settings.prompt_version_id is not None or settings.prepare_prompt_version_id is not None:
                raise ValueError('UUID промптів не переноситься між творами')
            if role.prompt.contract!=expected_contract(STAGES[name],settings):
                raise ValueError('Несумісний контракт промпту профілю')
            if name=='planner':
                if role.prepare_prompt is None or role.prepare_prompt.contract!=expected_contract('prepare',settings):
                    raise ValueError('Потрібен контракт підготовки планувальника')
            elif role.prepare_prompt is not None:
                raise ValueError('Промпт підготовки дозволений лише планувальнику')
            providers.append(settings.provider.key_env)
            if settings.classification:providers.append(settings.classification.provider.key_env)
        if self.evaluator:
            profile=self.evaluator.profile
            if profile.calibrated or profile.evaluator_fingerprint or profile.calibration_fingerprint:
                raise ValueError('Профіль не переносить допуск калібрування')
            if self.evaluator.config.codex_command!='codex':
                raise ValueError('Переносимий профіль дозволяє лише стандартну команду Codex CLI')
            providers.append(self.evaluator.config.api_key_env)
        if any(value and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',value) for value in providers):
            raise ValueError('Потрібне ім’я змінної середовища, а не значення ключа')
        return self


def parse_profile(raw: str) -> ProfileDocument:
    if len(raw.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Файл профілю перевищує 2 MiB')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Повтор поля JSON')
            result[key]=value
        return result
    try:
        data=json.loads(raw,object_pairs_hook=unique)
        return ProfileDocument.model_validate(data)
    except (ValueError,RecursionError) as exc:
        raise ValueError('Некоректний профіль: перевірте схему, контракти, налаштування та відсутність секретів') from None


def _document(data):
    # Validate through the same safe boundary as imported documents.
    doc=parse_profile(json.dumps(data,ensure_ascii=False))
    return doc


def capture_profile(repo,story_id,name,expected_revision,include_evaluator=False,profile_id=None,expected_version=None):
    story=repo.get_story(story_id)
    if story.revision!=expected_revision:raise RevisionConflict('Налаштування твору вже змінено')
    settings=repo.read_role_settings(story_id)
    if set(settings)!=set(ROLES):raise ValueError('Спершу налаштуйте всі чотири ролі')
    roles={}
    for name_role in ROLES:
        role=RoleSettings.model_validate(settings[name_role])
        def portable(stage,id):
            validate_role_prompt(repo,story_id,stage,role)
            return {'text':repo.read_text(id) if id else None,'contract':expected_contract(stage,role).model_dump()}
        prompt=portable(STAGES[name_role],role.prompt_version_id)
        prepare=portable('prepare',role.prepare_prompt_version_id) if name_role=='planner' else None
        roles[name_role]={'settings':{**role.model_dump(),'prompt_version_id':None,'prepare_prompt_version_id':None},'prompt':prompt,'prepare_prompt':prepare}
    evaluator=None
    if include_evaluator:
        evaluator=repo.read_evaluator_settings(story_id)
        if evaluator is None:raise ValueError('Оцінювач не налаштовано')
        evaluator=EvaluationSettings.model_validate(evaluator).model_dump()
        evaluator['profile'].update(calibrated=False,evaluator_fingerprint=None,calibration_fingerprint=None)
    document=_document(dict(name=name,roles=roles,evaluator=evaluator))
    return repo.role_profiles('save',document=document.model_dump(),profile_id=profile_id,expected_version=expected_version,
                              source_story_id=story_id,source_revision=expected_revision)


def export_profile(repo,profile_id,version):
    item=repo.role_profiles('read',profile_id=profile_id,version=version)
    doc=_document(item['document'])
    return doc.model_dump_json(indent=2)


def preview_profile(repo,story_id,profile_id,version,expected_revision):
    story=repo.get_story(story_id)
    if story.revision!=expected_revision:raise RevisionConflict('Налаштування твору вже змінено')
    item=repo.role_profiles('read',profile_id=profile_id,version=version)
    doc=_document(item['document'])
    warnings=[]
    if doc.evaluator:
        validate_evaluation_settings(repo,doc.evaluator.model_copy(deep=True))
        from .evaluation.blocks import get_block
        block=get_block(repo,story_id,doc.evaluator.config)
        warnings.append('Evaluator переноситься без допуску калібрування; наявні блокування твору зберігаються.')
        if block:warnings.append('Оцінювач уже заблоковано для цього оповідання; застосування не зніме блокування.')
    return {'id':profile_id,'version':version,'name':doc.name,'expected_revision':expected_revision,
            'roles':{key:value.settings.model_dump() for key,value in doc.roles.items()},
            'evaluator':doc.evaluator.model_dump() if doc.evaluator else None,
            'prompts':{key:{'prompt':value.prompt.model_dump(),'prepare_prompt':value.prepare_prompt.model_dump() if value.prepare_prompt else None} for key,value in doc.roles.items()},
            'warnings':warnings}


def apply_profile(repo,story_id,profile_id,version,expected_revision):
    preview_profile(repo,story_id,profile_id,version,expected_revision)
    doc=_document(repo.role_profiles('read',profile_id=profile_id,version=version)['document'])
    updates={}
    for key,item in doc.roles.items():
        role=item.settings.model_copy(deep=True)
        for field,prompt in [('prompt_version_id',item.prompt),('prepare_prompt_version_id',item.prepare_prompt)]:
            if prompt and prompt.text is not None:
                ref=repo.save_version(story_id,None,'prompt',prompt.text,[],prompt_contract=prompt.contract)
                setattr(role,field,ref.id)
        updates[key]=role.model_dump()
    return repo.role_profiles('apply',story_id=story_id,profile_id=profile_id,version=version,
        expected_revision=expected_revision,roles=updates,evaluator=doc.evaluator.model_dump() if doc.evaluator else None)
