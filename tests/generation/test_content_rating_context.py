import json
import pytest

from storygen.domain import StoryCreate,SceneCreate,ContentRating
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.generation.context import build_context,make_context

pytestmark=pytest.mark.unrated_stories  # each test sets the ratings it needs explicitly

UNSET='Задайте віковий рейтинг твору в налаштуваннях, щоб запустити генерацію.'
BLOCK='ВІКОВИЙ РЕЙТИНГ СЦЕНИ — МЕЖА, ЯКУ НЕ МОЖНА ПЕРЕВИЩУВАТИ'


def R(s,v,t):
    return ContentRating(sexual=s,violence=v,themes=t)


def settings(**kw):
    return RoleSettings(provider=ProviderSettings(model='fake'),**kw)


def card(id,name,*texts):
    return {'schema_version':2,'id':id,'name':name,'entries':[
        {'id':f'{id}{i}','text':text,'availability':'timeless','available_from_scene_id':None,'origin':'author','sources':[]}
        for i,text in enumerate(texts)]}


def make_story(tmp_path,rating=None,cast=('A',),cards=None,count=1,scene_ratings=None):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Нейтральний твір'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'Сцена {i+1}',beats='Прогулянка',character_ids=list(cast))) for i in range(count)]
    if cards is not None:
        ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
        repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    if rating is not None:
        repo.update_story_rating(story.id,rating,repo.get_story(story.id).revision)
    for index,value in (scene_ratings or {}).items():
        repo.update_scene_rating(scenes[index].id,value,repo.get_scene(scenes[index].id).revision)
    return repo,repo.get_story(story.id),[repo.get_scene(s.id) for s in scenes]


def with_heads(repo,scene,*heads):
    texts={'brief':('brief','{"objective":"Подія","beats":["Подія"]}'),'draft':('draft','Чернетка сцени.'),'prose':('manual','Готова проза.')}
    for head in heads:
        kind,text=texts[head]
        ref=repo.save_version(scene.story_id,scene.id,kind,text,[])
        repo.set_head(scene.id,head,ref.id,repo.get_scene(scene.id).revision)
    return repo.get_scene(scene.id)


ADULTS=[card('A','Анна','Вік: 30')]


def test_unrated_story_blocks_all_stages(tmp_path):
    repo,story,scenes=make_story(tmp_path,cast=(),cards=None)
    with_heads(repo,scenes[0],'prose')
    with pytest.raises(ValueError,match='Задайте віковий рейтинг твору'):
        make_context(repo,story,None,'prepare',settings(),['Джерело'],[])
    for stage in ['brief','memory']:
        with pytest.raises(ValueError) as error:
            build_context(repo,scenes[0].id,stage,settings())
        assert str(error.value)==UNSET


def test_minor_blocks_sexual_scene(tmp_path):
    cards=[card('A','Анна','Вік: 15'),card('B','Борис','Професія: лікар')]
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cast=('A','B'),cards=cards)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    message=str(error.value)
    assert message==('Генерацію заблоковано: сцена має рейтинг сексуального змісту 1, а персонаж «Анна» молодший за 18; '
        'персонаж «Борис» не має вказаного віку. Допишіть у картку рядок «Вік: …» (число від 18 або «дорослий»), '
        'приберіть персонажа зі складу сцени або позначте сцену рейтингом «сексуальний зміст 0».')


def test_participant_without_card_uses_id_and_list_is_capped(tmp_path):
    cast=('A','X1','X2','X3','X4','X5')
    repo,story,scenes=make_story(tmp_path,R(2,0,0),cast=cast,cards=ADULTS)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    message=str(error.value)
    assert 'персонаж «X1» не має вказаного віку' in message
    assert 'X5' in message and 'Анна' not in message
    assert message.count('персонаж «')==5


def test_child_allowed_when_scene_sexual_zero(tmp_path):
    repo,story,scenes=make_story(tmp_path,R(2,0,0),cards=[card('A','Анна','Вік: 10')],scene_ratings={0:R(0,0,0)})
    context=build_context(repo,scenes[0].id,'brief',settings())
    assert 'Сексуальний зміст (еротика та інтимні сцени): рівень 0 — без сексуального змісту; романтика без еротичних подробиць.' in context.system_text


def test_empty_cast_and_missing_cards_block(tmp_path):
    repo,story,scenes=make_story(tmp_path/'empty',R(1,0,0),cast=(),cards=ADULTS)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    assert str(error.value)=='Сцена має рейтинг сексуального змісту 1, але склад сцени порожній. Укажіть учасників, щоб перевірити їхній вік.'
    repo,story,scenes=make_story(tmp_path/'cards',R(2,0,0),cast=('A',),cards=None)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    assert str(error.value)=='Сцена має рейтинг сексуального змісту 2. Підготуйте картки персонажів із рядком «Вік:», щоб перевірити вік учасників.'


def test_adult_cast_builds_with_rating_block(tmp_path):
    repo,story,scenes=make_story(tmp_path,R(1,2,0),cards=ADULTS)
    context=build_context(repo,scenes[0].id,'brief',settings())
    assert (BLOCK+'\n'
        'Сексуальний зміст (еротика та інтимні сцени): рівень 1 — дорослий сексуальний зміст без графічних подробиць.\n'
        'Насильство (фізична шкода, яку показано в тексті: бійки, поранення, вбивства, катування): рівень 2 — графічне насильство допустиме.\n'
        'Жорсткі теми (важкі теми, про які йдеться в тексті, навіть без фізичного насильства: самогубство й самоушкодження, залежності, психологічне насильство й цькування, дискримінація, тяжка втрата): рівень 0 — жорсткі теми лише згадуються, без зображення.\n'
        'Межа не вимагає досягати рівня: пиши так, як потребує сцена.') in context.system_text
    assert BLOCK not in context.user_text
    with_heads(repo,scenes[0],'prose')
    memory=build_context(repo,scenes[0].id,'memory',settings())
    assert BLOCK not in memory.system_text and BLOCK not in memory.user_text
    prepare=make_context(repo,repo.get_story(story.id),None,'prepare',settings(),['Джерело'],[])
    assert BLOCK not in prepare.system_text


def test_minor_blocks_memory_stage_too(tmp_path):
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cards=[card('A','Анна','Вік: 15')])
    with_heads(repo,scenes[0],'prose')
    with pytest.raises(ValueError,match='молодший за 18'):
        build_context(repo,scenes[0].id,'memory',settings())


def test_higher_rated_scenes_listed(tmp_path):
    from storygen.rating.instructions import rating_instructions
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cards=ADULTS,count=3,scene_ratings={1:R(2,0,0)})
    text=rating_instructions(repo.context_view(story.id),story,scenes[2],'brief',settings())
    assert ('СЦЕНИ З ВИЩИМ РЕЙТИНГОМ: 2 (сексуальний зміст).\n'
        'Не переказуй і не згадуй їхніх подробиць понад межу цієї сцени; можна посилатися лише на події, важливі для сюжету.') in text
    # The future plan of scene 2 enters the request of scene 1 through the horizon.
    context=build_context(repo,scenes[0].id,'brief',settings())
    assert 'СЦЕНИ З ВИЩИМ РЕЙТИНГОМ: 2 (сексуальний зміст).' in context.system_text
    # Scene 2 is the highest; nothing above it.
    assert 'СЦЕНИ З ВИЩИМ' not in rating_instructions(repo.context_view(story.id),story,scenes[1],'brief',settings())


def test_higher_scenes_block_groups_by_axes():
    from storygen.rating.instructions import higher_scenes_block
    assert higher_scenes_block([])==''
    assert higher_scenes_block([(5,['sexual']),(7,['violence']),(9,['sexual']),(10,['sexual','themes'])]).splitlines()[0]==\
        'СЦЕНИ З ВИЩИМ РЕЙТИНГОМ: 5, 9 (сексуальний зміст); 7 (насильство); 10 (сексуальний зміст, жорсткі теми).'


def test_diff_edit_user_text_untouched(tmp_path):
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cards=ADULTS,count=2,scene_ratings={1:R(2,0,0)})
    with_heads(repo,scenes[0],'brief','draft')
    context=build_context(repo,scenes[0].id,'edit',settings(edit_mode='diff'))
    assert context.user_text=='Чернетка сцени.'
    assert BLOCK in context.system_text
    assert 'СЦЕНИ З ВИЩИМ' not in context.system_text


def test_rating_change_changes_fingerprint(tmp_path):
    repo,story,scenes=make_story(tmp_path,R(0,0,0),cards=ADULTS)
    before=build_context(repo,scenes[0].id,'brief',settings())
    repo.update_scene_rating(scenes[0].id,R(0,1,0),repo.get_scene(scenes[0].id).revision)
    after=build_context(repo,scenes[0].id,'brief',settings())
    assert before.fingerprint!=after.fingerprint


def test_guard_message_has_english_translation(tmp_path):
    from storygen.web.localization import diagnostic
    cards=[card('A','Анна','Вік: 15'),card('B','Борис','Професія: лікар')]
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cast=('A','B'),cards=cards)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    english=diagnostic(str(error.value),'en')
    assert english.startswith('Generation blocked: the scene has sexual content rating 1')
    assert 'character “Анна” is under 18; character “Борис” has no age specified.' in english
    assert 'персонаж' not in english
    assert diagnostic(UNSET,'en')=="Set the story's age rating in settings to start generation."
    for text in ['Сцена має рейтинг сексуального змісту 1, але склад сцени порожній. Укажіть учасників, щоб перевірити їхній вік.',
                 'Сцена має рейтинг сексуального змісту 2. Підготуйте картки персонажів із рядком «Вік:», щоб перевірити вік учасників.']:
        assert diagnostic(text,'en')!=text


@pytest.mark.parametrize('mode',['patches','diff'])
def test_trashed_anchor_age_blocks_patch_and_diff_edit(tmp_path,mode):
    cards=[{'schema_version':2,'id':'A','name':'Анна','entries':[
        {'id':'A0','text':'Вік: 30','availability':'timeless','available_from_scene_id':None,'origin':'author','sources':[]},
        {'id':'A1','text':'Вік: 16','availability':'from_scene','available_from_scene_id':None,'origin':'author','sources':[]}]}]
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cards=None,count=2)
    cards[0]['entries'][1]['available_from_scene_id']=scenes[1].id
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    with_heads(repo,scenes[0],'brief','draft')
    repo.set_scene_trashed(story.id,scenes[1].id,repo.get_scene(scenes[1].id).revision,False)
    with pytest.raises(ValueError,match='персонаж «Анна» не має вказаного віку'):
        build_context(repo,scenes[0].id,'edit',settings(edit_mode=mode))


def test_remaining_run_readiness_checks_every_target_scene(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.readiness import preview
    from storygen.generation.worker import RunRequest
    cards=[card('A','Анна','Вік: 30'),card('B','Борис','Вік: 15')]
    # Scene 1 (sexual 0) may include the minor; scene 2 (sexual 1) may not.
    repo,story,scenes=make_story(tmp_path,R(0,0,0),cast=('A','B'),cards=cards,count=2,scene_ratings={1:R(1,0,0)})
    for role in ['planner','writer','editor','memory']:
        save_role_settings(repo,story.id,role,settings(),repo.get_story(story.id).revision)
    single=preview(repo,RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='scene'))
    assert single['ready'],single['reason']
    result=preview(repo,RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='remaining'))
    assert not result['ready']
    assert 'персонаж «Борис» молодший за 18' in result['reason']



def test_more_than_five_failing_participants_adds_rest_hint(tmp_path):
    from storygen.web.localization import diagnostic
    cast=('X1','X2','X3','X4','X5','X6','X7')
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cast=cast,cards=ADULTS)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    message=str(error.value)
    assert message.count('персонаж «')==5 and 'X6' not in message
    assert 'персонаж «X5» не має вказаного віку; і ще 2. Допишіть у картку' in message
    english=diagnostic(message,'en')
    assert 'character “X5” has no age specified; and 2 more. Add an “Age: …” line' in english
    assert 'персонаж' not in english and 'і ще' not in english
    # Exactly five failing participants carry no hint.
    repo,story,scenes=make_story(tmp_path/'five',R(1,0,0),cast=cast[:5],cards=ADULTS)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    assert 'і ще' not in str(error.value)


def test_age_only_in_later_entry_names_the_scene(tmp_path):
    from storygen.web.localization import diagnostic
    cards=[{'schema_version':2,'id':'A','name':'Анна','entries':[
        {'id':'A0','text':'Вік: 25','availability':'from_scene','available_from_scene_id':None,'origin':'author','sources':[]}]},
        card('B','Борис','Професія: лікар')]
    repo,story,scenes=make_story(tmp_path,R(1,0,0),cast=('A','B'),cards=None,count=2)
    cards[0]['entries'][0]['available_from_scene_id']=scenes[1].id
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    with pytest.raises(ValueError) as error:
        build_context(repo,scenes[0].id,'brief',settings())
    message=str(error.value)
    assert ('а вік персонажа «Анна» указано лише у відомості, доступній від сцени 2 «Сцена 2» '
        '(перевірте «Першу сцену доступності»); персонаж «Борис» не має вказаного віку.') in message
    english=diagnostic(message,'en')
    assert ('the age of character “Анна” is set only in an entry available from scene 2 “Сцена 2” '
        '(check “First available scene”); character “Борис” has no age specified.') in english
    assert 'персонаж' not in english


EDITION='Генерацію заблоковано: рейтинг «сексуальний зміст» тут 2, а в цьому виданні Obscura найвищий дозволений рівень — 1. Знизьте рейтинг сцени або твору.'


def force_rating(repo,table,id,rating):
    """Write a rating straight into the payload, as data made in the full edition would arrive."""
    with repo.db.connection() as db:
        raw=json.loads(db.execute(f'SELECT payload FROM {table} WHERE id=?',(id,)).fetchone()[0])
        raw['content_rating']=rating.model_dump()
        if table=='stories':raw['initial_content_rating']=rating.model_dump()
        db.execute(f'UPDATE {table} SET payload=? WHERE id=?',(json.dumps(raw),id))


def blocked(repo,scene_id,stage='brief'):
    with pytest.raises(ValueError) as error:
        build_context(repo,scene_id,stage,settings())
    return str(error.value)


def test_store_edition_blocks_scene_with_own_level_two(tmp_path,store_edition):
    repo,story,scenes=make_story(tmp_path,rating=R(0,0,0),cards=ADULTS)
    force_rating(repo,'scenes',scenes[0].id,R(2,0,0))
    with_heads(repo,scenes[0],'prose')
    assert blocked(repo,scenes[0].id)==EDITION and blocked(repo,scenes[0].id,'memory')==EDITION


def test_store_edition_blocks_scene_inheriting_level_two(tmp_path,store_edition):
    repo,story,scenes=make_story(tmp_path,rating=R(0,0,0),cards=ADULTS)
    force_rating(repo,'stories',story.id,R(2,0,0))
    assert scenes[0].content_rating is None and blocked(repo,scenes[0].id)==EDITION


def test_store_edition_blocks_story_stage_without_scene(tmp_path,store_edition):
    repo,story,scenes=make_story(tmp_path,rating=R(0,0,0),cards=ADULTS)
    force_rating(repo,'stories',story.id,R(2,0,0))
    with pytest.raises(ValueError) as error:
        make_context(repo,repo.get_story(story.id),None,'prepare',settings(),['Джерело'],[])
    assert str(error.value)==EDITION


def test_store_edition_limit_comes_before_cast_checks(tmp_path,store_edition):
    repo,story,scenes=make_story(tmp_path,rating=R(0,0,0),cast=(),cards=None)
    force_rating(repo,'scenes',scenes[0].id,R(2,0,0))
    assert blocked(repo,scenes[0].id)==EDITION


def test_store_edition_allows_level_one_and_other_axes(tmp_path,store_edition):
    repo,story,scenes=make_story(tmp_path,rating=R(1,2,2),cards=ADULTS)
    assert BLOCK in build_context(repo,scenes[0].id,'brief',settings()).system_text


def test_store_edition_does_not_block_reading_or_manual_edit(tmp_path,store_edition):
    repo,story,scenes=make_story(tmp_path,rating=R(0,0,0),cards=ADULTS)
    force_rating(repo,'stories',story.id,R(2,0,0))
    assert repo.get_story(story.id).content_rating==R(2,0,0) and len(repo.list_scenes(story.id))==1
    scene=with_heads(repo,scenes[0],'prose')
    assert repo.read_text(scene.heads['prose'])=='Готова проза.'


def test_full_edition_level_two_unchanged(tmp_path):
    repo,story,scenes=make_story(tmp_path,rating=R(2,0,0),cards=ADULTS)
    assert BLOCK in build_context(repo,scenes[0].id,'brief',settings()).system_text


def test_edition_guard_message_has_english_translation():
    from storygen.web.localization import diagnostic
    assert diagnostic(EDITION,'en')=='Generation is blocked: the “sexual content” rating here is 2, and the highest level allowed in this edition of Obscura is 1. Lower the rating of the scene or the story.'


def test_edition_messages_translate_for_every_axis():
    from storygen.rating.guard import EDITION_LIMIT
    from storygen.rating.instructions import AXIS_NAMES
    from storygen.storage.authoring import SAVE_LIMIT
    from storygen.web.localization import diagnostic
    english={'sexual':'sexual content','violence':'violence','themes':'hard themes'}
    for axis,name in AXIS_NAMES.items():
        for template in (EDITION_LIMIT,SAVE_LIMIT):
            text=template.format(axis=name,n=2,max=1)
            translated=diagnostic(text,'en')
            assert translated!=text and english[axis] in translated and name not in translated
