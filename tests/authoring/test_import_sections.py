import pytest
from storygen.authoring.import_sections import split_plan, explicit_scene_number
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository

@pytest.mark.parametrize('ending',['\n','\r\n','\r'])
def test_sections_keep_exact_text_and_unnumbered_subheadings(ending):
    raw=ending.join(['# План','Вступ','## Сцена 02: Зустріч','Опис','## Інтерлюдія','### Спогад','Текст'])
    preamble,sections=split_plan(raw)
    assert preamble==ending.join(['# План','Вступ'])+ending
    assert [s.author_scene_number for s in sections]==[2,None]
    assert [s.title for s in sections]==['Зустріч','Інтерлюдія']
    assert '### Спогад' in sections[1].text
    assert preamble+''.join(s.text for s in sections)==raw


def test_fallback_is_not_author_number():
    assert split_plan('Довільний план')[1][0].author_scene_number is None
    assert explicit_scene_number('Сцена 2. Зустріч')==2
    assert explicit_scene_number('Сцена 2: Друзі')==2


def test_manual_plan_number_updates_and_conflict_is_atomic(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    a=repo.create_scene(story.id,SceneCreate(title='Перша',beats='Сцена 2: Назва'))
    b=repo.create_scene(story.id,SceneCreate(title='Друга',beats='Сцена 3: Назва'))
    assert a.author_scene_number==2
    with pytest.raises(ValueError):repo.update_scene_plan(a.id,'Сцена 3: Інша',a.revision)
    assert repo.get_scene(a.id).beats==a.beats
    a=repo.update_scene_plan(a.id,'Без номера',a.revision)
    assert a.author_scene_number is None
