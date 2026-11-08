from memory_bench.extract import extract_story, name_stems, records_from_journal
from memory_bench.model import render
from storygen.memory.journal import load_memory
from storygen.memory.projection import project_memory


def test_extract_targets_are_updates_and_retires_of_that_scene(synthetic_repo):
    repo,story_id,info=synthetic_repo
    scenes,skipped=extract_story(repo,story_id)
    assert [s.targets for s in scenes]==[frozenset(),frozenset(),{info['state']},{info['thread']}]
    assert not any(skipped.values())


def test_extract_state_before_scene_and_hidden(synthetic_repo):
    repo,story_id,info=synthetic_repo
    scenes,_=extract_story(repo,story_id)
    assert scenes[0].records==() and scenes[0].timeline==()
    # added in scene 2 and switched off there: hidden from scene 3 on, still in the stored journal
    assert info['hidden'] not in {r.claim_id for r in scenes[2].records}|{r.claim_id for r in scenes[3].records}
    assert info['fact'] in {r.claim_id for r in scenes[2].records}
    state=next(r for r in scenes[3].records if r.claim_id==info['state'])
    assert state.text=='Марія без халата' and state.last_changed_scene==3 and state.source_scene==3


def test_extract_protagonist_names_plan_prose(synthetic_repo):
    repo,story_id,info=synthetic_repo
    scenes,_=extract_story(repo,story_id)
    assert scenes[0].protagonist==info['maria'] and scenes[0].names[info['ostap']]=='Остап'
    assert scenes[1].plan_text=='План 2' and scenes[2].prose_text=='Марія зняла халат.'
    assert extract_story(repo,story_id,protagonist=info['ostap'])[0][0].protagonist==info['ostap']


def test_extract_first_meetings(synthetic_repo):
    repo,story_id,_=synthetic_repo
    assert [s.first_meetings for s in extract_story(repo,story_id)[0]]==[1,1,0,0]


def test_extract_skips_scene_needing_confirmation(synthetic_repo):
    from storygen.generation.dependencies import save_manual_prose
    repo,story_id,_=synthetic_repo
    first=repo.list_scenes(story_id)[0]
    save_manual_prose(repo,first.id,'Інша проза першої сцени.',first.revision)
    scenes,skipped=extract_story(repo,story_id)
    assert skipped['skipped_needs_confirmation']>=1 and len(scenes)<4


def test_records_from_journal_render_parity(synthetic_repo):
    repo,story_id,_=synthetic_repo
    last=repo.list_scenes(story_id)[-1]
    journal=load_memory(repo.read_text(last.heads['memory']))
    numbers={pid:i+1 for i,pid in enumerate(journal.source_prose_ids)}
    records,timeline=records_from_journal(journal,numbers,set())
    assert render(records,timeline)==project_memory(journal,[],numbers).text


def test_name_stems_inflection_and_apostrophe():
    assert name_stems('Марія')==('марі',) and name_stems('Мар’яна')==name_stems("Мар'яна")
    assert name_stems('Ія')==() and name_stems('Анна Петрівна')==('анна','петрівн')


def test_scene_targets_only_from_own_prose():
    from memory_bench.extract import scene_targets
    from storygen.memory.journal import MemoryEvent, MemoryJournal
    ev=lambda n,c,op,src:MemoryEvent(event_id=n,claim_id=c,operation=op,category='open_threads',text='t',source_version_id=src,quote='q')
    past=MemoryJournal(source_prose_ids=['p1'],events=[ev('e1','a','add','p1'),ev('e2','b','add','p1')])
    own=MemoryJournal(source_prose_ids=['p1','p2'],events=[ev('e1','a','add','p1'),ev('e2','b','add','p1'),
        ev('e9','a','update','p1'),ev('e3','b','retire','p2')])
    assert scene_targets(own,past,{'p2'})=={'b'}


def test_extract_skips_scene_whose_previous_has_no_memory(tmp_path):
    from storygen.domain import SceneCreate, StoryCreate
    from storygen.generation.dependencies import save_manual_prose
    from storygen.storage.repository import Repository
    repo=Repository(tmp_path/'d');story=repo.create_story(StoryCreate(title='Т'))
    first=repo.create_scene(story.id,SceneCreate(title='1'));repo.create_scene(story.id,SceneCreate(title='2'))
    save_manual_prose(repo,first.id,'Проза.',first.revision)
    scenes,skipped=extract_story(repo,story.id)
    assert len(scenes)==1 and skipped['skipped_no_memory']==1 and skipped['skipped_needs_confirmation']==0


def test_extract_counts_hidden_and_absent_targets(synthetic_repo):
    repo,story_id,_=synthetic_repo
    _,counts=extract_story(repo,story_id)
    assert counts['targets_hidden']==0 and counts['targets_absent']==0
