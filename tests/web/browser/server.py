"""Synthetic UI fixture. Never opens production data, dotenv or real gateways."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))

import uvicorn

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate, SceneCreate
from storygen.web.app import create_app

_failed_memories=set()

def forbidden_gateway(*args, **kwargs):
    from storygen.providers.streaming import GenerationEvent
    class Fake:
        def stream(self,context,cancel):
            if context.stage=='edit' and context.settings.provider.model=='synthetic-slow':
                cancel.wait(15)
                yield GenerationEvent(type='cancelled')
                return
            if context.stage in {'review_part','memory'} and context.settings.provider.model.startswith('synthetic-impact'):
                import json
                if context.stage=='memory':
                    if context.settings.provider.model.endswith('fail:'+context.scene_id) and context.scene_id not in _failed_memories:
                        _failed_memories.add(context.scene_id)
                        yield GenerationEvent(type='error',message='Memory checkpoint unavailable');return
                    from tests.memory.wire_helpers import core_unchanged, threads_open, v4_response
                    bounds=json.loads(context.fragments['memory_schema_bounds'])
                    raw=json.loads(v4_response(core_unchanged(*bounds['tracked']),threads_open(*bounds['threads'])))
                else:
                    data=json.loads(context.user_text)
                    raw=dict(complete=True,changes=[],questions=[]) if data['phase']=='delta' else dict(complete=True,concerns=[],carry_refs=[])
                    if data.get('contract_version')==4:
                        raw=dict(analysis_status='done',reason=None,candidates=[])
                        if data['phase']=='delta':raw['changes']=[]
                        if data['phase']=='premise_check':
                            sources=[k for k,v in data['evidence'].items() if v['kind']=='source' and 'Марія знає про лист.' in v['text'] and 'Марія не знає про лист.' in v['text']]
                            if sources:
                                ref=sources[0]
                                def ep(quote):
                                    start=data['evidence'][ref]['text'].index(quote)
                                    return dict(ref=ref,start=start,end=start+len(quote),quote=quote)
                                raw['candidates']=[dict(type='contradiction',left=ep('Марія знає про лист.'),right=ep('Марія не знає про лист.'),explanation='Дві передумови потребують авторського вибору.')]
                    elif context.settings.provider.model.endswith('-changes') and data['phase']=='check':
                        target=next(k for k,v in data['evidence'].items() if v['kind']=='target')
                        source=next(k for k,v in data['evidence'].items() if v['kind']=='source' and 'Марія' in v['text'])
                        raw['concerns']=[dict(kind='issue',message='Уточніть знання Марії відповідно до нових подій.',change_refs=[data['evidence'][source]['change']],target_refs=[target],source_refs=[source])]
                yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
                yield GenerationEvent(type='terminal',finish_reason='stop',usage={'prompt_tokens':100,'completion_tokens':50})
                return
            if context.stage=='impact_part' and context.settings.provider.model.startswith('synthetic-impact'):
                import json
                data=json.loads(context.user_text)
                raw=dict(covered_ids=data['required_coverage'],summary='Передумови перевірено, суперечностей немає.',verdict='no_impact',findings=[],evidence=[],uncertainty=None)
                yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
                yield GenerationEvent(type='terminal',finish_reason='stop',usage={'prompt_tokens':100,'completion_tokens':50})
                return
            if context.stage in {'impact_delta','impact_check'} and context.settings.provider.model.startswith('synthetic-impact'):
                import json
                target=json.loads(context.fragments['impact_target']);ids=[c['id'] for c in target['changes'] if c['changed']]
                if context.stage=='impact_delta':raw=dict(covered_change_ids=ids,items=[],uncertainty=None)
                else:
                    change=next(c for c in target['changes'] if c['changed'])
                    findings=[dict(target_quote=target['text'],change_ids=[change['id']],explanation='Уточніть знання Марії відповідно до нових подій.',evidence=[dict(source_id=change['id']+':new',quote=change['new_text'])])] if context.settings.provider.model.endswith('-changes') else []
                    raw=dict(materials=[dict(version_id=target['version_id'],verdict='changes_required' if findings else 'no_impact',covered_change_ids=ids,explanation='Перевірено зв’язок подій.',findings=findings)],memory_semantic_impact='unchecked',memory_explanation='Пам’ять потребує окремого оновлення.')
                yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
                yield GenerationEvent(type='terminal',finish_reason='stop')
                return
            if context.stage=='edit' and context.settings.provider.model=='synthetic-no-changes':
                yield GenerationEvent(type='delta',text='{"edits":[]}')
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
    with TemporaryDirectory(prefix='obscura-browser-') as directory:
        root = Path(directory)
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

        @app.post('/test-editor-no-changes')
        def editor_no_changes():
            from storygen.authoring.blueprints import save_role_settings
            from storygen.providers.models import RoleSettings,ProviderSettings
            fixture=make_fixture()
            save_role_settings(repo,fixture['story_id'],'editor',RoleSettings(provider=ProviderSettings(model='synthetic-no-changes'),edit_mode='patches'),repo.get_story(fixture['story_id']).revision)
            return fixture

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

        @app.post('/test-impact')
        def impact_fixture(changes:bool=False,chunked:bool=False,memory_fail:bool=False,legacy:bool=False,evidence:bool=False):
            from storygen.generation.dependencies import save_manual_prose
            from storygen.authoring.blueprints import save_role_settings
            from storygen.providers.models import RoleSettings,ProviderSettings
            story=rated_story('Лист у бібліотеці')
            first=repo.create_scene(story.id,SceneCreate(title='План'))
            second=repo.create_scene(story.id,SceneCreate(title='Вечір'))
            save_manual_prose(repo,first.id,'Марія знає про лист.'*(120 if chunked else 1),0)
            prose=save_manual_prose(repo,second.id,'Марія згадала лист.'*(140 if chunked else 1),0)
            if legacy:
                from storygen.domain import VersionRef
                with repo.db.connection() as db:
                    raw=repo._get(db,'versions',prose.id,VersionRef)
                    raw.dependency_snapshot=None;raw.input_refs=[];raw.stale=True
                    db.execute('UPDATE versions SET payload=? WHERE id=?',(raw.model_dump_json(),prose.id))
                    db.execute('DELETE FROM dependency_edges WHERE target_id=?',(prose.id,))
            text='Марія знає про лист. Марія не знає про лист.' if evidence else 'Марія не знає про лист.' if changes else 'Марія знає про лист. Вечір настав.'*(120 if chunked else 1)
            save_manual_prose(repo,first.id,text,repo.get_scene(first.id).revision)
            save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic-impact'+('-changes' if changes else '')),context_tokens=24000 if chunked else 32768,max_output_tokens=2048 if chunked else 8192,max_input_chars=14000 if chunked else 80000),repo.get_story(story.id).revision)
            save_role_settings(repo,story.id,'memory',RoleSettings(provider=ProviderSettings(model='synthetic-impact-memory'+('-fail:'+second.id if memory_fail else '')),context_tokens=32768,max_output_tokens=2048),repo.get_story(story.id).revision)
            if evidence:
                from tests.review.counter4 import activate_counter4
                activate_counter4(repo,second.id)
            return dict(story_id=story.id,scene_id=second.id,prose_id=prose.id)

        uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')


if __name__ == '__main__':
    main()
