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
          'location_description':('Маяк','Білий маяк на скелі; гвинтові сходи ведуть до ліхтарної.')},
    'en':{'title':'Lighthouse pier','scenes':['Morning in the village','An unsigned letter','The storm','Coming back'],'hero':'Anna',
          'brief':'{"objective":"Anna finds the letter and decides to read it","beats":["Anna opens the box on the pier","Inside lies an envelope with no signature","The sea wind almost tears the paper away"],"constraints":["No flashbacks"],"proposed_changes":[]}',
          'draft':'Anna opened the box on the pier and found an envelope with no signature. The sea wind tugged at the paper.',
          'characters':'## Anna\nThe lighthouse keeper, attentive to small things.\n\n## Peter\nA fisherman and an old friend of the family.\n',
          'location_label':'Location','locations':['Lighthouse / lamp room','Pier','Pier by the lighthouse','Lighthouse'],
          'location_description':('Lighthouse','A white lighthouse on the rock; a spiral stair leads to the lamp room.')},
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
        scene=scenes[1]
        brief=repo.save_version(story.id,scene.id,'brief',spec['brief'],[])
        repo.set_head(scene.id,'brief',brief.id,repo.get_scene(scene.id).revision)
        draft=repo.save_version(story.id,scene.id,'draft',spec['draft'],[brief.id])
        repo.set_head(scene.id,'draft',draft.id,repo.get_scene(scene.id).revision)
        result[lang]={'story_id':story.id,'scene_id':scene.id}
    return result


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
                        for path,name in [(f'/stories/{story}/revision','revision'),(f'/stories/{story}/characters','characters'),
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
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill()
    for path in shots:print(path.relative_to(ROOT).as_posix())
    print(f'Знімків: {len(shots)}; тимчасові дані: {work}')
    return 0


if __name__=='__main__':sys.exit(main())
