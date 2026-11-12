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


def test_unnumbered_markdown_before_txt_number_is_a_scene():
    text='## Інтерлюдія\nТиша\nСцена 2: Зустріч\nРозмова'
    preamble,sections=split_plan(text)
    assert preamble==''
    assert [s.author_scene_number for s in sections]==[None,2]


@pytest.mark.parametrize('title',['# План: Маяк на пристані','# Маяк на пристані','#\tMy story'])
@pytest.mark.parametrize('ending',['\n','\r\n'])
def test_opening_title_before_txt_scenes_is_preamble(title,ending):
    raw=ending.join(['',title,'','Робоча назва: Маяк','Сцена 1: Лист','Опис','','Scene 2. Pier','Text',''])
    preamble,sections=split_plan(raw)
    assert preamble==ending.join(['',title,'','Робоча назва: Маяк',''])
    assert [s.author_scene_number for s in sections]==[1,2]
    assert preamble+''.join(s.text for s in sections)==raw


def test_opening_title_does_not_change_the_level_of_other_headings():
    preamble,sections=split_plan('# Маяк\n## Інтерлюдія\nТиша\nСцена 2: Зустріч\nРозмова\n### Спогад\nТекст')
    assert preamble=='# Маяк\n'
    assert [(s.title,s.author_scene_number) for s in sections]==[('Інтерлюдія',None),('Зустріч',2)]


@pytest.mark.parametrize('text',[
    '# Пролог\nТиша\nСцена 1: Лист\nОпис\n# Епілог\nКінець',   # two level-1 headings: both are scenes
    'Вступ\n# Пролог\nТиша\nСцена 1: Лист\nОпис',               # not the first line of the file
])
def test_level_one_heading_that_is_not_a_lone_opening_title_stays_a_scene(text):
    sections=split_plan(text)[1]
    assert sections[0].title=='Пролог' and sections[0].author_scene_number is None


def test_opening_title_without_numbered_scenes_stays_a_scene():
    assert [s.title for s in split_plan('# Маяк\nОпис\n## Деталі\nТекст')[1]]==['Маяк']


def test_numbered_markdown_scenes_keep_the_level_rule():
    preamble,sections=split_plan('# Пролог\nТиша\n# Сцена 1: Лист\nОпис')
    assert preamble=='' and [s.author_scene_number for s in sections]==[None,1]
