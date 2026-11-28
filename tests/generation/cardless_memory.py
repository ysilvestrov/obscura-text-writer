"""A book without cards and its memory-stage request, for the byte-identity golden (MEMORY-ENTITIES-S07, Р13).

Imports only the API that exists before the participants work (merge-base a9c0e37c), so the golden can be produced there."""
import json
import re

from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.wire_v4 import memory_wire_v4_schema
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from tests.link_helpers import approve_links

_DERIVED=r'\bm[ce]_[0-9a-f]{24}\b'


def normalize_ids(text,ids):
    """Every story, scene and version id and every derived mc_/me_ id becomes <id0>, <id1>… in order of first appearance."""
    names={}
    pattern=re.compile('|'.join([*(re.escape(i) for i in sorted(set(ids),key=len,reverse=True)),_DERIVED]))
    return pattern.sub(lambda match:names.setdefault(match.group(0),f'<id{len(names)}>'),text)


def cardless_memory_request(tmp_path) -> dict[str,str]:
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Без карток'))
    if story.content_rating is None:  # the application creates stories unrated; the conftest fixture is not available in the old tree
        rating=ContentRating(sexual=0,violence=0,themes=0)
        story=story.model_copy(update={'content_rating':rating,'initial_content_rating':rating})
        with repo.db.connection() as db:db.execute('UPDATE stories SET payload=? WHERE id=?',(story.model_dump_json(),story.id))
    first=repo.create_scene(story.id,SceneCreate(title='1',beats='Вдома',character_ids=['A','B']))
    second=repo.create_scene(story.id,SceneCreate(title='2',beats='Маяк і стара карта',character_ids=['A']))
    p1=repo.save_version(story.id,first.id,'manual','Анна і Борис удома. На маяку горить світло.',[])
    repo.set_head(first.id,'prose',p1.id,repo.get_scene(first.id).revision)
    events=[_add_event('character_states','Анна втомлена',p1.id,'удома',0,['A']),
        _add_event('character_states','Іде дощ',p1.id,'удома',0),
        _add_event('facts','На маяку горить світло',p1.id,'На маяку горить світло',0),
        _add_event('open_threads','Анна шукає стару карту',p1.id,'удома',0),
        _add_event('timeline','Анна і Борис зустрілися вдома',p1.id,'Анна і Борис удома',0)]
    journal=MemoryJournal(schema_version=3,source_prose_ids=[p1.id],events=events)
    memory=repo.save_version(story.id,first.id,'memory',journal.model_dump_json(),[p1.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    p2=repo.save_version(story.id,second.id,'manual','Анна дивиться на дощ і згадує маяк.',[])
    repo.set_head(second.id,'prose',p2.id,repo.get_scene(second.id).revision)
    approve_links(repo,story.id)
    role=RoleSettings(provider=ProviderSettings(model='fake'),memory_mode='evidence_delta',context_tokens=262144)
    context=build_context(repo,second.id,'memory',role)
    ids=[story.id,first.id,second.id,p1.id,memory.id,p2.id]
    bounds=context.fragments['memory_schema_bounds']
    schema=json.dumps(memory_wire_v4_schema(json.loads(bounds)),sort_keys=True,ensure_ascii=False)
    return {key:normalize_ids(value,ids) for key,value in
        {'user_text':context.user_text,'bounds':bounds,'schema':schema}.items()}
