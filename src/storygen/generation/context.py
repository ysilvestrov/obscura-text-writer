from ..scene_description import SCENE_HEADING
import hashlib
import json
from dataclasses import dataclass
from typing import Callable

from pydantic import Field

from ..dependency_models import DependencySnapshot, TargetCAS
from ..storage.snapshots import build_dependency_snapshot
from ..domain import DomainModel
from ..memory.service import journal_before
from ..memory.projection import project_memory, memory_catalog_v4, memory_items
from ..memory.selection import SelectionInput, minimal_chars, select_memory
from ..providers.models import RoleSettings
from .models import StyleProfile
from .prompts import role_prompt, validate_role_prompt
from ..prompt_contracts import memory_wire_version
from ..characters.context import character_material
from ..characters.projection import OTHER_MATERIAL_WARNING
from ..story_horizon import selected_plan_scenes,horizon_future_count,horizon_instructions,HORIZON_LIMIT_WARNING,MISSING_ENDING_WARNING


class ContextOverflow(ValueError):
    def __init__(self,estimated_tokens: int,limit: int,chars: int,memory_chars: int=0,breakdown=None,*,max_input_chars: int | None=None,minimal_memory: bool=False):
        self.breakdown=breakdown
        self.estimated_tokens=estimated_tokens
        self.limit=limit
        self.chars=chars
        contribution=f' Проєкція пам’яті: {memory_chars} символів.' if memory_chars else ''
        if minimal_memory:
            # MEMORY-SELECT-S03: even the core alone (with the timeline note) does not fit; the core is never cut.
            contribution+=' Не вміщається навіть мінімальна пам’ять: ядро й позначка хронології; ядро не обрізається.'
        self.max_input_chars=max_input_chars
        if max_input_chars is None:
            message=f'Контекст завеликий: приблизно {estimated_tokens} токенів, доступно {limit}; {chars} символів. Текст не обрізано.'
        else:
            if estimated_tokens>limit and chars>max_input_chars:
                reason='Перевищено токенний та операційний ліміти входу'
            elif chars>max_input_chars:
                reason='Перевищено операційний ліміт входу'
            else:
                reason='Перевищено токенний ліміт входу'
            message=f'{reason}: {chars} символів, дозволено {max_input_chars}; приблизно {estimated_tokens} токенів, доступно {limit}. Текст не обрізано.'
        super().__init__(message+contribution)


CATALOG_NARROWED_WARNING='Каталог пам’яті звужено: {hidden} записів не показано моделі; оновити їх у цьому запуску неможливо, а повтор уже відомого факту можливий.'
MEMORY_SELECTED_WARNING='Повна пам’ять не вміщається: у запит відібрано {shown} з {total} записів; ядро показано повністю, відкинуте пораховано в статистиці.'


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
    api_request: dict = Field(default_factory=dict)
    token_estimate: dict = Field(default_factory=dict)
    fragments: dict[str,str] = Field(default_factory=dict)
    memory_metrics: dict = Field(default_factory=dict)
    context_warnings: list[str] = Field(default_factory=list)
    context_breakdown: dict = Field(default_factory=dict)


@dataclass(frozen=True)
class MemorySelector:
    """The literary memory section of a request and how to select it under a budget (MEMORY-SELECT)."""
    index: int                           # position of the memory section in `sections`
    header: str
    full_text: str
    build: Callable[[], SelectionInput]  # lazy: no extra work while the full request fits
    kinds: Callable[[], dict] = dict      # selector value scene/memory_kind_overrides (MEMORY-SELECT-S08)


SELECTION_STEPS=12
SELECTED_PROJECTION='memory-uk-v3-selected'


def _select_memory_section(selector,sections,measured,measure,fits,settings):
    """Largest char budget whose whole request passes the same token and char checks (binary search, MEMORY-SELECT-S06).

    Returns None when no smaller section exists, ('minimal', measured, sections) when no probed section fits — the
    sections are the reduced ones the measurement was taken on — otherwise (sections, selection, steps, measured)."""
    inp=selector.build()
    low=minimal_chars(inp)
    high=min(len(selector.full_text)-1,settings.max_input_chars-(measured[1]-len(selector.full_text)))
    def attempt(budget):
        selection=select_memory(inp,budget)
        parts=list(sections);parts[selector.index]=selector.header+selection.text
        result=measure(parts)
        return fits(result),parts,selection,result
    if high<low:
        if low<len(selector.full_text):
            _,parts,_,result=attempt(low)
            return 'minimal',result,parts
        return None
    ok,parts,selection,result=attempt(low)
    if not ok:
        # A verified token profile holds only inside its byte range and the fallback outside it is coarser, so the
        # estimate is not monotonic in the budget: a failing minimum does not prove that nothing fits. Probe the
        # largest budget before giving up.
        top=attempt(high) if high>low else None
        if top is None or not top[0]:return 'minimal',result,parts
        return top[1],top[2],1,top[3]
    best=(parts,selection,result);steps=0
    while low<high and steps<SELECTION_STEPS:
        middle=(low+high+1)//2;steps+=1
        ok,parts,selection,result=attempt(middle)
        if ok:low,best=middle,(parts,selection,result)
        else:high=middle-1
    return best[0],best[1],steps,best[2]


def make_context(repo,story,scene,stage,settings,sections,refs,fragments=None,accepted_prose_ids=(),memory_metrics=None,context_warnings=None,memory_provenance=(),accepted_memory_ids=(),memory_selector=None,memory_narrower=None):
    if hasattr(repo, 'context_view'):
        repo=repo.context_view(story.id)
        story=repo.get_story(story.id)
        scene=repo.get_scene(scene.id) if scene else None
    from ..rating.guard import enforce_rating
    enforce_rating(repo,story,scene,stage)
    prompt_id=settings.prepare_prompt_version_id if stage=='prepare' else settings.prompt_version_id
    ref=None if stage=='rewrite' else validate_role_prompt(repo,story.id,stage,settings)
    if ref:
        system=repo.read_text(ref.id)
        refs.append(ref.id)
        if stage=='brief':
            # The WritersBrief wire (strict schema) requires `introduced`; custom prompts may predate it.
            from ..prompt_contracts import BRIEF_INTRODUCED_CONTRACT
            system+='\n\n'+BRIEF_INTRODUCED_CONTRACT
    else:
        if stage=='rewrite':
            from importlib.resources import files
            system=files('storygen.generation').joinpath('resources','assisted_writer_uk_v1.txt').read_text(encoding='utf-8')
        else:system=role_prompt(stage,settings)
    fragments=dict(fragments or {})
    if stage in {'draft','edit','rewrite'}:
        source_id=fragments.get('copyedit_draft_id') or fragments.get('rewrite_source_id')
        content_format='markdown' if stage=='draft' else repo.get_version(source_id).content_format if source_id else 'plain'
        fragments['output_content_format']=content_format
        if content_format=='markdown':
            from ..prompt_contracts import MARKDOWN_PRESERVATION
            system+='\n\n'+MARKDOWN_PRESERVATION
    from ..rating.instructions import rating_instructions
    rating_text=rating_instructions(repo,story,scene,stage,settings)
    if rating_text:system+='\n\n'+rating_text
    warnings=list(context_warnings or [])
    if prompt_id and stage in {'brief','draft','edit'} and OTHER_MATERIAL_WARNING not in warnings:
        warnings.append(OTHER_MATERIAL_WARNING)
    from ..providers.requests import generation_request
    from ..token_budget.service import token_estimate
    from .context_metrics import request_breakdown
    limit=settings.context_tokens-settings.max_output_tokens
    def measure(parts):
        user='\n\n'.join(parts)
        api_request=generation_request(stage,settings,system,user,fragments or {})
        prediction=token_estimate(repo,settings.provider.provider,settings.provider.base_url,api_request)
        return user,len(system)+len(user),api_request,prediction
    fits=lambda result:result[3]['input_tokens']<=limit and result[1]<=settings.max_input_chars
    measured=measure(sections)
    memory_metrics=dict(memory_metrics or {})
    if not fits(measured) and memory_selector is not None:
        # MEMORY-SELECT: only an overflowing request is selected; a fitting one stays byte-identical (S01).
        selected=_select_memory_section(memory_selector,sections,measured,measure,fits,settings)
        if selected and selected[0]=='minimal':
            minimal=selected[1]
            raise ContextOverflow(minimal[3]['input_tokens'],limit,minimal[1],memory_metrics.get('projection_chars',0),
                request_breakdown(minimal[2],selected[2],stage,minimal[3],settings),max_input_chars=settings.max_input_chars,minimal_memory=True)
        if selected:
            sections,selection,steps,measured=selected
            total=sum(selection.layers.values())+sum(selection.dropped.values())
            memory_metrics.update({'projection_version':SELECTED_PROJECTION,'projection_chars':len(selection.text),
                'selection':{'layers':selection.layers,'dropped':selection.dropped,'selected_claim_ids':list(selection.selected_claim_ids),
                    'timeline_note':selection.timeline_note,'char_budget':selection.char_budget,'steps':steps}})
            warnings.append(MEMORY_SELECTED_WARNING.format(shown=len(selection.selected_claim_ids),total=total))
    if not fits(measured) and memory_narrower is not None:
        # MEMORY-SELECT-S07: one narrowed memory-stage catalog with matching schema bounds; no search, no further cuts.
        sections,updates,metrics,warning=memory_narrower()
        fragments.update(updates);memory_metrics.update(metrics);warnings.append(warning)
        measured=measure(sections)
    user,chars,api_request,prediction=measured
    estimate=prediction['input_tokens']
    breakdown=request_breakdown(api_request,sections,stage,prediction,settings)
    if not fits(measured):
        raise ContextOverflow(estimate,limit,chars,memory_metrics.get('projection_chars',memory_metrics.get('catalog_chars',0)),breakdown,max_input_chars=settings.max_input_chars)
    accepted_stale=[id for id in dict.fromkeys(accepted_prose_ids) if id in refs and (ref:=repo.get_version(id)).stale and ref.kind in {'edited','manual'}]
    fingerprint=hashlib.sha256(json.dumps({'system':system,'user':user,'settings':settings.model_dump(),'refs':refs,'accepted_stale_prose_ids':accepted_stale,'order':build_dependency_snapshot(repo,scene.id if scene else None,stage,settings,refs).scene_order},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    snapshot=build_dependency_snapshot(repo,scene.id if scene else None,stage,settings,refs)
    from ..dependency_models import MemoryReuseApproval
    snapshot.memory_provenance=[MemoryReuseApproval.model_validate(p) for p in memory_provenance]
    snapshot.accepted_stale_memory_ids=list(accepted_memory_ids)
    if 'selection' in memory_metrics and scene:
        # MEMORY-SELECT-S08 (I8): author marks stale only versions whose request was built with selection.
        from ..dependency_models import DependencySelector
        snapshot.selectors.append(DependencySelector(kind='scene',owner_id=scene.id,field='memory_kind_overrides',expected=memory_selector.kinds()))
    if memory_provenance:
        fingerprint=hashlib.sha256((fingerprint+snapshot.model_dump_json()).encode()).hexdigest()
    head={'brief':'brief','draft':'draft','edit':'prose','memory':'memory','rewrite':'draft'}.get(stage)
    target=TargetCAS(scene_id=scene.id,head=head,version_id=scene.heads.get(head),head_revision=scene.head_revisions.get(head,0)) if scene and head else None
    return ContextBundle(context_breakdown=breakdown,api_request=api_request,token_estimate=prediction,estimate_method=prediction['method'],dependency_snapshot=snapshot,target_cas=target,story_id=story.id,scene_id=scene.id if scene else None,stage=stage,scene_revision=scene.revision if scene else None,story_revision=story.revision,settings=settings,system_text=system,user_text=user,input_refs=list(dict.fromkeys(refs)),accepted_stale_prose_ids=accepted_stale,fingerprint=fingerprint,estimated_tokens=estimate,fragments=fragments or {},memory_metrics=memory_metrics,context_warnings=list(dict.fromkeys(warnings)))


def build_context(repo,scene_id: str,stage: str,settings: RoleSettings,*,editor_source_id: str | None=None,memory_approval: str | None=None,view=None) -> ContextBundle:
    if memory_approval is not None and stage!='memory':
        raise ValueError('Підтвердження пам’яті дозволено лише для її оновлення')
    if stage not in {'brief','draft','edit','memory','rewrite'}:
        raise ValueError('Невідомий етап сцени')
    if view is not None:
        repo=view
        scene=repo.get_scene(scene_id)
    else:
        scene=repo.get_scene(scene_id)
        if hasattr(repo, 'context_view'):
            repo=repo.context_view(scene.story_id)
            scene=repo.get_scene(scene_id)
    story=repo.get_story(scene.story_id)
    from ..characters.context import validate_scene_participants
    validate_scene_participants(repo,story,scene)
    scenes=repo.list_scenes(story.id)
    refs=[]
    sections=[f'СЦЕНА {scene.position+1}/{len(scenes)}: {scene.title}\nЦільовий обсяг: {scene.target_words} слів.']
    def add(label,id):
        ref=repo.get_version(id)
        if (ref.stale and not (stage=='memory' and ref.kind in {'edited','manual'}) and not (stage=='rewrite' and id==editor_source_id)) or not ref.complete:
            raise ValueError('Контекст містить застарілий матеріал; потрібне оновлення')
        refs.append(id)
        sections.append(f'{label} [version_id={id}]\n'+repo.read_text(id))
    if stage=='memory':
        from ..memory.reuse import memory_for_update, provenance_warnings
        past,approval,provenance=memory_for_update(repo,scene.id,memory_approval)
        reuse={'memory_provenance':provenance,'accepted_memory_ids':[approval['memory_id']] if approval else [],'context_warnings':provenance_warnings(provenance)}
        previous=[s for s in scenes if s.position<scene.position]
        prose_id=scene.heads.get('prose')
        if not prose_id:raise ValueError('Спершу виберіть завершену прозу')
        if repo.get_version(prose_id).kind not in {'edited','manual'}:
            raise ValueError('Пам’ять може спиратися лише на вибрану прозу')
        refs.extend(past.source_prose_ids)
        if previous:refs.append(previous[-1].heads['memory'])
        expected=past.source_prose_ids+[prose_id]
        from .evidence import render_fragments
        from ..characters.models import load_characters
        from ..memory.core import tracked_characters
        from ..memory.story_time import comparison_scene, day_change, day_key, day_label
        from ..memory.wire_v4 import schema_bounds_v4
        add('ПОТОЧНА ПРОЗА',prose_id)
        # Only v4 prompts pass preflight; /2 and /3 contracts are rejected before any request.
        wire=memory_wire_version(validate_role_prompt(repo,story.id,'memory',settings))
        cards=load_characters(repo.read_text(story.characters_version_id)) if story.characters_version_id else []
        everyone=tracked_characters(cards,scenes)
        tracked=[cid for cid in everyone if cid in scene.character_ids]
        changed={cid:day_change(scenes,scene,cid) for cid in tracked}
        names={card.id:card.name for card in cards}
        prose_text=repo.read_text(prose_id)
        dump=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':'))
        def catalog_sections(keep=None):
            catalog=memory_catalog_v4(past,tracked,names,all_tracked=everyone,keep=keep)
            parts=json.loads(catalog)
            bounds=schema_bounds_v4(past,prose_text,scene.character_ids,everyone,changed,keep=keep)
            return catalog,parts,bounds,stage_sections(parts)
        def stage_sections(parts):
            sections=['ЯДРО СТАНУ ВІДСТЕЖУВАНИХ ПЕРСОНАЖІВ — УСІ СЛОТИ ОБОВ’ЯЗКОВІ\n'+dump({'names':parts['names'],'core':parts['core']}),
                'АКТИВНІ ЛІНІЇ — ДЛЯ КОЖНОЇ ОБОВ’ЯЗКОВЕ open/closed\n'+dump(parts['threads']),
                'ЧИННІ ТВЕРДЖЕННЯ — MUTABLE ДЛЯ UPDATE/RETIRE, IMMUTABLE ЛИШЕ ДЛЯ УНИКНЕННЯ ПОВТОРІВ\n'+dump({'mutable':parts['mutable'],'immutable':parts['immutable']})]
            for cid in tracked:
                if changed[cid]:
                    sections.append(f'ЗМІНИВСЯ ДЕНЬ: {day_label(day_key(comparison_scene(scenes,scene,cid)))} → {day_label(day_key(scene))} ({parts["names"][cid]})\n'
                        'Одяг, речі при собі й тілесний стан могли застаріти: якщо проза їх не підтверджує, познач unknown із причиною.')
            sections+=['ДОЗВОЛЕНІ CHARACTER_IDS ДЛЯ НОВИХ СТАНІВ\n'+json.dumps(scene.character_ids,ensure_ascii=False),
                f'ПОТОЧНА ПРОЗА [version_id={prose_id}] — НУМЕРОВАНІ ФРАГМЕНТИ\n'+render_fragments(prose_text)]
            return sections
        catalog,parts,bounds,sections=catalog_sections()
        def narrower():
            from ..memory.selection import narrow_catalog
            numbers={s.id:s.position+1 for s in scenes}
            narrow=narrow_catalog(past,scene.character_ids,everyone,names,prose_text,scene.position+1,
                {id:numbers[repo.get_version(id).scene_id] for id in past.source_prose_ids})
            small,_,small_bounds,small_sections=catalog_sections(set(narrow.keep))
            return (small_sections,{'memory_schema_bounds':json.dumps(small_bounds,ensure_ascii=False)},
                {'projection_version':f'memory-catalog-v{wire}-narrow','catalog_chars':len(small),
                 'narrow':{'hidden':narrow.hidden,'mutable_shown':narrow.mutable_shown,'immutable_shown':narrow.immutable_shown}},
                CATALOG_NARROWED_WARNING.format(hidden=narrow.hidden))
        return make_context(repo,story,scene,stage,settings,sections,refs,{'previous_memory':past.model_dump_json(),'expected_source_prose_ids':json.dumps(expected),
            'memory_allowed_character_ids':json.dumps(scene.character_ids),'memory_wire_version':str(wire),
            'memory_schema_bounds':json.dumps(bounds,ensure_ascii=False),'memory_tracked':json.dumps(tracked,ensure_ascii=False)},accepted_prose_ids=expected,**reuse,
            memory_metrics={'projection_version':f'memory-catalog-v{wire}','journal_chars':len(past.model_dump_json()),'catalog_chars':len(catalog),'event_count':len(past.events)},
            memory_narrower=narrower)
    if stage=='edit' and settings.edit_mode in {'patches','diff'}:
        from .evidence import render_fragments
        draft_id=editor_source_id or scene.heads.get('draft')
        if not draft_id:raise ValueError('Спершу створіть чернетку')
        add('ЧЕРНЕТКА',draft_id)
        sections=[repo.read_text(draft_id)] if settings.edit_mode=='diff' else [f'ЧЕРНЕТКА [version_id={draft_id}] — НУМЕРОВАНІ ФРАГМЕНТИ\n'+render_fragments(repo.read_text(draft_id))]
        return make_context(repo,story,scene,stage,settings,sections,refs,{'copyedit_draft_id':draft_id})
    profile=StyleProfile()
    warnings=[]
    if story.style_version_id:
        add('ПРОФІЛЬ ПИСЬМА',story.style_version_id)
        profile=StyleProfile.model_validate_json(repo.read_text(story.style_version_id))
        if profile.ending_goal.strip():
            sections[-1]=f'ПРОФІЛЬ ПИСЬМА [version_id={story.style_version_id}]\n'+profile.model_dump_json(exclude={'ending_goal'})
    if story.canon_version_id:
        add('АВТОРСЬКИЙ КАНОН',story.canon_version_id)
        warnings.append(OTHER_MATERIAL_WARNING)
    character_text,character_warnings,character_refs=character_material(repo,story,scene)
    if character_text:sections.append(character_text)
    warnings.extend(character_warnings);refs.extend(character_refs)
    from ..characters.acquaintance import acquaintance_material
    acquaintance_text,acquaintance_warnings=acquaintance_material(repo,story,scene,stage)
    if acquaintance_text:sections.append(acquaintance_text)
    warnings.extend(acquaintance_warnings)
    source_plan=repo.active_source(story.id,'source_plan')
    if source_plan:
        text=repo.read_text(source_plan.id)
        from ..plan_sections import split_plan
        preamble=split_plan(text)[0].strip()
        if preamble:
            warnings.append(OTHER_MATERIAL_WARNING)
            refs.append(source_plan.id)
            sections.append(f'ГЛОБАЛЬНІ АВТОРСЬКІ ВКАЗІВКИ [version_id={source_plan.id}]\n'+preamble)
    # Author plans are explicitly future intentions, never evidence of completed events.
    for item in selected_plan_scenes(scenes,scene,settings):
        if item.heads.get('plan'):
            add(f'МАЙБУТНІ ПОДІЇ — ПЛАН СЦЕНИ {item.position+1}',item.heads['plan'])
        else:
            sections.append(f'МАЙБУТНІ ПОДІЇ — ПЛАН СЦЕНИ {item.position+1}\n{item.beats}')
    count=horizon_future_count(settings)
    if count is not None:
        warnings.append(HORIZON_LIMIT_WARNING)
        sections.append(horizon_instructions(scene,len(scenes)))
        if count==0 and not profile.ending_goal.strip():
            warnings.append(MISSING_ENDING_WARNING)
    if profile.ending_goal.strip():
        sections.append('АВТОРСЬКИЙ ОРІЄНТИР ФІНАЛУ — ЗАДУМ, НЕ ЗДІЙСНЕНІ ПОДІЇ\n'+profile.ending_goal)
        if count is None:sections.append(horizon_instructions(scene,len(scenes)))
    past=journal_before(repo,scene.id)
    from ..memory.reuse import provenance_before, provenance_warnings
    inherited_provenance=provenance_before(repo,scene.id)
    warnings.extend(provenance_warnings(inherited_provenance))
    from ..memory.forwarding import hidden_before,forwarded_before
    from ..memory.core import tracked_characters
    from ..characters.models import load_characters
    scene_numbers={s.id:s.position+1 for s in scenes if s.position<scene.position}
    cards=load_characters(repo.read_text(story.characters_version_id)) if story.characters_version_id else []
    source_numbers={id:scene_numbers[repo.get_version(id).scene_id] for id in past.source_prose_ids}
    hidden,forwarded=hidden_before(repo,scene.id),forwarded_before(repo,scene.id)
    tracked=tracked_characters(cards,scenes);names={card.id:card.name for card in cards}
    projection=project_memory(past,scene.character_ids,source_numbers,hidden_claim_ids=hidden,forwarded_claim_ids=forwarded,tracked=tracked,names=names)
    memory_header='ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ\n'
    memory_index=len(sections)
    sections.append(memory_header+projection.text)
    def selection_input():
        from ..memory.story_time import day_key
        items,_=memory_items(past,scene.character_ids,source_numbers,hidden_claim_ids=hidden,forwarded_claim_ids=forwarded,tracked=tracked,names=names)
        # FTS query: the scene's own plan (already in refs) and, where it is a required input, its brief.
        query=[repo.read_text(scene.heads['plan']) if scene.heads.get('plan') else scene.beats]
        if stage in {'draft','edit'} and scene.heads.get('brief'):query.append(repo.read_text(scene.heads['brief']))
        return SelectionInput(tuple(items),scene.id,scene.position+1,tuple(scene.character_ids),tuple(tracked),names,'\n'.join(query),kinds(),
            day_key(scene),{s.position+1:day_key(s) for s in scenes if s.position<scene.position})
    def kinds():
        from ..memory.kinds import kind_overrides
        return kind_overrides(repo if hasattr(repo,'peek_scene') else repo.context_view(story.id),scene.id)
    memory_selector=MemorySelector(memory_index,memory_header,projection.text,selection_input,kinds)
    previous=[s for s in scenes if s.position<scene.position]
    fragments={}
    if previous:
        refs.extend(past.source_prose_ids)
        refs.append(previous[-1].heads['memory'])
        tail=repo.read_text(previous[-1].heads['prose'])[-profile.previous_tail_chars:] if profile.previous_tail_chars else ''
        fragments['previous_prose_tail']=tail
        sections.append('ЗАВЕРШЕННЯ ПОПЕРЕДНЬОЇ СЦЕНИ (явно вибраний фрагмент)\n'+tail)
    if stage=='rewrite':
        fragments['rewrite_source_id']=editor_source_id
        add('ЗБЕРЕЖЕНА ЧЕРНЕТКА ДЛЯ ПЕРЕПИСУВАННЯ',editor_source_id)
    required={'rewrite':[],'brief':[],'draft':['brief'],'edit':['brief','draft'],'memory':['prose']}[stage]
    for head in required:
        version_id=editor_source_id if stage=='edit' and head=='draft' and editor_source_id else scene.heads.get(head)
        if not version_id:
            raise ValueError('Спершу завершіть попередній етап: '+head)
        if stage=='edit' and head=='draft':fragments['copyedit_draft_id']=version_id
        add({'brief':'ЗАВДАННЯ ПИСЬМЕННИКУ','draft':'ЧЕРНЕТКА ДЛЯ РЕДАКТУРИ','prose':'ПОТОЧНА ПРОЗА — ДЖЕРЕЛО НОВОЇ ПАМ’ЯТІ'}[head],version_id)
    return make_context(repo,story,scene,stage,settings,sections,refs,fragments,accepted_prose_ids=past.source_prose_ids,memory_metrics=projection.metrics,context_warnings=warnings,memory_provenance=inherited_provenance,memory_selector=memory_selector)
