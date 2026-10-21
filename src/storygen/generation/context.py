import hashlib
import json
import math
import re

from pydantic import Field

from ..dependency_models import DependencySnapshot, TargetCAS
from ..storage.snapshots import build_dependency_snapshot
from ..domain import DomainModel
from ..memory.service import journal_before
from ..memory.projection import project_memory, memory_catalog
from ..memory.journal import legacy_view
from ..providers.models import RoleSettings
from .models import StyleProfile
from .prompts import role_prompt
from ..characters.context import character_material
from ..characters.projection import OTHER_MATERIAL_WARNING


class ContextOverflow(ValueError):
    def __init__(self,estimated_tokens: int,limit: int,chars: int,memory_chars: int=0):
        self.estimated_tokens=estimated_tokens
        self.limit=limit
        self.chars=chars
        contribution=f' Проєкція пам’яті: {memory_chars} символів.' if memory_chars else ''
        super().__init__(f'Контекст завеликий: приблизно {estimated_tokens} токенів, доступно {limit}; {chars} символів. Текст не обрізано.'+contribution)


class ContextBundle(DomainModel):
    story_id: str
    scene_id: str | None
    stage: str
    dependency_snapshot: DependencySnapshot | None = None
    target_cas: TargetCAS | None = None
    scene_revision: int | None
    story_revision: int
    settings: RoleSettings
    system_text: str
    user_text: str
    input_refs: list[str]
    accepted_stale_prose_ids: list[str] = Field(default_factory=list)
    fingerprint: str
    estimated_tokens: int
    estimate_method: str = 'approximate_utf8_bytes_div_2_plus_overhead'
    fragments: dict[str,str] = Field(default_factory=dict)
    memory_metrics: dict = Field(default_factory=dict)
    context_warnings: list[str] = Field(default_factory=list)


def make_context(repo,story,scene,stage,settings,sections,refs,fragments=None,accepted_prose_ids=(),memory_metrics=None,context_warnings=None):
    if hasattr(repo, 'context_view'):
        repo=repo.context_view(story.id)
        story=repo.get_story(story.id)
        scene=repo.get_scene(scene.id) if scene else None
    prompt_id=settings.prepare_prompt_version_id if stage=='prepare' else settings.prompt_version_id
    if prompt_id:
        ref=repo.get_version(prompt_id)
        if ref.story_id!=story.id or ref.kind!='prompt':
            raise ValueError('Промпт не належить цьому твору')
        system=repo.read_text(ref.id)
        refs.append(ref.id)
    else:
        system=role_prompt(stage,settings)
    warnings=list(context_warnings or [])
    if prompt_id and stage in {'brief','draft','edit'} and OTHER_MATERIAL_WARNING not in warnings:
        warnings.append(OTHER_MATERIAL_WARNING)
    user='\n\n'.join(sections)
    chars=len(system)+len(user)
    estimate=math.ceil(len((system+user).encode('utf-8'))/2)+64
    limit=settings.context_tokens-settings.max_output_tokens
    if estimate>limit or chars>settings.max_input_chars:
        raise ContextOverflow(estimate,limit,chars,(memory_metrics or {}).get('projection_chars',(memory_metrics or {}).get('catalog_chars',0)))
    accepted_stale=[id for id in dict.fromkeys(accepted_prose_ids) if id in refs and (ref:=repo.get_version(id)).stale and ref.kind in {'edited','manual'}]
    fingerprint=hashlib.sha256(json.dumps({'system':system,'user':user,'settings':settings.model_dump(),'refs':refs,'accepted_stale_prose_ids':accepted_stale,'order':build_dependency_snapshot(repo,scene.id if scene else None,stage,settings,refs).scene_order},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    snapshot=build_dependency_snapshot(repo,scene.id if scene else None,stage,settings,refs)
    head={'brief':'brief','draft':'draft','edit':'prose','memory':'memory'}.get(stage)
    target=TargetCAS(scene_id=scene.id,head=head,version_id=scene.heads.get(head),head_revision=scene.head_revisions.get(head,0)) if scene and head else None
    return ContextBundle(dependency_snapshot=snapshot,target_cas=target,story_id=story.id,scene_id=scene.id if scene else None,stage=stage,scene_revision=scene.revision if scene else None,story_revision=story.revision,settings=settings,system_text=system,user_text=user,input_refs=list(dict.fromkeys(refs)),accepted_stale_prose_ids=accepted_stale,fingerprint=fingerprint,estimated_tokens=estimate,fragments=fragments or {},memory_metrics=memory_metrics or {},context_warnings=list(dict.fromkeys(warnings)))


def build_context(repo,scene_id: str,stage: str,settings: RoleSettings) -> ContextBundle:
    if stage not in {'brief','draft','edit','memory'}:
        raise ValueError('Невідомий етап сцени')
    scene=repo.get_scene(scene_id)
    if hasattr(repo, 'context_view'):
        repo=repo.context_view(scene.story_id)
        scene=repo.get_scene(scene_id)
    story=repo.get_story(scene.story_id)
    scenes=repo.list_scenes(story.id)
    refs=[]
    sections=[f'СЦЕНА {scene.position+1}/{len(scenes)}: {scene.title}\nЦільовий обсяг: {scene.target_words} слів.']
    def add(label,id):
        ref=repo.get_version(id)
        if (ref.stale and not (stage=='memory' and ref.kind in {'edited','manual'})) or not ref.complete:
            raise ValueError('Контекст містить застарілий матеріал; потрібне оновлення')
        refs.append(id)
        sections.append(f'{label} [version_id={id}]\n'+repo.read_text(id))
    if stage=='memory':
        past=journal_before(repo,scene.id)
        previous=[s for s in scenes if s.position<scene.position]
        prose_id=scene.heads.get('prose')
        if not prose_id:raise ValueError('Спершу виберіть завершену прозу')
        if repo.get_version(prose_id).kind not in {'edited','manual'}:
            raise ValueError('Пам’ять може спиратися лише на вибрану прозу')
        refs.extend(past.source_prose_ids)
        if previous:refs.append(previous[-1].heads['memory'])
        expected=past.source_prose_ids+[prose_id]
        if settings.memory_mode=='evidence_delta':
            from .evidence import render_fragments
            add('ПОТОЧНА ПРОЗА',prose_id)
            catalog=memory_catalog(past)
            sections=['ЧИННІ ТВЕРДЖЕННЯ — КАТАЛОГ ДЛЯ ОПЕРАЦІЙ\n'+catalog,
                'ДОЗВОЛЕНІ CHARACTER_IDS ДЛЯ НОВИХ СТАНІВ\n'+json.dumps(scene.character_ids,ensure_ascii=False),
                f'ПОТОЧНА ПРОЗА [version_id={prose_id}] — НУМЕРОВАНІ ФРАГМЕНТИ\n'+render_fragments(repo.read_text(prose_id))]
            return make_context(repo,story,scene,stage,settings,sections,refs,{'previous_memory':past.model_dump_json(),'expected_source_prose_ids':json.dumps(expected),'memory_allowed_character_ids':json.dumps(scene.character_ids)},accepted_prose_ids=expected,
                memory_metrics={'projection_version':'memory-catalog-v2','journal_chars':len(past.model_dump_json()),'catalog_chars':len(catalog),'event_count':len(past.events)})
        sections=['ПОПЕРЕДНЯ ПЕРЕВІРЕНА ПАМ’ЯТЬ\n'+legacy_view(past).model_dump_json(),
            'EXPECTED_SOURCE_PROSE_IDS — скопіюй цей список точно у source_prose_ids:\n'+json.dumps(expected)]
        add('ПОТОЧНА ПРОЗА — ЄДИНЕ ДЖЕРЕЛО НОВИХ ФАКТІВ',prose_id)
        return make_context(repo,story,scene,stage,settings,sections,refs,{'expected_source_prose_ids':json.dumps(expected),'previous_memory':past.model_dump_json()},accepted_prose_ids=expected)
    if stage=='edit' and settings.edit_mode=='patches':
        from .evidence import render_fragments
        draft_id=scene.heads.get('draft')
        if not draft_id:raise ValueError('Спершу створіть чернетку')
        add('ЧЕРНЕТКА',draft_id)
        sections=[f'ЧЕРНЕТКА [version_id={draft_id}] — НУМЕРОВАНІ ФРАГМЕНТИ\n'+render_fragments(repo.read_text(draft_id))]
        return make_context(repo,story,scene,stage,settings,sections,refs,{'copyedit_draft_id':draft_id})
    profile=StyleProfile()
    warnings=[]
    if story.style_version_id:
        add('ПРОФІЛЬ ПИСЬМА',story.style_version_id)
        profile=StyleProfile.model_validate_json(repo.read_text(story.style_version_id))
    if story.canon_version_id:
        add('АВТОРСЬКИЙ КАНОН',story.canon_version_id)
        warnings.append(OTHER_MATERIAL_WARNING)
    character_text,character_warnings,character_refs=character_material(repo,story,scene)
    if character_text:sections.append(character_text)
    warnings.extend(character_warnings);refs.extend(character_refs)
    source_plan=repo.active_source(story.id,'source_plan')
    if source_plan:
        text=repo.read_text(source_plan.id)
        heading=re.search(r'(?m)^\s*(?:#{1,6}\s*)?Сцена\s+\d+[.:]',text,re.IGNORECASE)
        preamble=text[:heading.start()].strip() if heading else ''
        if preamble:
            warnings.append(OTHER_MATERIAL_WARNING)
            refs.append(source_plan.id)
            sections.append(f'ГЛОБАЛЬНІ АВТОРСЬКІ ВКАЗІВКИ [version_id={source_plan.id}]\n'+preamble)
    # Author plans are explicitly future intentions, never evidence of completed events.
    for item in scenes:
        if item.position>=scene.position:
            if item.heads.get('plan'):
                add(f'МАЙБУТНІ ПОДІЇ — ПЛАН СЦЕНИ {item.position+1}',item.heads['plan'])
            else:
                sections.append(f'МАЙБУТНІ ПОДІЇ — ПЛАН СЦЕНИ {item.position+1}\n{item.beats}')
    past=journal_before(repo,scene.id)
    projection=project_memory(past,scene.character_ids,{s.heads['prose']:s.position+1 for s in scenes if s.position<scene.position and s.heads.get('prose')})
    sections.append('ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ\n'+projection.text)
    previous=[s for s in scenes if s.position<scene.position]
    fragments={}
    if previous:
        refs.extend(past.source_prose_ids)
        refs.append(previous[-1].heads['memory'])
        tail=repo.read_text(previous[-1].heads['prose'])[-profile.previous_tail_chars:] if profile.previous_tail_chars else ''
        fragments['previous_prose_tail']=tail
        sections.append('ЗАВЕРШЕННЯ ПОПЕРЕДНЬОЇ СЦЕНИ (явно вибраний фрагмент)\n'+tail)
    required={'brief':[],'draft':['brief'],'edit':['brief','draft'],'memory':['prose']}[stage]
    for head in required:
        if not scene.heads.get(head):
            raise ValueError('Спершу завершіть попередній етап: '+head)
        add({'brief':'ЗАВДАННЯ ПИСЬМЕННИКУ','draft':'ЧЕРНЕТКА ДЛЯ РЕДАКТУРИ','prose':'ПОТОЧНА ПРОЗА — ДЖЕРЕЛО НОВОЇ ПАМ’ЯТІ'}[head],scene.heads[head])
    return make_context(repo,story,scene,stage,settings,sections,refs,fragments,accepted_prose_ids=past.source_prose_ids,memory_metrics=projection.metrics,context_warnings=warnings)
