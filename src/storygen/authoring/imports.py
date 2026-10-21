import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..domain import DomainModel, SceneCreate, new_id
from ..storage.repository import Repository


class SourceFile(DomainModel):
    name: str
    raw: bytes
    kind: Literal["source_plan","source_characters"]="source_plan"


class ImportResult(DomainModel):
    sources: list[dict]=Field(default_factory=list)
    version_ids: list[str]=Field(default_factory=list)
    proposed_scenes: list[SceneCreate]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)


def suggest_scene_sections(plan: str) -> list[SceneCreate]:
    headings=list(re.finditer(r"(?m)^\s*(?:#{1,6}\s*)?Сцена\s+\d+[.:]\s*([^\n]+)",plan,re.IGNORECASE))
    if not headings:
        return [SceneCreate(title="Сцена 1",beats=plan)]
    return [SceneCreate(title=m.group(1).strip()[:300] or f"Сцена {index+1}",
        beats=plan[m.start():headings[index+1].start() if index+1<len(headings) else len(plan)].strip()) for index,m in enumerate(headings)]


def import_sources(repo: Repository,story_id: str,files: list[SourceFile]) -> ImportResult:
    story=repo.get_story(story_id)
    prepared=[]
    for file in files:
        if Path(file.name).suffix.lower() not in {".txt",".md"} or len(file.raw)>2*1024*1024:
            raise ValueError("Потрібен файл TXT/MD розміром до 2 MiB")
        text=file.raw.decode("utf-8-sig")
        if not text.strip():
            raise ValueError("Матеріал порожній")
        prepared.append((file,text))
    result=ImportResult()
    for file,text in prepared:
        id=new_id()
        relative=f"stories/{story_id}/sources/{id}.bin"
        repo.files.write(relative,file.raw)
        version=repo.save_version(story_id,None,file.kind,text,[])
        metadata={"id":id,"name":file.name,"relative_path":relative,"sha256":hashlib.sha256(file.raw).hexdigest(),"version_id":version.id,"kind":file.kind}
        repo.register_source(story_id,metadata)
        result.sources.append(metadata)
        result.version_ids.append(version.id)
        if file.kind=="source_plan":
            proposed=suggest_scene_sections(text)
            result.proposed_scenes.extend(proposed)
            if len(proposed)==1:
                result.warnings.append("Перегляньте поділ плану на сцени; за потреби розділіть його вручну.")
            if not repo.list_scenes(story_id):
                base,remainder=divmod(story.target_words,len(proposed))
                for index,item in enumerate(proposed):
                    item.target_words=max(1,base+(index<remainder))
                    scene=repo.create_scene(story_id,item)
                    plan_version=repo.save_version(story_id,scene.id,"scene_plan",item.beats,[version.id])
                    repo.set_head(scene.id,"plan",plan_version.id,scene.revision)
            else:
                result.warnings.append("Новий план збережено; наявні сцени не замінено автоматично.")
    return result
