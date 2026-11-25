"""Reproducible screenshots for the user-guide site (#29, DOCS-SITE), in both interface languages.

Seeds neutral stories in a fresh work directory (never the author's data), starts a local server
without any provider keys, and captures pages with Playwright (extra `browser`) into
docs/images/site/{uk,en}/. No model calls.

    python scripts/capture_screenshots.py [--work-dir C:/tmp/obscura-shots] [--port 8811]
"""
import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/images/site'

STORIES={
    'uk':{'title':'Маяк на пристані','scenes':['Ранок у селищі','Лист без підпису','Шторм','Повернення'],'hero':'Анна',
          'brief':'{"objective":"Анна знаходить лист і вирішує його прочитати","beats":["Анна відчиняє скриньку на пристані","Усередині лежить конверт без підпису","Вітер з моря ледь не вириває папір"],"constraints":["Без флешбеків"],"proposed_changes":[]}',
          'draft':'Анна відчинила скриньку на пристані й побачила конверт без підпису. Вітер з моря шарпав папір.',
          'characters':'## Анна\nДоглядачка маяка, уважна до дрібниць.\n\n## Петро\nРибалка, давній друг родини.\n',
          'location_label':'Локація','locations':['Маяк / ліхтарна','Пристань','Пристань біля маяка','Маяк'],
          'location_description':('Маяк','Білий маяк на скелі; гвинтові сходи ведуть до ліхтарної.'),
          # VALID-LINKS-S15: the first scene's own brief, the author's prose of both scenes and the Auditor's verdicts.
          'brief1':'{"objective":"Анна оглядає маяк перед світанком","beats":["Анна піднімається до ліхтарної","Петро махає їй з пристані"],"constraints":[],"proposed_changes":[]}',
          'prose1':'Анна піднялася гвинтовими сходами до ліхтарної. Унизу, на пристані, Петро махав їй рукою.',
          'prose2':'Анна відчинила скриньку на пристані й побачила конверт без підпису. Вона сховала його в кишеню й пішла додому, не читаючи.',
          'verdict1':('Завдання може розходитися з планом.','План називає ранок у селищі, а завдання — огляд маяка перед світанком.','перед світанком'),
          'verdict2':('Проза може розходитися із завданням: Анна не читає листа.','Завдання каже, що Анна вирішує прочитати лист, а в прозі вона його не читає.','пішла додому, не читаючи'),
          # EDITOR-IMPORT-S11: the editor's tracked change in the prose of scene 1 and a comment on the prose of scene 2.
          'import_edit':('махав їй рукою','помахав їй рукою'),'import_note':('конверт без підпису','Редакторка','Чий це конверт? Варто натякнути раніше.')},
    'en':{'title':'Lighthouse pier','scenes':['Morning in the village','An unsigned letter','The storm','Coming back'],'hero':'Anna',
          'brief':'{"objective":"Anna finds the letter and decides to read it","beats":["Anna opens the box on the pier","Inside lies an envelope with no signature","The sea wind almost tears the paper away"],"constraints":["No flashbacks"],"proposed_changes":[]}',
          'draft':'Anna opened the box on the pier and found an envelope with no signature. The sea wind tugged at the paper.',
          'characters':'## Anna\nThe lighthouse keeper, attentive to small things.\n\n## Peter\nA fisherman and an old friend of the family.\n',
          'location_label':'Location','locations':['Lighthouse / lamp room','Pier','Pier by the lighthouse','Lighthouse'],
          'location_description':('Lighthouse','A white lighthouse on the rock; a spiral stair leads to the lamp room.'),
          'brief1':'{"objective":"Anna inspects the lighthouse before dawn","beats":["Anna climbs to the lamp room","Peter waves to her from the pier"],"constraints":[],"proposed_changes":[]}',
          'prose1':'Anna climbed the spiral stair to the lamp room. Down on the pier, Peter waved to her.',
          'prose2':'Anna opened the box on the pier and found an envelope with no signature. She put it in her pocket and went home without reading it.',
          'verdict1':('The brief may differ from the plan.','The plan names a morning in the village, but the brief has a lighthouse inspection before dawn.','before dawn'),
          'verdict2':('The prose may differ from the brief: Anna does not read the letter.','The brief says Anna decides to read the letter, but in the prose she does not read it.','went home without reading it'),
          'import_edit':('waved to her','waved up at her'),'import_note':('an envelope with no signature','Editor','Whose envelope is it? Worth a hint earlier.')}
}


def seed(data_dir,languages=('uk','en')):
    """Create one neutral story per language; return {lang: {story_id, scene_id}}. Offline, repository only."""
    from storygen.domain import ContentRating, SceneCreate, StoryCreate
    from storygen.storage.repository import Repository
    repo=Repository(Path(data_dir));result={}
    for lang in languages:
        spec=STORIES[lang]
        story=repo.create_story(StoryCreate(title=spec['title'],language=lang))
        story=repo.update_story_rating(story.id,ContentRating(sexual=0,violence=0,themes=0),story.revision)
        # MEMORY-LOCATIONS: each scene names a place; «Пристань біля маяка» looks like «Пристань», so the panel shows a suggestion.
        scenes=[repo.create_scene(story.id,SceneCreate(title=title,beats=f'{spec["hero"]}: {title.lower()}.\n{spec["location_label"]}: {place}'))
                for title,place in zip(spec['scenes'],spec['locations'])]
        from storygen.locations import location_id,normalize
        from storygen.storage.locations import change_locations,set_description
        path,text=spec['location_description'];card=location_id(story.id,normalize((path,)))
        change_locations(repo,story.id,repo.get_story(story.id).revision,lambda db:set_description(db,story.id,card,text))
        first,scene=scenes[0],scenes[1]
        first_brief=repo.save_version(story.id,first.id,'brief',spec['brief1'],[])
        repo.set_head(first.id,'brief',first_brief.id,repo.get_scene(first.id).revision)
        brief=repo.save_version(story.id,scene.id,'brief',spec['brief'],[])
        repo.set_head(scene.id,'brief',brief.id,repo.get_scene(scene.id).revision)
        draft=repo.save_version(story.id,scene.id,'draft',spec['draft'],[brief.id])
        repo.set_head(scene.id,'draft',draft.id,repo.get_scene(scene.id).revision)
        result[lang]={'story_id':story.id,'scene_id':scene.id,'first_id':first.id}
        result[lang]['verdict_id']=seed_consistency(repo,story.id,first.id,scene.id,spec)
    return result


def link_states(repo,story_id,scene_id):
    """{link: LinkState} of a scene on a fresh view (the status and the fingerprint a decision or verdict must name)."""
    from storygen.storage.context_view import ContextView
    from storygen.storage.links import link_state
    with repo.db.connection() as db:
        view=ContextView(repo,db,story_id)
        return {link:link_state(view,scene_id,link) for link in ('brief','prose','memory')}


def seed_consistency(repo,story_id,first_id,second_id,spec):
    """VALID-LINKS-S15: the author's prose and memory of the first two scenes, a cloud Auditor with a stored tariff (the scene preview is
    ready without a key and shows a price) and the Auditor's discrepancies on the brief of scene 1 and the prose of
    scene 2, which then shows: brief not checked, prose with a quote, memory consistent, its calls with the price bound.
    Returns the id of the verdict on scene 1 (the stop of the book validation)."""
    from datetime import timedelta
    from storygen.authoring.blueprints import save_role_settings
    from storygen.billing.models import Tariff,utcnow
    from storygen.billing.service import save_tariff,set_limit
    from storygen.generation.dependencies import save_manual_prose
    from storygen.memory.journal import MemoryJournal,_add_event
    from storygen.memory.service import save_scene_memory
    from storygen.providers.models import ProviderSettings,RoleSettings
    from storygen.storage.link_decisions import decide_link,write_auditor_verdict
    # A cloud Auditor with a stored manual tariff: the preview prices from the tariff only, so it shows «N викл., до $X» with no key and no network.
    auditor=ProviderSettings(provider='openrouter',model='neutral/auditor')
    save_role_settings(repo,story_id,'auditor',RoleSettings(provider=auditor,temperature=0.2,context_tokens=32768,max_input_chars=60000,max_output_tokens=2048),
        repo.get_story(story_id).revision)
    save_tariff(repo,Tariff(provider='openrouter',model='neutral/auditor',base_url=auditor.base_url,input_per_million='1',output_per_million='2',
        source='neutral screenshot tariff',kind='manual',expires_at=(utcnow()+timedelta(days=1)).isoformat()))
    set_limit(repo,'story:'+story_id,'10',0)  # a cloud run needs an explicit budget limit before its preview is ready
    # The editor role is set too, so the run row offers no «Налаштувати редактора».
    save_role_settings(repo,story_id,'editor',RoleSettings(provider=ProviderSettings(provider='local',base_url='http://127.0.0.1:11434/v1',model='neutral-editor'),
        temperature=0.2,context_tokens=32768,max_input_chars=60000,max_output_tokens=2048),repo.get_story(story_id).revision)
    journal=MemoryJournal()
    for scene_id,text in ((first_id,spec['prose1']),(second_id,spec['prose2'])):
        prose=save_manual_prose(repo,scene_id,text,repo.get_scene(scene_id).revision)
        fact=text.split('.')[0]
        event=_add_event('facts',fact,prose.id,fact,len(journal.events))
        journal=MemoryJournal(source_prose_ids=journal.source_prose_ids+[prose.id],events=journal.events+[event])
        save_scene_memory(repo,scene_id,journal.model_dump_json(),repo.get_scene(scene_id).revision)
    for scene_id in (first_id,second_id):
        memory=link_states(repo,story_id,scene_id)['memory']
        if memory.status!='valid':decide_link(repo,scene_id,'memory','approve',memory.fingerprint)
    verdicts=[]
    for scene_id,link,confidence,(summary,text,quote) in ((first_id,'brief',64,spec['verdict1']),(second_id,'prose',72,spec['verdict2'])):
        state=link_states(repo,story_id,scene_id)[link]
        status,verdict_id=write_auditor_verdict(repo,story_id,scene_id,link,fingerprint=state.fingerprint,marker=None,outcome='discrepancy',
                                                confidence=confidence,discrepancies=[{'text':text,'quote':quote}],reason=summary)
        if status!='written':raise RuntimeError(f'висновок Ревізора не записано: {scene_id} {link} {status}')
        verdicts.append(verdict_id)
    states={link:value.status for link,value in link_states(repo,story_id,second_id).items()}
    if states!={'brief':'unchecked','prose':'discrepancy','memory':'valid'}:raise RuntimeError(f'сцена 2 не в очікуваному стані: {states}')
    return verdicts[0]


def seed_stopped_validation(data_dir,ids):
    """VALID-UI-S06: a book validation stopped for the author on the brief of scene 1 (needs_review). Written while the
    server runs, after the general shots, so the story menu there still reads «Валідація книги (N)», as workspace.md says."""
    from storygen.domain import new_id
    from storygen.run_models import Run,RunRequest
    from storygen.storage import run_store
    from storygen.storage.repository import Repository
    repo=Repository(Path(data_dir));story_id,first_id,verdict_id=ids['story_id'],ids['first_id'],ids['verdict_id']
    run=Run(id=new_id(),story_id=story_id,request_id='shots-'+new_id(),
            request=RunRequest(story_id=story_id,scene_id=None,mode='audit',audit_scope='story',audit_plan_fingerprint='0'*64),  # a stand-in plan: the shot never resumes it
            state='needs_review',tasks=[],
            planned_telemetry={'roles':{'auditor':{'provider':'openrouter','model':'neutral/auditor'}},'calls':4,'cost_bound_usd':'0.0210','scenes':2},
            checkpoint={'scene_id':first_id,'link':'brief','outcome':'discrepancy','verdict_id':verdict_id,'reason':None,'phase':'awaiting_author'})
    # Inserted already stopped, so the server's worker never takes it as a queued run.
    run_store.enqueue_run(repo,run)
    for kind,data in (('stage_started',{'stage':'audit_brief','scene_id':first_id,'link':'brief','model':'neutral/auditor','provider':'openrouter'}),
                      ('stage_finished',{'attempt_id':'shot-1','state':'completed','usage':{'cost':{'usd':0.0052}}}),
                      ('audit_step',{'scene_id':first_id,'link':'brief','outcome':'discrepancy','verdict_id':verdict_id,'attempt_id':'shot-1'})):
        run_store.append_run_event(repo,run.id,kind,data)


def editor_import_docx(repo,story_id,lang):
    """EDITOR-IMPORT-S11: the DOCX an editor returns — the story's own manuscript export with a tracked change in scene 1
    and a comment in scene 2. The export is recorded in the data folder, so it is made after the other shots."""
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))  # run as `python scripts/capture_screenshots.py`
    from storygen.application.exports import export_story
    from tests.publication.editor_import_helpers import edit,ranged,run,split,tracked
    spec=STORIES[lang];(old,new),(phrase,author,note)=spec['import_edit'],spec['import_note']
    content=export_story(repo,story_id,'docx',allow_incomplete=True).read_bytes()
    return edit(content,lambda xml:split(split(xml,old,tracked(old,new)),phrase,ranged(7,run(phrase))),[(7,author,note)])


# MANUSCRIPT-IMPORT-S11: a neutral manuscript in the same lighthouse world; the long second chapter (over 2 500 words)
# gets a proposed boundary, a separator splits the first one and the epilogue is a chapter without a number.
MANUSCRIPTS={
    'uk':{'name':'lysty-z-maiaka.md','title':'Листи з маяка','chapter':'Глава','chapters':['Ранок на пристані','Шторм'],'epilogue':'Епілог',
          'paragraphs':['Анна піднялася гвинтовими сходами до ліхтарної й протерла скло. Над морем ще висів туман, а внизу на пристані Петро перевіряв сіті.',
                        'Вітер змінився ближче до полудня. Хвилі почали бити в каміння біля маяка, і чайки сховалися за дахом старого складу.',
                        'Петро прив’язав човен подвійним вузлом і гукнув, що ввечері прийде допомогти з ліхтарем. Анна махнула йому рукою з галереї.',
                        'У скриньці на пристані лежав конверт без підпису. Анна поклала його в кишеню й вирішила прочитати пізніше, коли стихне вітер.',
                        'До вечора небо потемніло. Анна запалила ліхтар, записала в журнал час і силу вітру й довго дивилася на темну воду.'],
          'epilogue_text':'Уранці море стихло. Анна відчинила вікно ліхтарної й нарешті розгорнула лист.'},
    'en':{'name':'lighthouse-letters.md','title':'Letters from the lighthouse','chapter':'Chapter','chapters':['Morning on the pier','The storm'],'epilogue':'Epilogue',
          'paragraphs':['Anna climbed the spiral stair to the lamp room and wiped the glass. Fog still hung over the sea, and down on the pier Peter was checking his nets.',
                        'The wind changed closer to noon. Waves began to beat against the rocks by the lighthouse, and the gulls hid behind the roof of the old shed.',
                        'Peter tied the boat with a double knot and called up that he would come in the evening to help with the lamp. Anna waved to him from the gallery.',
                        'In the box on the pier lay an envelope with no signature. Anna put it in her pocket and decided to read it later, when the wind dropped.',
                        'By evening the sky had darkened. Anna lit the lamp, wrote the time and the strength of the wind in the log and watched the dark water for a long time.'],
          'epilogue_text':'In the morning the sea was calm. Anna opened the window of the lamp room and at last unfolded the letter.'},
}


def manuscript_sample(lang):
    """(file name, Markdown bytes) of the neutral manuscript for the import dialog shot; no author material."""
    spec=MANUSCRIPTS[lang];text=spec['paragraphs']
    first,second=spec['chapters']
    lines=[f'# {spec["title"]}',f'## {spec["chapter"]} 1. {first}',text[0],text[1],'***',text[2],text[3],
           f'## {spec["chapter"]} 2. {second}',*[text[i%len(text)] for i in range(140)],f'## {spec["epilogue"]}',spec['epilogue_text']]
    return spec['name'],'\n\n'.join(lines).encode('utf-8')


def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def ensure_port_free(port):
    """Refuse a busy port: otherwise the author's own running server could answer and be photographed."""
    with socket.socket() as sock:
        try:sock.bind(('127.0.0.1',port))
        except OSError:raise SystemExit(f'порт {port} зайнятий: зупиніть інший сервер або вкажіть інший --port')


def server_env():
    """Environment for the seed server: our sources first, no provider keys."""
    env={k:v for k,v in os.environ.items() if not k.upper().endswith('_API_KEY')}
    env['PYTHONPATH']=str(ROOT/'src');return env


def server_command(data,port,env_file):
    """Seed server command: an explicit empty env file, so the repository `.env` keys are never loaded."""
    return [sys.executable,'-m','storygen.server','--data-dir',str(data),'--port',str(port),'--env-file',str(env_file)]


def resolve_work_dir(value):
    """Absolute work directory: the server runs with cwd=ROOT, so a relative path would point elsewhere."""
    return Path(value).resolve()


def wait_for(url,server,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if server.poll() is not None:raise RuntimeError(f'сервер знімків завершився з кодом {server.poll()}')
        try:
            with urllib.request.urlopen(url,timeout=2):
                if server.poll() is not None:raise RuntimeError(f'сервер знімків завершився з кодом {server.poll()}')
                return
        except OSError:time.sleep(0.3)
    raise TimeoutError(f'сервер не відповів: {url}')


def capture(base,ids,languages):
    from playwright.sync_api import sync_playwright
    shots=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            for lang in languages:
                spec=STORIES[lang]
                story,scene=ids[lang]['story_id'],ids[lang]['scene_id'];folder=OUT/lang;folder.mkdir(parents=True,exist_ok=True)
                for viewport,suffix in [({'width':1280,'height':800},'desktop'),({'width':390,'height':844},'mobile')]:
                    page=browser.new_page(viewport=viewport,locale='uk-UA' if lang=='uk' else 'en-US')
                    page.goto(base+'/');page.locator(f'[data-ui-locale={lang}]').click();page.wait_for_load_state('networkidle')
                    if suffix=='desktop':
                        page.request.post(f'{base}/api/stories/{story}/sources',multipart={'characters':{'name':'characters.md','mimeType':'text/plain','buffer':spec['characters'].encode('utf-8')}})
                        page.goto(base+'/');page.wait_for_load_state('networkidle');shot(page,folder/'library-desktop.png',shots)
                    page.goto(f'{base}/stories/{story}?scene={scene}&material=draft');page.wait_for_load_state('networkidle')
                    page.locator('#workspace-scene-status').wait_for();shot(page,folder/f'workspace-{suffix}.png',shots)
                    if suffix=='desktop':
                        # BRIEF-FORM: the writer's brief as a form.
                        page.goto(f'{base}/stories/{story}?scene={scene}&material=brief');page.wait_for_load_state('networkidle')
                        page.locator('#brief-form').wait_for(state='visible');shot(page,folder/'brief-form-desktop.png',shots)
                    if suffix=='desktop':
                        # MEMORY-LOCATIONS-S07: the «Locations» section of the memory panel with a suggestion and a description.
                        page.set_viewport_size({'width':1280,'height':2400})  # the whole section without the sticky tabs over it
                        page.goto(f'{base}/stories/{story}?scene={scene}&material=memory');page.wait_for_load_state('networkidle')
                        section=page.locator('#memory-view #story-locations')
                        section.locator('.location-row').first.wait_for();section.locator('.location-description').first.locator('summary').click()
                        section.scroll_into_view_if_needed();page.wait_for_timeout(300)
                        section.screenshot(path=str(folder/'locations-desktop.png'));shots.append(folder/'locations-desktop.png')
                        page.set_viewport_size(viewport);page.goto(f'{base}/stories/{story}?scene={scene}&material=draft');page.wait_for_load_state('networkidle')
                    page.locator('#story-menu-toggle').click();page.locator('#story-menu').wait_for();shot(page,folder/f'story-menu-{suffix}.png',shots)
                    if suffix=='desktop':
                        for path,name in [(f'/stories/{story}/characters','characters'),
                                          (f'/stories/{story}/settings?section=models','settings-models'),(f'/stories/{story}/publication','publication')]:
                            page.goto(base+path);page.wait_for_load_state('networkidle');shot(page,folder/f'{name}-desktop.png',shots)
                        # R16-COVER-S04: the cover panel after "Create text cover"; the card itself stays unsaved.
                        page.locator('#publication-cover-palette').select_option('wine');page.locator('#publication-cover-generate').click()
                        page.locator('#publication-cover').wait_for(state='visible');page.locator('#notice-close').click()
                        section=page.locator('section[aria-labelledby=publication-cover-title]');section.scroll_into_view_if_needed()
                        page.wait_for_timeout(300);section.screenshot(path=str(folder/'publication-cover-desktop.png'));shots.append(folder/'publication-cover-desktop.png')
                    page.close()
        finally:browser.close()
    return shots


def capture_validation(base,ids,lang):
    """VALID-LINKS-S15, VALID-UI-S06: after seed_stopped_validation — the «Узгодженість сцени» panel of scene 2 (brief not
    checked, prose with the Auditor's quote, memory consistent, «Перевірити Ревізором» with its calls) and the expanded
    run row of the stopped book validation with «Перейти до сцени 1». Element shots on a tall page, so the sticky tabs
    never cover them."""
    from playwright.sync_api import sync_playwright
    shots=[];folder=OUT/lang;folder.mkdir(parents=True,exist_ok=True);story,scene=ids['story_id'],ids['scene_id']
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            page=browser.new_page(viewport={'width':1280,'height':800},locale='uk-UA' if lang=='uk' else 'en-US')
            page.goto(base+'/');page.locator(f'[data-ui-locale={lang}]').click();page.wait_for_load_state('networkidle')
            page.set_viewport_size({'width':1280,'height':1800})
            page.goto(f'{base}/stories/{story}?scene={scene}&material=draft');page.wait_for_load_state('networkidle')
            panel=page.locator('#scene-consistency')
            panel.locator('.consistency-cost').wait_for(state='visible')
            page.locator('#run-stop-scene').wait_for(state='visible')
            page.mouse.move(0,0);page.wait_for_timeout(300)
            path=folder/'scene-consistency-desktop.png';panel.screenshot(path=str(path));shots.append(path)
            path=folder/'run-progress-desktop.png';page.locator('#workspace-status-row').screenshot(path=str(path));shots.append(path)
            page.close()
        finally:browser.close()
    return shots


def capture_editor_import(base,ids,lang,docx):
    """EDITOR-IMPORT-S11: the import dialog with the summary of the editor's DOCX; nothing is imported."""
    from playwright.sync_api import sync_playwright
    folder=OUT/lang;folder.mkdir(parents=True,exist_ok=True);story,scene=ids['story_id'],ids['scene_id']
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            page=browser.new_page(viewport={'width':1280,'height':800},locale='uk-UA' if lang=='uk' else 'en-US')
            page.goto(base+'/');page.locator(f'[data-ui-locale={lang}]').click();page.wait_for_load_state('networkidle')
            page.goto(f'{base}/stories/{story}?scene={scene}&material=draft');page.wait_for_load_state('networkidle')
            page.locator('#story-menu-toggle').click();page.locator('#import-edition').click()
            dialog=page.locator('#editor-import-dialog');dialog.wait_for(state='visible')
            dialog.locator('#editor-import-file').set_input_files({'name':'edition.docx','buffer':docx,
                'mimeType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})
            dialog.locator('#editor-import-summary').wait_for(state='visible')
            page.mouse.move(0,0);path=folder/'editor-import-desktop.png';shot(page,path,[])
            page.close()
        finally:browser.close()
    return [path]


def capture_manuscript_import(base,lang,sample):
    """MANUSCRIPT-IMPORT-S11: the library dialog on its preview step with the neutral manuscript; nothing is imported."""
    from playwright.sync_api import sync_playwright
    folder=OUT/lang;folder.mkdir(parents=True,exist_ok=True);name,content=sample
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            page=browser.new_page(viewport={'width':1280,'height':900},locale='uk-UA' if lang=='uk' else 'en-US')
            page.goto(base+'/');page.locator(f'[data-ui-locale={lang}]').click();page.wait_for_load_state('networkidle')
            page.locator('#manuscript-import-open').click()
            dialog=page.locator('#manuscript-import-dialog');dialog.wait_for(state='visible')
            dialog.locator('#manuscript-import-file').set_input_files({'name':name,'buffer':content,'mimeType':'text/markdown'})
            dialog.locator('#manuscript-import-preview').wait_for(state='visible')
            # The scenes from the first chapter on: the separator split, the proposed boundary and the epilogue in view.
            dialog.locator('.manuscript-import-scene').nth(1).evaluate('node=>node.scrollIntoView({block:"start"})')
            page.mouse.move(0,0);path=folder/'manuscript-import-desktop.png';shot(page,path,[])
            page.close()
        finally:browser.close()
    return [path]


def shot(page,path,shots):
    page.wait_for_timeout(300);page.screenshot(path=str(path));shots.append(path)


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='Зняти знімки сайту інструкцій з нейтральних творів.')
    parser.add_argument('--work-dir',help='порожній каталог для тимчасових даних (типово новий у C:/tmp)')
    parser.add_argument('--port',type=int)
    args=parser.parse_args(argv)
    work=resolve_work_dir(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix='obscura-shots-',dir='C:/tmp' if Path('C:/tmp').is_dir() else None))
    shots=[]
    for lang in STORIES:  # one data folder and server per language: each library shows only its own story
        data=work/lang/'data'
        if data.exists() and any(data.iterdir()):raise SystemExit(f'{data} не порожній: знімки беруться лише з нового seed')
        ids=seed(data,[lang]);port=args.port or free_port();ensure_port_free(port);base=f'http://127.0.0.1:{port}'
        env_file=work/lang/'empty.env';env_file.write_text('',encoding='utf-8')
        server=subprocess.Popen(server_command(data,port,env_file),cwd=ROOT,
                                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=server_env())
        try:
            wait_for(base+'/',server)
            shots+=capture(base,ids,[lang])
            seed_stopped_validation(data,ids[lang])
            shots+=capture_validation(base,ids[lang],lang)
            from storygen.storage.repository import Repository
            shots+=capture_editor_import(base,ids[lang],lang,editor_import_docx(Repository(data),ids[lang]['story_id'],lang))
            shots+=capture_manuscript_import(base,lang,manuscript_sample(lang))
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill()
    for path in shots:print(path.relative_to(ROOT).as_posix())
    print(f'Знімків: {len(shots)}; тимчасові дані: {work}')
    return 0


if __name__=='__main__':sys.exit(main())
