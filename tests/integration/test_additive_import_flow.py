from storygen.authoring.imports import SourceFile,import_sources
from storygen.characters.models import load_characters
from storygen.characters.service import save_character_material
from storygen.domain import StoryCreate
from storygen.storage.repository import Repository
from storygen.storage.integrity import check_integrity
from storygen.storage.backup import create_backup,restore_backup
from storygen.generation.prepare_sources import prepare_sources
from storygen.generation.context import make_context
from storygen.providers.models import RoleSettings,ProviderSettings


def test_additive_flow_current_cards_prepare_snapshot_and_backup(tmp_path):
    root=tmp_path/'data';repo=Repository(root);story=repo.create_story(StoryCreate(title='Твір'))
    def upload(text,kind):return import_sources(repo,story.id,[SourceFile(name='file.md',raw=text.encode(),kind=kind)])
    upload('Вступ\n## Сцена 1: Ранок\nПерсонажі: Анна','source_plan')
    upload('## Анна\nПочатковий факт','source_characters')
    current=repo.get_story(story.id)
    cards=[c.model_dump() for c in load_characters(repo.read_text(current.characters_version_id))]
    cards[0]['entries'].append(dict(id=None,text='Ручна авторська правка',origin='author',sources=[],availability='timeless',available_from_scene_id=None))
    save_character_material(repo,story.id,cards,current.revision)
    upload('## Анна\nЧужа заміна\n## Марія\nНовий факт','source_characters')
    upload('## Сцена 1: Інша назва\nНе приймати\n## Сцена 2. Вечір\nПерсонажі: Марія','source_plan')
    view=repo.context_view(story.id);current=view.get_story(story.id)
    sources=prepare_sources(view,current)
    assert sources[-1].id==current.characters_version_id
    assert 'Ручна авторська правка' in view.read_text(sources[-1].id)
    assert 'Чужа заміна' not in view.read_text(sources[-1].id)
    role=RoleSettings(provider=ProviderSettings(model='synthetic'))
    context=make_context(view,current,None,'prepare',role,[view.read_text(v.id) for v in sources],[v.id for v in sources])
    assert any(s.kind=='story' and s.field=='characters_version_id' and s.expected==current.characters_version_id for s in context.dependency_snapshot.selectors)
    assert check_integrity(root).ok,check_integrity(root).to_dict()
    active=repo.active_source(story.id,'source_plan')
    backup=create_backup(root,tmp_path/'backup');restored=restore_backup(backup,tmp_path/'restored')
    copy=Repository(restored)
    assert copy.active_source(story.id,'source_plan').id==active.id
    assert copy.read_text(active.id)==repo.read_text(active.id)
    assert [s.author_scene_number for s in copy.list_scenes(story.id)]==[1,2]
    assert check_integrity(restored).ok
