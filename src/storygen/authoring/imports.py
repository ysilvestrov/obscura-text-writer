import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import Field
from ..domain import DomainModel, SceneCreate, RevisionConflict, new_id
from ..scene_description import name_key
from ..storage.repository import Repository
from ..import_models import ImportPublication,ImportedScene,ImportFileResult
from .import_sections import split_plan


class SourceFile(DomainModel):
    name: str
    raw: bytes
    kind: Literal['source_plan','source_characters']='source_plan'


class ImportResult(DomainModel):
    sources: list[dict]=Field(default_factory=list)
    version_ids: list[str]=Field(default_factory=list)
    proposed_scenes: list[SceneCreate]=Field(default_factory=list)
    created_character_cards: int=0
    created_scene_ids: list[str]=Field(default_factory=list)
    skipped_character_names: list[str]=Field(default_factory=list)
    skipped_scene_numbers: list[int]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)
    files: list[ImportFileResult]=Field(default_factory=list)
    partial: bool=False
    active_sources: dict[str,str]=Field(default_factory=dict)


class ImportBatchConflict(RevisionConflict):
    def __init__(self,result):
        super().__init__('Матеріали вже змінено; імпорт не застосовано')
        self.result=result


class ImportBatchFailure(ValueError):
    def __init__(self,result):
        super().__init__('Імпорт не застосовано; файл збережено лише як неопублікований матеріал')
        self.result=result


class ImportTooLarge(ValueError):pass


def suggest_scene_sections(plan):
    return [SceneCreate(title=s.title,beats=s.text,author_scene_number=s.author_scene_number) for s in split_plan(plan)[1]]


def _characters(repo,view,story,text,version,item,publication):
    from ..characters.importing import cards_from_markdown
    from ..characters.models import load_characters
    from ..characters.service import prepare_character_material
    existing=load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []
    cards,warnings=cards_from_markdown(text,version.id)
    item.warnings.extend(warnings)
    keys={name_key(c.name) for c in existing};new=[]
    for card in cards:
        key=name_key(card['name'])
        if key in keys:item.skipped_character_names.append(card['name']);continue
        keys.add(key);new.append(card)
    if new:
        payload,refs=prepare_character_material(repo.context_view(story.id),story,[c.model_dump() for c in existing]+new)
        saved=repo.save_version(story.id,None,'character_cards',json.dumps(payload,ensure_ascii=False),refs)
        publication.character_cards_version_id=saved.id
        publication.active_characters_version_id=version.id
        item.created_character_cards=len(new)
        item.warnings.append(f'Створено нових карток персонажів: {len(new)}. Часову доступність описів не перевірено; перегляньте картки.')
    elif not cards:
        if not story.characters_version_id:publication.active_characters_version_id=version.id
        item.warnings.append('Картки не створено: потрібні заголовки імен з описом нижче. Файл збережено; картки можна додати вручну.')
    if item.skipped_character_names:
        item.warnings.append('Наявні картки не перезаписано. Дублікати: '+', '.join(item.skipped_character_names)+'. Відредагуйте їх на сторінці «Персонажі».')


def _plan(repo,view,story,text,version,item,publication):
    from .. import build_edition
    default='Scene' if story.language=='en' else 'Сцена'
    if build_edition.current().long_prose:
        # BOOK-STRUCTURE: parts and arcs; an edition without long prose imports the plan exactly as before.
        from ..plan_sections import split_book_plan
        preamble,book,publication.structured=split_book_plan(text,default)
        sections=[item.section for item in book];places={id(item.section):item for item in book}
        # SERIES: the preamble lines were applied before the batch (enter_series_from_plan); here they are only cut.
        from ..plan_sections import cut_series_lines
        kept=cut_series_lines(preamble)[0];series_cut=kept!=preamble;preamble=kept
    else:
        preamble,sections=split_plan(text,default);places={};series_cut=False
    existing=view.list_scenes(story.id)
    numbers={s.author_scene_number for s in existing if s.author_scene_number is not None}
    accepted=[]
    for section in sections:
        number=section.author_scene_number
        if number is not None and number in numbers:
            item.skipped_scene_numbers.append(number);continue
        if number is not None:numbers.add(number)
        accepted.append(section)
    if not accepted:
        item.warnings.append('Дублікати сцен за номером пропущено; наявні сцени не змінено.')
        return []
    base,remainder=divmod(story.target_words,len(accepted))
    proposals=[];cut=False;invalid_flashback=False
    from ..plan_sections import cut_flashback_line
    for index,section in enumerate(accepted):
        # STORY-TIME: «Спогад: так|ні» is cut from the scene plan and sets the flag in every edition.
        beats,flashback,invalid=cut_flashback_line(section.text)
        cut=cut or beats!=section.text;invalid_flashback=invalid_flashback or invalid
        data=SceneCreate(title=section.title,beats=beats,author_scene_number=section.author_scene_number,target_words=1000 if existing else max(1,base+(index<remainder)),
                         flashback=bool(flashback))
        plan=repo.save_version(story.id,None,'scene_plan',beats,[version.id])
        place=places.get(id(section))
        publication.scenes.append(ImportedScene(data=data,plan_version_id=plan.id,part_title=place.part_title if place else None,
                                                arc_title=place.arc_title if place else None,part_index=place.part_index if place else None,
                                                protagonist_name=place.protagonist_name if place else None,
                                                arc_titles=list(place.arc_titles) if place and place.arc_titles else None));proposals.append(data)
    if invalid_flashback:item.warnings.append('Рядок «Спогад:» має бути «так» або «ні»; прапорець не поставлено.')
    texts=[cut_flashback_line(s.text)[0] for s in accepted]
    previous=view.active_source(story.id,'source_plan')
    if previous:
        combined=view.read_text(previous.id)+'\n\n'+''.join(texts)
        active=repo.save_version(story.id,None,'source_plan',combined,[previous.id,version.id])
        publication.active_plan_version_id=active.id
    # A structured plan is never kept as is: its part headings and arc lines must not reach the source plan.
    elif len(accepted)==len(sections) and not publication.structured and not cut and not series_cut:publication.active_plan_version_id=version.id
    else:
        active=repo.save_version(story.id,None,'source_plan',preamble+''.join(texts),[version.id])
        publication.active_plan_version_id=active.id
    if any(s.author_scene_number is None for s in accepted):
        item.warnings.append('Сцени без номера завжди додаються як нові, зокрема при повторному імпорті. Перегляньте поділ плану.')
    if item.skipped_scene_numbers:item.warnings.append('Пропущено номери сцен: '+', '.join(map(str,item.skipped_scene_numbers))+'. Наявні плани не змінено.')
    return proposals


def _enter_series(repo,story_id,prepared):
    """SERIES: the series lines of the first plan of the batch put the book into its series before any file is imported,
    so the start snapshot comes before a card file of the same batch. Returns {file index: warnings}."""
    from .. import build_edition
    if not build_edition.current().long_prose:return {}
    index=next((i for i,(file,_) in enumerate(prepared) if file.kind=='source_plan'),None)
    if index is None:return {}
    from ..plan_sections import cut_series_lines, split_book_plan
    from ..storage.series import enter_series_from_plan
    _,lines,invalid=cut_series_lines(split_book_plan(prepared[index][1])[0])
    return {index:enter_series_from_plan(repo,story_id,lines,invalid)}


def import_sources(repo: Repository,story_id: str,files: list[SourceFile]) -> ImportResult:
    repo.get_story(story_id)
    prepared=[]
    for file in files:
        if len(file.raw)>2*1024*1024:raise ImportTooLarge('Потрібен файл розміром до 2 MiB')
        if Path(file.name).suffix.lower() not in {'.txt','.md'}:raise ValueError('Потрібен файл TXT/MD')
        try:text=file.raw.decode('utf-8-sig')
        except UnicodeError:raise ValueError('Потрібен файл UTF-8') from None
        if not text.strip():raise ValueError('Матеріал порожній')
        prepared.append((file,text))
    result=ImportResult(files=[ImportFileResult(client_index=i,name=f.name,kind=f.kind) for i,f in enumerate(files)])
    created=[];pending=[]
    series_notes=_enter_series(repo,story_id,prepared)
    for index,(file,text) in enumerate(prepared):
        item=result.files[index]
        try:
            view=repo.context_view(story_id);story=view.get_story(story_id)
            id=new_id();relative=f'stories/{story_id}/sources/{id}.bin'
            repo.files.write(relative,file.raw)
            version=repo.save_version(story_id,None,file.kind,text,[])
            metadata=dict(id=id,name=file.name,relative_path=relative,sha256=hashlib.sha256(file.raw).hexdigest(),version_id=version.id,kind=file.kind)
            publication=ImportPublication(metadata=metadata)
            proposals=[]
            if file.kind=='source_characters':_characters(repo,view,story,text,version,item,publication)
            else:proposals=_plan(repo,view,story,text,version,item,publication)
            published=repo.publish_import(story_id,story.revision,publication)
        except Exception as error:
            item.status='failed'
            item.created_character_cards=0;item.created_scene_ids=[]
            item.warnings=[];item.skipped_character_names=[];item.skipped_scene_numbers=[]
            item.error='Матеріали вже змінено; файл не застосовано' if isinstance(error,RevisionConflict) else 'Не вдалося застосувати файл; попередні успішні імпорти збережено'
            result.partial=any(f.status=='imported' for f in result.files)
            if not result.partial:
                result.warnings=[item.error]
                result.active_sources=dict(repo.context_view(story_id).sources)
                raise (ImportBatchConflict(result) if isinstance(error,RevisionConflict) else ImportBatchFailure(result)) from error
            break
        item.status='imported';item.source_id=id;item.version_id=version.id;item.created_scene_ids=published.created_scene_ids
        item.warnings.extend(series_notes.get(index,[]))
        item.warnings.extend(published.warnings)
        if published.pending_protagonists:pending.append((item,published.pending_protagonists))
        result.sources.append(metadata);result.version_ids.append(version.id)
        created.extend(zip(item.created_scene_ids,proposals,strict=True))
        result.proposed_scenes.extend(proposals);result.created_scene_ids.extend(item.created_scene_ids)
        result.created_character_cards+=item.created_character_cards
        result.skipped_character_names.extend(item.skipped_character_names);result.skipped_scene_numbers.extend(item.skipped_scene_numbers)
    # BOOK-LINEAGE-S04: protagonist names a later card file of the batch may have created, resolved like the cast (#103).
    from ..storage.book_structure import bind_pending_protagonists
    for item,names in pending:item.warnings.extend(bind_pending_protagonists(repo,story_id,names))
    result.warnings=[message for item in result.files for message in item.warnings+([item.error] if item.error else [])]
    view=repo.context_view(story_id)
    # The cast is resolved at publication, also against cards a later file of the same batch created (#103).
    for scene_id,proposal in created:proposal.character_ids=list(view.get_scene(scene_id).character_ids)
    result.active_sources=dict(view.sources)
    return result
