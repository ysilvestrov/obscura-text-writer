import hashlib
import json
import math
import re

from pydantic import Field

from ..domain import DomainModel
from ..memory.service import memory_before
from ..providers.models import RoleSettings
from .models import StyleProfile
from .prompts import role_prompt


class ContextOverflow(ValueError):
    def __init__(self,estimated_tokens: int,limit: int,chars: int):
        self.estimated_tokens=estimated_tokens
        self.limit=limit
        self.chars=chars
        super().__init__(f'Контекст завеликий: приблизно {estimated_tokens} токенів, доступно {limit}; {chars} символів. Текст не обрізано.')


class ContextBundle(DomainModel):
    story_id: str
    scene_id: str | None
    stage: str
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


def make_context(repo,story,scene,stage,settings,sections,refs,fragments=None,accepted_prose_ids=()):
    prompt_id=settings.prepare_prompt_version_id if stage=='prepare' else settings.prompt_version_id
    if prompt_id:
        ref=repo.get_version(prompt_id)
        if ref.story_id!=story.id or ref.kind!='prompt':
            raise ValueError('Промпт не належить цьому твору')
        system=repo.read_text(ref.id)
        refs.append(ref.id)
    else:
        system=role_prompt(stage,settings)
    user='\n\n'.join(sections)
    chars=len(system)+len(user)
    estimate=math.ceil(len((system+user).encode('utf-8'))/2)+64
    limit=settings.context_tokens-settings.max_output_tokens
    if estimate>limit or chars>settings.max_input_chars:
        raise ContextOverflow(estimate,limit,chars)
    accepted_stale=[id for id in dict.fromkeys(accepted_prose_ids) if id in refs and (ref:=repo.get_version(id)).stale and ref.kind in {'edited','manual'}]
    fingerprint=hashlib.sha256(json.dumps({'system':system,'user':user,'settings':settings.model_dump(),'refs':refs,'accepted_stale_prose_ids':accepted_stale,'order':[s.id for s in repo.list_scenes(story.id)]},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return ContextBundle(story_id=story.id,scene_id=scene.id if scene else None,stage=stage,scene_revision=scene.revision if scene else None,story_revision=story.revision,settings=settings,system_text=system,user_text=user,input_refs=list(dict.fromkeys(refs)),accepted_stale_prose_ids=accepted_stale,fingerprint=fingerprint,estimated_tokens=estimate,fragments=fragments or {})


def build_context(repo,scene_id: str,stage: str,settings: RoleSettings) -> ContextBundle:
    if stage not in {'brief','draft','edit','memory'}:
        raise ValueError('Невідомий етап сцени')
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
        past=memory_before(repo,scene.id)
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
            sections=['ПОПЕРЕДНЯ ПЕРЕВІРЕНА ПАМ’ЯТЬ — НЕ ПЕРЕПИСУЙ\n'+past.model_dump_json(),
                f'ПОТОЧНА ПРОЗА [version_id={prose_id}] — НУМЕРОВАНІ ФРАГМЕНТИ\n'+render_fragments(repo.read_text(prose_id))]
            return make_context(repo,story,scene,stage,settings,sections,refs,{'previous_memory':past.model_dump_json()},accepted_prose_ids=expected)
        sections=['ПОПЕРЕДНЯ ПЕРЕВІРЕНА ПАМ’ЯТЬ\n'+past.model_dump_json(),
            'EXPECTED_SOURCE_PROSE_IDS — скопіюй цей список точно у source_prose_ids:\n'+json.dumps(expected)]
        add('ПОТОЧНА ПРОЗА — ЄДИНЕ ДЖЕРЕЛО НОВИХ ФАКТІВ',prose_id)
        return make_context(repo,story,scene,stage,settings,sections,refs,{'expected_source_prose_ids':json.dumps(expected)},accepted_prose_ids=expected)
    if stage=='edit' and settings.edit_mode=='patches':
        from .evidence import render_fragments
        draft_id=scene.heads.get('draft')
        if not draft_id:raise ValueError('Спершу створіть чернетку')
        add('ЧЕРНЕТКА',draft_id)
        sections=[f'ЧЕРНЕТКА [version_id={draft_id}] — НУМЕРОВАНІ ФРАГМЕНТИ\n'+render_fragments(repo.read_text(draft_id))]
        return make_context(repo,story,scene,stage,settings,sections,refs,{'copyedit_draft_id':draft_id})
    profile=StyleProfile()
    if story.style_version_id:
        add('ПРОФІЛЬ ПИСЬМА',story.style_version_id)
        profile=StyleProfile.model_validate_json(repo.read_text(story.style_version_id))
    if story.canon_version_id:
        add('АВТОРСЬКИЙ КАНОН',story.canon_version_id)
    if story.characters_version_id:
        if repo.get_version(story.characters_version_id).stale:
            raise ValueError('Картки персонажів застаріли; перегляньте й оновіть їх')
        cards=json.loads(repo.read_text(story.characters_version_id))
        selected=[c for c in cards if not scene.character_ids or c['id'] in scene.character_ids]
        refs.append(story.characters_version_id)
        sections.append('КАРТКИ ПЕРСОНАЖІВ\n'+json.dumps(selected,ensure_ascii=False))
    else:
        source=repo.active_source(story.id,'source_characters')
        if source:
            add('АВТОРСЬКІ ОПИСИ ПЕРСОНАЖІВ',source.id)
    source_plan=repo.active_source(story.id,'source_plan')
    if source_plan:
        text=repo.read_text(source_plan.id)
        heading=re.search(r'(?m)^\s*(?:#{1,6}\s*)?Сцена\s+\d+[.:]',text,re.IGNORECASE)
        preamble=text[:heading.start()].strip() if heading else ''
        if preamble:
            refs.append(source_plan.id)
            sections.append(f'ГЛОБАЛЬНІ АВТОРСЬКІ ВКАЗІВКИ [version_id={source_plan.id}]\n'+preamble)
    # Author plans are explicitly future intentions, never evidence of completed events.
    for item in scenes:
        if item.position>=scene.position:
            if item.heads.get('plan'):
                add(f'МАЙБУТНІ ПОДІЇ — ПЛАН СЦЕНИ {item.position+1}',item.heads['plan'])
            else:
                sections.append(f'МАЙБУТНІ ПОДІЇ — ПЛАН СЦЕНИ {item.position+1}\n{item.beats}')
    past=memory_before(repo,scene.id)
    sections.append('ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ\n'+past.model_dump_json())
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
    return make_context(repo,story,scene,stage,settings,sections,refs,fragments,accepted_prose_ids=past.source_prose_ids)
