"""Synthetic UI fixture. Never opens production data, dotenv or real gateways."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
# The checkout's own sources first: in a worktree the virtualenv's editable install points at another checkout.
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'src'))

import uvicorn

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate, SceneCreate
from storygen.web.app import create_app


def forbidden_gateway(*args, **kwargs):
    from storygen.providers.streaming import GenerationEvent
    class Fake:
        def stream(self,context,cancel):
            if context.settings.provider.model=='synthetic-slow':  # any stage: holds the run until it is cancelled
                cancel.wait(15)
                yield GenerationEvent(type='cancelled')
                return
            if context.stage=='publication_suggest' and context.settings.provider.model=='synthetic-card-writer':
                # R16-SUGGEST-S07: a card proposal for the long book (neutral text).
                import json
                yield GenerationEvent(type='delta',text=json.dumps({'title':None,'annotation':'Доглядачка маяка шукає брата.',
                    'genres':['short_story'],'keywords':['маяк']},ensure_ascii=False))
                yield GenerationEvent(type='terminal',finish_reason='stop')
                return
            if context.stage=='edit' and context.settings.provider.model=='synthetic-no-changes':
                yield GenerationEvent(type='delta',text='{"edits":[]}')
                yield GenerationEvent(type='terminal',finish_reason='stop')
                return
            if context.stage=='draft' and context.settings.provider.model=='synthetic-writer':
                # A long draft: the page is taller than the window, so where the workspace scrolls is visible.
                yield GenerationEvent(type='delta',text='\n\n'.join(f'Абзац {n}: Лєра йшла парком і рахувала ліхтарі, поки вечір густішав над озером.' for n in range(1,61)))
                yield GenerationEvent(type='terminal',finish_reason='stop')
                return
            if context.stage.startswith('audit_') and context.settings.provider.model=='synthetic-auditor':
                # VALID-LINKS: the auditor sees two discrepancies with quotes (neutral text).
                import json
                yield GenerationEvent(type='delta',text=json.dumps({'confidence':35,'summary':'Завдання може розходитися з планом',
                    'discrepancies':[{'text':'Місце дії не збігається з планом','quote':'Світло на воді'},
                                     {'text':'Немає кроку про човен','quote':'Маяк'}]},ensure_ascii=False))
                yield GenerationEvent(type='terminal',finish_reason='stop')
                return
            if context.stage.startswith('audit_') and context.settings.provider.model=='synthetic-book-auditor':
                # R-44 book validation: only a brief that names «Світло на воді» disagrees; everything else is valid.
                import json
                wrong=context.stage=='audit_brief' and 'Світло на воді' in context.user_text
                yield GenerationEvent(type='delta',text=json.dumps({'confidence':40,'summary':'Завдання може розходитися з планом',
                    'discrepancies':[{'text':'Місце дії не збігається з планом','quote':'Світло на воді'}]} if wrong else
                    {'confidence':95,'summary':'Узгоджено','discrepancies':[]},ensure_ascii=False))
                yield GenerationEvent(type='terminal',finish_reason='stop')
                return
            if context.stage!='rewrite' or context.settings.provider.model!='synthetic-rewrite':raise AssertionError('Only synthetic rewrite is allowed')
            yield GenerationEvent(type='delta',text='Лєра побачила **сузір’я**.\n\nВечір був _спокійним_.')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    return Fake()


CORE_PROSE1='Анна в халаті.\nУ кишені ключ.\nХто стукав у двері?'
CORE_PROSE2='Анна вдягла пальто.\nСтукав сусід.'


def core_review_fixture(repo,story):
    """Two scenes; scene 2 memory comes from a captured v4 answer: clothing changed, carried unknown, thread closed."""
    import threading
    from storygen.domain import SceneCreate
    from storygen.generation.context import build_context
    from storygen.generation.stages import execute_stage
    from storygen.memory.journal import MemoryJournal,_add_event
    from storygen.providers.models import ProviderSettings,RoleSettings
    from storygen.providers.streaming import GenerationEvent
    from tests.memory.wire_helpers import core_unchanged,v4_response
    from tests.storage.test_memory_core_selectors import cards
    repo.publish_story_material(story.id,'characters_version_id',cards(repo,story.id,'A'),repo.get_story(story.id).revision)
    s1,s2=(repo.create_scene(story.id,SceneCreate(title=title,beats='Анна.',character_ids=['A'])) for title in ('Ранок','Гість'))
    p1=repo.save_version(story.id,s1.id,'manual',CORE_PROSE1,[])
    repo.set_head(s1.id,'prose',p1.id,repo.get_scene(s1.id).revision)
    thread=_add_event('open_threads','Хто стукав?',p1.id,'Хто стукав у двері?',0)
    journal=MemoryJournal(schema_version=3,source_prose_ids=[p1.id],events=[
        _add_event('character_states','Халат',p1.id,'Анна в халаті.',0,['A'],slot='clothing'),
        _add_event('character_states','Ключ',p1.id,'У кишені ключ.',0,['A'],slot='carried'),thread])
    memory=repo.save_version(story.id,s1.id,'memory',journal.model_dump_json(),[p1.id])
    repo.set_head(s1.id,'memory',memory.id,repo.get_scene(s1.id).revision)
    from tests.link_helpers import approve_links
    approve_links(repo,story.id)  # VALID-LINKS: hand-made memory stands for confirmed
    p2=repo.save_version(story.id,s2.id,'manual',CORE_PROSE2,[])
    repo.set_head(s2.id,'prose',p2.id,repo.get_scene(s2.id).revision)
    core=core_unchanged('A')
    core['A']['clothing']={'status':'changed','text':'Пальто','evidence_ids':['f000001'],'reason':''}
    core['A']['carried']={'status':'unknown','text':'','evidence_ids':[],'reason':'Ключ більше не згадано'}
    raw=v4_response(core,{thread.claim_id:{'status':'closed','resolution':'Стукав сусід','evidence_ids':['f000002']}})
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    role=RoleSettings(provider=ProviderSettings(model='synthetic'),memory_mode='evidence_delta',context_tokens=32768)
    attempt=execute_stage(repo,s2.id,'memory',build_context(repo,s2.id,'memory',role),Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='completed',attempt.error
    return {'story_id':story.id,'scene_id':s2.id,'first_scene_id':s1.id}


def main():
    import os
    configured = os.environ.get('OBSCURA_BROWSER_TEST_ROOT')
    test_root = Path(configured) if configured else Path('C:/tmp') if os.name == 'nt' else None
    if test_root is not None:
        test_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='obscura-browser-', dir=test_root) as directory:
        root = Path(directory)
        profile = root/'home'
        profile.mkdir()
        for key in ('HOME', 'USERPROFILE'):
            os.environ[key] = str(profile)
        os.environ['CODEX_HOME'] = str(root/'codex')
        port = int(sys.argv[1]) if len(sys.argv)>1 else 8976
        app = create_app(AppSettings(data_dir=root/'data', env_file=root/'absent.env', port=port),
                         gateway_factory=forbidden_gateway, evaluator_factory=forbidden_gateway)
        repo = app.state.repo
        # SECURITY-002: specs never touch the real OS credential store or the keys of this machine.
        import os
        from storygen.providers import secrets
        for name in ('OPENROUTER_API_KEY','VENICE_API_KEY'):os.environ.pop(name,None)

        class MemorySecretStore:
            def __init__(self):self.items={}
            def get(self,name):return self.items.get(name)
            def set(self,name,value):self.items[name]=value
            def delete(self,name):self.items.pop(name,None)
        secrets.set_backend(MemorySecretStore())

        @app.post('/test-secret-store')
        def reset_secret_store(body: dict):
            # Empties the in-memory store; {"available": false} simulates a machine without one,
            # {"env": {"NAME": "value"}} sets or (null) clears environment variables of the server.
            secrets.set_backend(MemorySecretStore() if body.get('available',True) else None)
            for name,value in (body.get('env') or {}).items():
                if value is None:os.environ.pop(name,None)
                else:os.environ[name]=value
            return {'available': secrets.store_available()}
        def rated_story(title):
            # Generation is blocked for an unrated story; browser fixtures start rated like conftest stories.
            from storygen.domain import ContentRating
            story = repo.create_story(StoryCreate(title=title))
            return repo.update_story_rating(story.id, ContentRating(sexual=0, violence=0, themes=0), story.revision)
        def make_fixture():
            story = rated_story('Нічний каталог')
            scene = repo.create_scene(story.id, SceneCreate(title='Зорі над парком', beats='Сцена 1: Зорі над парком\nДії: Лєра дивиться на зорі.'))
            draft = repo.save_version(story.id, scene.id, 'draft', 'Лєра побачила **зорі**.\n\nВечір був _тихим_.', [], content_format='markdown')
            scene = repo.set_head(scene.id, 'draft', draft.id, scene.revision)
            prose = repo.save_version(story.id, scene.id, 'manual', 'Літеральні *зірочки* та &amp;.', [])
            repo.set_head(scene.id, 'prose', prose.id, scene.revision)
            from storygen.authoring.blueprints import save_role_settings
            from storygen.providers.models import RoleSettings,ProviderSettings
            save_role_settings(repo,story.id,'writer',RoleSettings(provider=ProviderSettings(model='synthetic-rewrite')),repo.get_story(story.id).revision)
            return {'story_id': story.id, 'scene_id': scene.id}

        initial = make_fixture()

        @app.get('/test-fixture')
        def fixture():
            return initial

        @app.post('/test-fixture')
        def new_fixture():
            return make_fixture()

        @app.post('/test-series-prequel')
        def series_prequel_fixture():
            # SERIES-S11: a series with a finished book 1 and a fresh prequel 2 (every record future); a second series with
            # book 1, a finished prequel 2 (records past, Anna's clothing changed) and book 3 after it (neutral text).
            import uuid
            from storygen.storage import series as store
            from tests.series.helpers import book, finished_book, into_series
            from tests.series.test_series_prequel_merge import enter, write_prequel
            tag = uuid.uuid4().hex[:6]
            item = store.create_series(repo, f'Сага приквела {tag}')
            first, _, cloth = finished_book(repo)
            into_series(repo, first, item.id, 1)
            prequel, _ = book(repo, 'Приквел', cast=['A'])
            prequel = enter(repo, prequel, item, 2, ('Рік -10', 1))
            other = store.create_series(repo, f'Сага джерел {tag}')
            book1, _, cloth = finished_book(repo, 'Перша книга')
            into_series(repo, book1, other.id, 1)
            write_prequel(repo, other, 2, ('Рік -10', 1), cloth)
            third, _ = book(repo, 'Третя книга', cast=['A'])
            enter(repo, third, other, 3, ('Рік 2', 1))
            return {'series_id': item.id, 'prequel_id': prequel.id, 'sources_series_id': other.id, 'third_id': third.id}

        @app.post('/test-series-bible-prequel')
        def series_bible_prequel_fixture():
            # SERIES-BIBLE: a series with a finished world bible, a finished book 1 and a prequel 2 (neutral texts).
            import uuid
            from storygen.series_models import SeriesStart
            from storygen.storage import series as store
            from tests.series.helpers import book
            from tests.series.test_series_bible_snapshot import write_bible, write_book_one
            item = store.create_series(repo, f'Сага біблії {uuid.uuid4().hex[:6]}')
            write_bible(repo, item)
            write_book_one(repo, item)
            prequel, _ = book(repo, 'Приквел', written=False, cast=['A'])
            prequel = store.set_story_series(repo, prequel.id, item.id, 2, SeriesStart(offset='Рік -10', anchor=1),
                                             prequel.revision)
            return {'series_id': item.id, 'prequel_id': prequel.id}

        @app.post('/test-brief-proposal')
        def brief_proposal():
            import json,threading
            from storygen.generation.context import build_context
            from storygen.generation.stages import execute_stage
            from storygen.providers.models import RoleSettings,ProviderSettings
            from storygen.providers.streaming import GenerationEvent
            fixture=make_fixture();scene=repo.get_scene(fixture['scene_id'])
            plan=repo.save_version(scene.story_id,scene.id,'scene_plan','Прогулянка парком.',[])
            scene=repo.set_head(scene.id,'plan',plan.id,scene.revision)
            old=repo.save_version(scene.story_id,scene.id,'brief',json.dumps(dict(objective='Старе завдання',beats=['Парк'],constraints=[],proposed_changes=[])),[plan.id])
            repo.set_head(scene.id,'brief',old.id,scene.revision);repo.invalidate_dependents([plan.id])
            class Proposal:
                def stream(self,*_):
                    yield GenerationEvent(type='delta',text=json.dumps(dict(objective='Нове завдання для перегляду',beats=['Парк'],constraints=[],proposed_changes=['Уточнити емоційний акцент.'])))
                    yield GenerationEvent(type='terminal',finish_reason='stop')
            role=RoleSettings(provider=ProviderSettings(model='synthetic'))
            attempt=execute_stage(repo,scene.id,'brief',build_context(repo,scene.id,'brief',role),Proposal(),threading.Event(),lambda _:None)
            return dict(**fixture,proposal_id=attempt.result_version_id,old_brief_id=old.id)

        @app.post('/test-edit-split')
        def edit_split_fixture():
            """EDIT-SENTENCE-GROUPS-S04: an editor proposal with two separate edits in one sentence (name + wording)."""
            import threading
            from storygen.authoring.blueprints import save_role_settings
            from storygen.generation.context import build_context
            from storygen.generation.stages import execute_stage
            from storygen.providers.models import RoleSettings,ProviderSettings
            from storygen.providers.streaming import GenerationEvent
            story=rated_story('Станція')
            scene=repo.create_scene(story.id,SceneCreate(title='Жилет',beats='Борис знімає жилет.'))
            draft=repo.save_version(story.id,scene.id,'draft','Boris скинув важкий робочий жилет на стілець та розстібнув комір комбінезона, що з тихим шелестом відійшов від шкіри.',[],content_format='markdown')
            repo.set_head(scene.id,'draft',draft.id,scene.revision)
            role=RoleSettings(provider=ProviderSettings(model='synthetic-editor'),edit_mode='diff')
            save_role_settings(repo,story.id,'editor',role,repo.get_story(story.id).revision)
            class Editor:
                def stream(self,*_):
                    yield GenerationEvent(type='delta',text='Борис скинув важкий робочий жилет на стілець і розстебнув комір комбінезона; тканина з тихим шелестом відійшла від шкіри.')
                    yield GenerationEvent(type='terminal',finish_reason='stop')
            execute_stage(repo,scene.id,'edit',build_context(repo,scene.id,'edit',role),Editor(),threading.Event(),lambda _:None)
            return {'story_id':story.id,'scene_id':scene.id}

        @app.post('/test-brief-link')
        def brief_link_fixture():
            import json
            story=rated_story('Знайомства в парку')
            cards=[dict(schema_version=2,id=cid,name=name,entries=[dict(id='e'+cid,text=text,availability='timeless',origin='author')])
                for cid,name,text in [('lera','Лєра','Протагоністка'),('marko','Марко','Сусід'),('nina','Ніна','Бариста')]]
            ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
            repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
            ids=[]
            for title,cast in [('Ранок у парку',['lera','marko','nina']),('Кав’ярня',['lera','nina'])]:
                scene=repo.create_scene(story.id,SceneCreate(title=title,character_ids=cast))
                brief=repo.save_version(story.id,scene.id,'brief',json.dumps(dict(objective=f'{title}: нейтральне завдання',beats=['Прогулянка'],constraints=[],proposed_changes=[]),ensure_ascii=False),[])
                scene=repo.set_head(scene.id,'brief',brief.id,scene.revision)
                prose=repo.save_version(story.id,scene.id,'manual','Тиха сцена.',[])
                repo.set_head(scene.id,'prose',prose.id,scene.revision);ids.append(scene.id)
            return {'story_id':story.id,'scene_ids':ids}

        @app.post('/test-ghost-mode')
        def ghost_mode_fixture(format: str = 'markdown'):
            import json
            story=rated_story('Маяк на березі')
            scene=repo.create_scene(story.id,SceneCreate(title='Вечір біля маяка'))
            brief=repo.save_version(story.id,scene.id,'brief',json.dumps(dict(objective='Нейтральне завдання',beats=['Вечір'],constraints=[],proposed_changes=[]),ensure_ascii=False),[])
            scene=repo.set_head(scene.id,'brief',brief.id,scene.revision)
            text=('Над морем повільно сідало сонце, і **маяк** уже світив першим променем, хоча небо ще було світле. '
                  'Хвилі билися об каміння, а вітер приносив запах солі й водоростей.\n\n'
                  '— Ще рано, — сказала доглядачка.\n\n— Ні, саме час.\n\n***\n\n'
                  'Вона піднялася сходами нагору, рахуючи сходинки, як робила щовечора, і зупинилася біля вікна, '
                  'звідки було видно всю затоку й далекі вогні рибальського селища.')
            if format=='plain':text=text.replace('**маяк**','маяк')
            draft=repo.save_version(story.id,scene.id,'draft',text,[brief.id],source_run_id='synthetic',content_format=format)
            repo.set_head(scene.id,'draft',draft.id,scene.revision)
            return {'story_id':story.id,'scene_id':scene.id,'draft_id':draft.id}

        @app.post('/test-draft-writer')
        def draft_writer_fixture():
            import json
            from storygen.authoring.blueprints import save_role_settings
            from storygen.providers.models import RoleSettings,ProviderSettings
            story=rated_story('Вечірній парк')
            scene=repo.create_scene(story.id,SceneCreate(title='Ліхтарі',beats='Лєра йде парком.'))
            brief=repo.save_version(story.id,scene.id,'brief',json.dumps(dict(objective='Прогулянка',beats=[f'Крок {n}: Лєра проходить ще одну алею парку й зупиняється біля ліхтаря.' for n in range(1,26)],constraints=[],proposed_changes=[]),ensure_ascii=False),[])
            repo.set_head(scene.id,'brief',brief.id,scene.revision)
            save_role_settings(repo,story.id,'writer',RoleSettings(provider=ProviderSettings(model='synthetic-writer'),context_tokens=32768),repo.get_story(story.id).revision)
            return {'story_id':story.id,'scene_id':scene.id}

        @app.post('/test-editor-no-changes')
        def editor_no_changes():
            from storygen.authoring.blueprints import save_role_settings
            from storygen.providers.models import RoleSettings,ProviderSettings
            fixture=make_fixture()
            save_role_settings(repo,fixture['story_id'],'editor',RoleSettings(provider=ProviderSettings(model='synthetic-no-changes'),edit_mode='patches'),repo.get_story(fixture['story_id']).revision)
            return fixture

        @app.post('/test-timeline-summaries')
        def timeline_summaries_fixture():
            # MEMORY-SUMMARY-S07: 22 scenes, memory up to scene 21, a published summary of scenes 1-10.
            from tests.memory.summary_helpers import seed_long_story
            from storygen.memory.summary_blocks import summary_blocks
            from storygen.storage.timeline_summaries import publish_summary, save_summary_version
            story = seed_long_story(repo, 22, 21, title='Довга дорога')
            from tests.link_helpers import approve_links
            approve_links(repo, story.id)  # VALID-LINKS: hand-made memory stands for confirmed
            scenes = repo.list_scenes(story.id)
            block = summary_blocks(story, scenes)[0]
            ref = save_summary_version(repo, story.id, block, [s.heads['memory'] for s in scenes[:10]], 'Анна приїхала до міста.', 'model', 'uk')
            publish_summary(repo, story.id, block.key, ref.id, story.revision)
            return {'story_id': story.id, 'scene_id': scenes[21].id}

        @app.post('/test-locations')
        def locations_fixture(model: bool = False):
            # MEMORY-LOCATIONS-S07: two scenes with a typo look-alike («Квартира Джорджа» / «Квартира Джоржа») and a nested
            # room; scene 1 has prose and a memory fact, so the memory table can change an entry type (neutral text).
            # `model` (MEMORY-LOCATIONS-S08): a third scene «Ніч» without a plan place holds «двір», a place a prose
            # search gave it (`location_source='model'`).
            from storygen.domain import SceneCreate, StoryCreate
            from storygen.memory.journal import MemoryJournal, _add_event
            story = repo.create_story(StoryCreate(title='Пристань'))
            first = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Локація: Квартира Джорджа / вітальня', character_ids=[]))
            repo.create_scene(story.id, SceneCreate(title='Вечір', beats='Локація: Квартира Джоржа, двір', character_ids=[]))
            prose = repo.save_version(story.id, first.id, 'manual', 'Чайник закипів на плиті.', [])
            repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
            journal = MemoryJournal(schema_version=3, source_prose_ids=[prose.id],
                                    events=[_add_event('facts', 'Чайник закипів', prose.id, 'Чайник закипів на плиті.', 0,
                                                       location_ids=repo.get_scene(first.id).location_ids)])
            memory = repo.save_version(story.id, first.id, 'memory', journal.model_dump_json(), [prose.id])
            repo.set_head(first.id, 'memory', memory.id, repo.get_scene(first.id).revision)
            if model:
                import json as _json
                from storygen.locations import location_id, normalize
                night = repo.create_scene(story.id, SceneCreate(title='Ніч', beats='Дії: тиша.', character_ids=[]))
                with repo.db.connection() as db:
                    row = _json.loads(db.execute('SELECT payload FROM scenes WHERE id=?', (night.id,)).fetchone()[0])
                    row.update(location_ids=[location_id(story.id, normalize(('двір',)))], location_source='model')
                    db.execute('UPDATE scenes SET payload=? WHERE id=?', (_json.dumps(row, ensure_ascii=False), night.id))
                repo.db.bump_generation()
            return {'story_id': story.id, 'scene_id': first.id}

        @app.post('/test-memory-merge')
        def memory_merge_fixture():
            # MEMORY-MERGE-S04: part 1 — arc Z; part 2 — arcs A and B interleave, scene 4 is their meeting. Scenes 2 and 3
            # dress Anna differently, so the merge has one conflict (neutral text).
            from storygen.authoring.blueprints import save_role_settings
            from storygen.domain import ContentRating
            from storygen.providers.models import ProviderSettings, RoleSettings
            from tests.memory.merge_helpers import arc_book
            from tests.storage.test_memory_merges import coat_events
            _, story, scenes = arc_book(None, 'Z A B A+B', [['Z'], ['A', 'B']], coat_events, repo=repo)
            story = repo.update_story_rating(story.id, ContentRating(sexual=0, violence=0, themes=0), story.revision)
            save_role_settings(repo, story.id, 'planner', RoleSettings(provider=ProviderSettings(model='planner')), story.revision)
            return {'story_id': story.id, 'scene_ids': [s.id for s in scenes]}

        @app.post('/test-core-review')
        def core_review_scene():
            return core_review_fixture(repo,rated_story('Ключ і пальто'))

        @app.post('/test-language-lock/{story_id}')
        def language_lock(story_id: str):
            # STORY-LANGUAGE: a version with source_run_id stands for model material and locks the story language.
            scene = repo.list_scenes(story_id)[0]
            repo.save_version(story_id, scene.id, 'brief', '{}', [], 'browser-run')
            return {'story_id': story_id, 'scene_id': scene.id}

        @app.post('/test-build-edition')
        def switch_build_edition(body: dict):
            # BUILD-EDITION-001: the fixture server runs as the full edition; a spec switches it and must switch back.
            from storygen import build_edition
            original=getattr(build_edition,'_fixture_original',None) or build_edition.current
            build_edition._fixture_original=original
            if body.get('edition')=='store':
                edition=build_edition.BuildEdition(edition='store',report_url='https://example.test/report',support_url='https://example.test/thanks')
                build_edition.current=lambda:edition
            else:
                build_edition.current=original
            return {'edition': build_edition.current().edition}

        @app.post('/test-app-window')
        def switch_app_window(body: dict):
            # DESKTOP-001-S08: the fixture server is not a desktop launch; a spec turns the window on, reads what it was
            # asked to open and turns it off again.
            class Window:
                def __init__(self):
                    self.external=[]

                def open_external(self,url):
                    self.external.append(url)
            if body.get('on') is True:
                app.state.app_window=Window()
            elif body.get('on') is False and hasattr(app.state,'app_window'):
                del app.state.app_window
            window=getattr(app.state,'app_window',None)
            return {'on': window is not None, 'external': window.external if window else []}

        @app.post('/test-force-story-rating/{story_id}')
        def force_story_rating(story_id: str, body: dict):
            # Data rated in the full edition arrives in a store build unchanged; the API cannot create it there.
            import json
            with repo.db.connection() as db:
                raw=json.loads(db.execute('SELECT payload FROM stories WHERE id=?',(story_id,)).fetchone()[0])
                raw['content_rating']=raw['initial_content_rating']=body
                db.execute('UPDATE stories SET payload=? WHERE id=?',(json.dumps(raw),story_id))
            return {'ok': True}

        @app.post('/test-model-refusal')
        def model_refusal(body: dict):
            # MODEL-004: a refusal mark as the gateway records it, for the consent and refusal block spec.
            from storygen.providers.models import ProviderSettings
            from storygen.providers.policy import endpoint
            settings=ProviderSettings(provider=body['provider'],model=body['model'],base_url=body.get('base_url'))
            entry={'rating':body['rating'],'at':'2026-11-12T10:00:00+00:00','story_id':initial['story_id'],'scene_id':initial['scene_id'],'attempt_id':None,'category':'refusal_content'}
            repo.model_policy('add_refusal',entry=entry,role=body['role'],provider=settings.provider,base_url=endpoint(settings),model=settings.model)
            return {'ok': True}

        @app.post('/test-unrated')
        def unrated_story():
            # Unrated like a story created through the application; used by the rating settings spec.
            story = repo.create_story(StoryCreate(title='Без рейтингу'))
            scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='Сцена 1: Сцена\nДії: Лєра дивиться на зорі.'))
            from storygen.authoring.blueprints import save_role_settings
            from storygen.providers.models import RoleSettings,ProviderSettings
            save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic')),repo.get_story(story.id).revision)
            return {'story_id': story.id, 'scene_id': scene.id}

        @app.post('/test-editor-slow')
        def editor_slow():
            from storygen.authoring.blueprints import save_role_settings
            from storygen.providers.models import RoleSettings,ProviderSettings
            fixture=make_fixture()
            save_role_settings(repo,fixture['story_id'],'editor',RoleSettings(provider=ProviderSettings(model='synthetic-slow'),edit_mode='patches'),repo.get_story(fixture['story_id']).revision)
            return fixture

        @app.post('/test-book')
        def book_fixture():
            """Two scenes; the first scene's prose changed after the second was written (neutral text)."""
            from storygen.generation.dependencies import save_manual_prose
            story=rated_story('Лист у бібліотеці')
            first=repo.create_scene(story.id,SceneCreate(title='План'))
            second=repo.create_scene(story.id,SceneCreate(title='Вечір'))
            save_manual_prose(repo,first.id,'Марія знає про лист.',0)
            prose=save_manual_prose(repo,second.id,'Марія згадала лист.',0)
            save_manual_prose(repo,first.id,'Марія не знає про лист.',repo.get_scene(first.id).revision)
            return dict(story_id=story.id,scene_id=second.id,prose_id=prose.id)

        @app.post('/test-card-invalidation')
        def card_invalidation_fixture():
            """A finished scene the author approved (brief, prose, own memory): «Валідна»; Олена is in its cast."""
            import json
            from storygen.characters.service import save_character_material
            from storygen.generation.dependencies import save_manual_prose
            from storygen.memory.journal import MemoryJournal, _add_event
            from storygen.memory.service import save_scene_memory
            from storygen.storage.link_decisions import decide_link
            from storygen.storage.links import scene_links
            story=rated_story('Маяк на пагорбі')
            scene=repo.create_scene(story.id,SceneCreate(title='Ранок',beats='Маяк\nЛокація: Пагорб'))
            entry={'id':None,'text':'Доглядачка маяка.','availability':'timeless','available_from_scene_id':None,'origin':'author','sources':[]}
            cards=save_character_material(repo,story.id,[{'id':None,'schema_version':2,'name':'Олена','entries':[entry]}],repo.get_story(story.id).revision)
            repo.update_scene_metadata(scene.id,{'character_ids':[cards['cards'][0]['id']]},repo.get_scene(scene.id).revision)
            brief=json.dumps({'objective':'Світло на воді','beats':['Маяк'],'constraints':[],'proposed_changes':[]},ensure_ascii=False)
            ref=repo.save_version(story.id,scene.id,'brief',brief,[])
            repo.set_head(scene.id,'brief',ref.id,repo.get_scene(scene.id).revision)
            prose=save_manual_prose(repo,scene.id,'Олена запалила маяк.',repo.get_scene(scene.id).revision)
            journal=MemoryJournal(source_prose_ids=[prose.id],events=[_add_event('facts','Олена запалила маяк',prose.id,'Олена запалила маяк',0)])
            save_scene_memory(repo,scene.id,journal.model_dump_json(),repo.get_scene(scene.id).revision)
            for link in ('brief','prose'):
                decide_link(repo,scene.id,link,'approve',scene_links(repo.context_view(story.id),scene.id)[link].fingerprint)
            return dict(story_id=story.id,scene_id=scene.id)

        @app.post('/test-memory-decision')
        def memory_decision_fixture(previous_memory: bool = True):
            """Two approved scenes with memory; the first scene's prose changed after its memory (Z3 unchecked), so the
            second scene's stages wait for the author. previous_memory=false: the first scene has no memory at all."""
            import json
            from storygen.authoring.blueprints import save_role_settings
            from storygen.generation.dependencies import save_manual_prose
            from storygen.memory.journal import MemoryJournal, _add_event
            from storygen.memory.service import save_scene_memory
            from storygen.providers.models import RoleSettings,ProviderSettings
            from storygen.storage.link_decisions import decide_link
            from storygen.storage.links import scene_links
            story=rated_story('Маяк і човен')
            for role in ('planner','writer','editor','memory'):
                save_role_settings(repo,story.id,role,RoleSettings(provider=ProviderSettings(model='synthetic-'+role)),repo.get_story(story.id).revision)
            def scene_with(title,text,previous,memory=True):
                scene=repo.create_scene(story.id,SceneCreate(title=title,beats=title))
                brief=json.dumps({'objective':title,'beats':[title],'constraints':[],'proposed_changes':[]},ensure_ascii=False)
                ref=repo.save_version(story.id,scene.id,'brief',brief,[])
                repo.set_head(scene.id,'brief',ref.id,repo.get_scene(scene.id).revision)
                prose=save_manual_prose(repo,scene.id,text,repo.get_scene(scene.id).revision)
                journal=None
                if memory:
                    base=previous or MemoryJournal()
                    event=_add_event('facts',text.rstrip('.'),prose.id,text.rstrip('.'),len(base.events))
                    journal=MemoryJournal(source_prose_ids=base.source_prose_ids+[prose.id],events=base.events+[event])
                    save_scene_memory(repo,scene.id,journal.model_dump_json(),repo.get_scene(scene.id).revision)
                for link in ('brief','prose'):
                    state=scene_links(repo.context_view(story.id),scene.id)[link]
                    if state.status=='unchecked':decide_link(repo,scene.id,link,'approve',state.fingerprint)
                return scene,journal
            first,journal=scene_with('Ранок','Олена запалила маяк.',None,previous_memory)
            if not previous_memory:
                second=repo.create_scene(story.id,SceneCreate(title='Вечір',beats='Вечір'))
                brief=json.dumps({'objective':'Вечір','beats':['Вечір'],'constraints':[],'proposed_changes':[]},ensure_ascii=False)
                ref=repo.save_version(story.id,second.id,'brief',brief,[])
                repo.set_head(second.id,'brief',ref.id,repo.get_scene(second.id).revision)
                return dict(story_id=story.id,first_id=first.id,second_id=second.id)
            second,_=scene_with('Вечір','Олена погасила маяк.',journal)
            save_manual_prose(repo,first.id,'Олена запалила старий маяк.',repo.get_scene(first.id).revision)
            return dict(story_id=story.id,first_id=first.id,second_id=second.id)

        @app.post('/test-scene-audit')
        def scene_audit_fixture(memory: bool = False):
            """A scene with an unchecked brief and prose and an auditor of its own (synthetic, local: no budget).
            `memory` adds the scene's memory, so its memory link is valid instead of unavailable."""
            import json
            from storygen.authoring.blueprints import save_role_settings
            from storygen.generation.dependencies import save_manual_prose
            from storygen.providers.models import RoleSettings,ProviderSettings
            story=rated_story('Маяк і човен')
            save_role_settings(repo,story.id,'auditor',RoleSettings(provider=ProviderSettings(model='synthetic-auditor'),temperature=0.2,
                context_tokens=200000,max_input_chars=400000,max_output_tokens=4096),repo.get_story(story.id).revision)
            scene=repo.create_scene(story.id,SceneCreate(title='Ранок',beats='Маяк і човен'))
            brief=json.dumps({'objective':'Світло на воді','beats':['Маяк'],'constraints':[],'proposed_changes':[]},ensure_ascii=False)
            ref=repo.save_version(story.id,scene.id,'brief',brief,[])
            repo.set_head(scene.id,'brief',ref.id,repo.get_scene(scene.id).revision)
            prose=save_manual_prose(repo,scene.id,'Ранок: світло на воді.',repo.get_scene(scene.id).revision)
            if memory:
                from storygen.memory.journal import MemoryJournal, _add_event
                from storygen.memory.service import save_scene_memory
                event=_add_event('facts','Світло на воді',prose.id,'світло на воді',0)
                journal=MemoryJournal(source_prose_ids=[prose.id],events=[event])
                save_scene_memory(repo,scene.id,journal.model_dump_json(),repo.get_scene(scene.id).revision)
            return dict(story_id=story.id,scene_id=scene.id)

        @app.post('/test-book-validation')
        def book_validation_fixture(slow_planner: bool = False, slow_auditor: bool = False):
            """Two scenes with a brief, prose and memory, all links unchecked; the first brief disagrees with the plan.
            The auditor is synthetic and local (no budget). `slow_planner` adds a planner whose brief runs until cancelled; `slow_auditor` makes the auditor hold the run until cancelled."""
            import json
            from storygen.authoring.blueprints import save_role_settings
            from storygen.generation.dependencies import save_manual_prose
            from storygen.memory.journal import MemoryJournal, _add_event
            from storygen.memory.service import save_scene_memory
            from storygen.providers.models import RoleSettings,ProviderSettings
            story=rated_story('Маяк і човен')
            save_role_settings(repo,story.id,'auditor',RoleSettings(provider=ProviderSettings(model='synthetic-book-auditor'),temperature=0.2,
                context_tokens=200000,max_input_chars=400000,max_output_tokens=4096),repo.get_story(story.id).revision)
            journal=MemoryJournal()
            ids=[]
            for title,objective,text in (('Ранок','Світло на воді','Олена запалила маяк.'),('Вечір','Човен біля берега','Олена погасила маяк.')):
                scene=repo.create_scene(story.id,SceneCreate(title=title,beats=title))
                brief=json.dumps({'objective':objective,'beats':[title],'constraints':[],'proposed_changes':[]},ensure_ascii=False)
                ref=repo.save_version(story.id,scene.id,'brief',brief,[])
                repo.set_head(scene.id,'brief',ref.id,repo.get_scene(scene.id).revision)
                prose=save_manual_prose(repo,scene.id,text,repo.get_scene(scene.id).revision)
                event=_add_event('facts',text.rstrip('.'),prose.id,text.rstrip('.'),len(journal.events))
                journal=MemoryJournal(source_prose_ids=journal.source_prose_ids+[prose.id],events=journal.events+[event])
                save_scene_memory(repo,scene.id,journal.model_dump_json(),repo.get_scene(scene.id).revision)
                ids.append(scene.id)
            if slow_auditor:
                save_role_settings(repo,story.id,'auditor',RoleSettings(provider=ProviderSettings(model='synthetic-slow'),temperature=0.2,
                    context_tokens=200000,max_input_chars=400000,max_output_tokens=4096),repo.get_story(story.id).revision)
            if slow_planner:
                save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic-slow')),repo.get_story(story.id).revision)
            return dict(story_id=story.id,first_id=ids[0],second_id=ids[1])

        @app.post('/test-long-book')
        def long_book_fixture():
            """R16-SUGGEST-S07: a plan with an idea and three scenes; the writer's character limit fits the first two."""
            import json
            from storygen.authoring.blueprints import save_role_settings
            from storygen.authoring.imports import SourceFile, import_sources
            from storygen.generation.dependencies import save_manual_prose
            from storygen.generation.publication_metadata import build_publication_context
            from storygen.providers.models import RoleSettings,ProviderSettings
            story=rated_story('Маяк над затокою')
            plan='Задум: доглядачка маяка шукає зниклого брата.\n\n'+''.join(f'## Сцена {n}: {title}\nОпис\n' for n,title in enumerate(('Ранок','Шторм','Човен'),1))
            import_sources(repo,story.id,[SourceFile(name='plan.md',raw=plan.encode())])
            for scene in repo.list_scenes(story.id):
                save_manual_prose(repo,scene.id,f'{scene.title}. '+'Хвилі билися об каміння, і ліхтар світив крізь туман. '*30,repo.get_scene(scene.id).revision)
            def writer(limit):
                save_role_settings(repo,story.id,'writer',RoleSettings(provider=ProviderSettings(model='synthetic-card-writer'),
                    context_tokens=400000,max_input_chars=limit,max_output_tokens=4096),repo.get_story(story.id).revision)
            writer(4000000)
            full=build_publication_context(repo,story.id)
            whole=len(json.dumps(full.api_request,ensure_ascii=False,separators=(',',':')))
            writer(whole-1200)  # one scene (~1.7k characters) short of the whole book
            return dict(story_id=story.id)

        @app.post('/test-editor-import')
        def editor_import_fixture():
            """EDITOR-IMPORT UI: three scenes exported to DOCX; the editor changed scene 1 (tracked), left a comment on
            scene 2, and scene 3's prose changed after the export, so the summary needs the author's choice."""
            import base64
            from storygen.application.exports import export_story
            from storygen.generation.dependencies import save_manual_prose
            from tests.publication.editor_import_helpers import edit, ranged, run, split, tracked
            story=rated_story('Маяк на пірсі')
            ids=[]
            for title,text in (('Ранок','Ранок на пірсі був тихий.'),('Хвилі','Хвилі билися об старі палі.'),('Вечір','Увечері маяк засвітився.')):
                scene=repo.create_scene(story.id,SceneCreate(title=title,beats=title))
                save_manual_prose(repo,scene.id,text,repo.get_scene(scene.id).revision,content_format='markdown')
                ids.append(scene.id)
            content=export_story(repo,story.id,'docx').read_bytes()
            def change(xml):
                xml=split(xml,'тихий',tracked('тихий','ясний'))
                return split(xml,'старі палі',ranged(7,run('старі палі')))
            docx=edit(content,change,[(7,'Редакторка','Які саме палі?')])
            save_manual_prose(repo,ids[2],'Увечері маяк спалахнув.',repo.get_scene(ids[2]).revision,content_format='markdown')
            return {'story_id':story.id,'docx_base64':base64.b64encode(docx).decode('ascii'),'scene_ids':ids}

        @app.post('/test-manuscript-import')
        def manuscript_import_fixture():
            """MANUSCRIPT-IMPORT UI: the same small manuscript as DOCX and Markdown (neutral text about a pier lighthouse):
            a book title, a short dedication (front matter), chapter 1 split by a separator, and a long chapter 2 with one
            proposed boundary — four scenes: «Пірс (1)», «Пірс (2)», «Шторм (1)», «Шторм (2)» (proposed)."""
            import base64
            from tests.publication.manuscript_fixtures import docx, para, style
            prose=lambda n,seed:' '.join(f'Хвиля {seed}{i} била об старий пірс' for i in range(n//6))+'.'
            chapter1=[prose(60,'а'),prose(60,'б'),'* * *',prose(60,'в')]
            chapter2=[prose(120,f'г{k}-') for k in range(26)]
            body=para('Маяк на пірсі','Title')+para('Присвячую доглядачам маяків.')+para('Глава 1. Пірс')
            body+=''.join(para(text) for text in chapter1)+para('Глава 2. Шторм')+''.join(para(text) for text in chapter2)
            md='# Маяк на пірсі\n\nПрисвячую доглядачам маяків.\n\nГлава 1. Пірс\n\n'+'\n\n'.join(chapter1)
            md+='\n\nГлава 2. Шторм\n\n'+'\n\n'.join(chapter2)+'\n'
            return {'docx_base64':base64.b64encode(docx(body,[style('Title','title')])).decode('ascii'),
                    'md_base64':base64.b64encode(md.encode('utf-8')).decode('ascii')}

        @app.post('/test-character-extract')
        def character_extract_fixture(proposal: bool = False):
            """R-51 «Знайти персонажів і місця у прозі» (spec §6): a book imported from a manuscript (two scenes of prose, no
            memory) with card «Олена»; the memory role is local (the cost is unknown) and slow, so a started search waits
            until it is cancelled. `proposal`: a finished search left a proposal — new card «Марко» (other names «Марк»,
            suggested, and «сторож», not suggested), the name «Оленка» for «Олена», «Олена» as the main character and
            both scene casts; places (spec 2 §5): «Пірс» (new) and «Маяк / ліхтарна» (new, not named in the prose, not
            suggested) for scene 1, «Маяк» (new) for scene 2. Neutral text about a pier lighthouse."""
            from datetime import datetime, timezone
            from storygen.authoring.blueprints import save_role_settings
            from storygen.domain import ContentRating, ManuscriptImportOrigin, new_id
            from storygen.generation.extract_run import proposal_fingerprint
            from storygen.providers.models import RoleSettings, ProviderSettings
            from storygen.run_models import Run, RunRequest
            from storygen.storage.manuscript_store import publish_manuscript
            from tests.series.helpers import card, publish_cards
            origin = ManuscriptImportOrigin(file_name='mayak.docx', file_sha256='b'*64, imported_at=datetime.now(timezone.utc))
            story, scenes = publish_manuscript(repo, StoryCreate(title='Маяк і човен', content_rating=ContentRating(sexual=0, violence=0, themes=0)),
                                               [('Пірс', 'Олена стояла на пірсі. Марко махнув їй з човна.', 'markdown', None, 8),
                                                ('Шторм', 'Уночі Марко запалив маяк, і той світив до ранку.', 'markdown', None, 9)],
                                               origin, False)
            publish_cards(repo, story, [card('A', 'Олена')])
            save_role_settings(repo, story.id, 'memory', RoleSettings(provider=ProviderSettings(model='synthetic-slow'), context_tokens=131072),
                               repo.get_story(story.id).revision)
            scenes = [repo.get_scene(scene.id) for scene in scenes]
            if proposal:
                quote = lambda scene, text: {'version_id': scene.heads['prose'], 'scene_id': scene.id, 'quote': text}
                body = {'cards': [{'key': 'n1', 'name': 'Марко', 'other_names': [{'name': 'Марк', 'suggested': True}, {'name': 'сторож', 'suggested': False}],
                                   'quotes': [quote(scenes[0], 'Марко махнув їй з човна'), quote(scenes[1], 'Уночі Марко запалив маяк')],
                                   'first_scene_id': scenes[0].id}],
                        'name_updates': [{'card_id': 'A', 'names': [{'name': 'Оленка', 'suggested': True}]}],
                        'protagonist': {'ref': 'A', 'scores': [1.0]},
                        'casts': [{'scene_id': scenes[0].id, 'mode': 'set', 'participants': ['A', 'n1']},
                                  {'scene_id': scenes[1].id, 'mode': 'set', 'participants': ['n1']}],
                        'locations': [{'scene_id': scenes[0].id, 'mode': 'set', 'places': [
                                          {'ref': 'l1', 'path': 'Пірс', 'new': True, 'suggested': True},
                                          {'ref': 'l2', 'path': 'Маяк / ліхтарна', 'new': True, 'suggested': False}]},
                                      {'scene_id': scenes[1].id, 'mode': 'set', 'places': [
                                          {'ref': 'l3', 'path': 'Маяк', 'new': True, 'suggested': True}]}],
                        'skipped_scenes': [], 'calls': 1, 'partial': False, 'cost_usd': None,
                        'source': {'scenes': {s.id: {'version_id': s.heads['prose'], 'sha256': repo.get_version(s.heads['prose']).sha256} for s in scenes},
                                   'start_cards_version_id': repo.get_story(story.id).characters_version_id, 'group_words': 5000}}
                body['fingerprint'] = proposal_fingerprint(body)
                repo.enqueue_run(Run(id=new_id(), story_id=story.id, request_id='extract-'+new_id(), state='completed', tasks=[],
                                     request=RunRequest(story_id=story.id, mode='character_extract', group_words=5000),
                                     checkpoint={'phase': 'done', 'proposal': body}))
            return {'story_id': story.id, 'scene_ids': [scene.id for scene in scenes]}

        @app.post('/test-memory-build')
        def memory_build_fixture(series: bool = False, narrow: bool = False):
            """R-48 «Побудувати пам'ять» (spec §5): a book imported from a manuscript (two scenes of prose, no plan, no
            memory) with card «Олена», named in scene 1. The memory role is local (no tariff: the cost is unknown) and slow,
            so a started run waits until it is cancelled. `narrow`: the default role limits, which neither scene fits.
            `series`: the book is number 2 of a series whose finished book 1 has memory, without a start snapshot and
            without cards of its own. Neutral text about a pier lighthouse."""
            import uuid
            from datetime import datetime, timezone
            from storygen.authoring.blueprints import save_role_settings
            from storygen.domain import ContentRating, ManuscriptImportOrigin
            from storygen.providers.models import RoleSettings, ProviderSettings
            from storygen.storage.manuscript_store import publish_manuscript
            from tests.series.helpers import card, finished_book, into_series, publish_cards
            origin = ManuscriptImportOrigin(file_name='mayak.docx', file_sha256='a'*64, imported_at=datetime.now(timezone.utc))
            slot = None
            if series:
                from storygen.storage import series as store
                item = store.create_series(repo, f'Сага маяка {uuid.uuid4().hex[:6]}')
                first, _, _ = finished_book(repo, 'Перша книга')
                into_series(repo, first, item.id, 1)
                slot = (item.id, 2)
            story, scenes = publish_manuscript(repo, StoryCreate(title='Маяк на пірсі', content_rating=ContentRating(sexual=0, violence=0, themes=0)),
                                               [('Пірс', 'Олена стояла на пірсі й дивилася на воду.', 'markdown', None, 8),
                                                ('Шторм', 'Уночі почався шторм, і маяк світив до ранку.', 'markdown', None, 9)],
                                               origin, False, series=slot)
            if not series:
                publish_cards(repo, story, [card('A', 'Олена')])
            role = RoleSettings(provider=ProviderSettings(model='synthetic-slow')) if narrow else \
                RoleSettings(provider=ProviderSettings(model='synthetic-slow'), context_tokens=131072)
            save_role_settings(repo, story.id, 'memory', role, repo.get_story(story.id).revision)
            return {'story_id': story.id, 'scene_ids': [scene.id for scene in scenes]}

        @app.post('/test-editor-import-touch/{scene_id}')
        def editor_import_touch(scene_id: str):
            # Changes a scene's prose between the summary and the save: the save then answers 409.
            from storygen.generation.dependencies import save_manual_prose
            save_manual_prose(repo,scene_id,'Ранок на пірсі був зовсім інший.',repo.get_scene(scene_id).revision,content_format='markdown')

        uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')


if __name__ == '__main__':
    main()
