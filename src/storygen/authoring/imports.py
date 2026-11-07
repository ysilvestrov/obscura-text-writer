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
    preamble,sections=split_plan(text)
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
    proposals=[]
    for index,section in enumerate(accepted):
        data=SceneCreate(title=section.title,beats=section.text,author_scene_number=section.author_scene_number,target_words=1000 if existing else max(1,base+(index<remainder)))
        plan=repo.save_version(story.id,None,'scene_plan',section.text,[version.id])
        publication.scenes.append(ImportedScene(data=data,plan_version_id=plan.id));proposals.append(data)
    previous=view.active_source(story.id,'source_plan')
    if previous:
        combined=view.read_text(previous.id)+'\n\n'+''.join(s.text for s in accepted)
        active=repo.save_version(story.id,None,'source_plan',combined,[previous.id,version.id])
        publication.active_plan_version_id=active.id
    elif len(accepted)==len(sections):publication.active_plan_version_id=version.id
    else:
        active=repo.save_version(story.id,None,'source_plan',preamble+''.join(s.text for s in accepted),[version.id])
        publication.active_plan_version_id=active.id
    if any(s.author_scene_number is None for s in accepted):
        item.warnings.append('Сцени без номера завжди додаються як нові, зокрема при повторному імпорті. Перегляньте поділ плану.')
    if item.skipped_scene_numbers:item.warnings.append('Пропущено номери сцен: '+', '.join(map(str,item.skipped_scene_numbers))+'. Наявні плани не змінено.')
    return proposals


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
        result.sources.append(metadata);result.version_ids.append(version.id)
        result.proposed_scenes.extend(proposals);result.created_scene_ids.extend(item.created_scene_ids)
        result.created_character_cards+=item.created_character_cards
        result.skipped_character_names.extend(item.skipped_character_names);result.skipped_scene_numbers.extend(item.skipped_scene_numbers)
    result.warnings=[message for item in result.files for message in item.warnings+([item.error] if item.error else [])]
    result.active_sources=dict(repo.context_view(story_id).sources)
    return result
