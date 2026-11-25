"""Helpers for the revise-skill probes: bridge tools in-process against an ISOLATED stand only
(`python scripts/skills_stand.py serve --work C:/tmp/<dir>`). Set OB_BASE to the stand URL from <dir>/mcp.json;
OBSCURA_REPO defaults to the repository root above this folder. Run from a scratch dir under C:/tmp (writes state.json)."""
import os
import sys, json
from pathlib import Path
REPO = os.environ.get('OBSCURA_REPO') or str(Path(__file__).resolve().parents[5])
sys.path[:0] = [REPO + '/src', REPO]
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from scripts.skills_stand import obscura_call
import httpx
BASE = os.environ['OB_BASE']
def call(name, **args):
    try:
        return obscura_call(BASE, name, args)
    except RuntimeError as e:
        return {'ERROR': str(e)}
def http(method, path, **kw):
    r = httpx.request(method, BASE+path, timeout=60, **kw)
    try: return r.status_code, r.json()
    except Exception: return r.status_code, r.text
def p(x, n=3000):
    print(json.dumps(x, ensure_ascii=False, indent=1)[:n])

def sid(): return json.load(open('state.json'))['sid']
def scenes(): return [s['id'] for s in call('get_story', story_id=sid())['scenes']]
def do_brief(sc, objective):
    t = call('get_stage_task', scene_id=sc, stage='brief')
    return call('save_stage_result', scene_id=sc, stage='brief', task_fingerprint=t['task_fingerprint'],
                result={'objective': objective, 'beats': ['початок','середина','кінець'], 'constraints': [], 'proposed_changes': [], 'introduced': []})
def do_draft(sc, text):
    c = call('get_scene_context', scene_id=sc)
    d = call('get_scene_text', scene_id=sc, material='draft')
    return call('save_draft', scene_id=sc, text=text, expected_revision=c['revision'], context_fingerprint=c['context_fingerprint'], draft_version_id=d.get('version_id'))
def summary(sc_ids=None):
    st = call('get_story', story_id=sid())
    for s in st['scenes']:
        print(' ', s['position'], s['title'], 'state=', s['state'], 'validity=', s['validity'], 'links=', s['links'], 'rev=', s['revision'])
def stale(sc):
    out = {}
    for m in ('draft','prose','memory'):
        r = call('get_scene_text', scene_id=sc, material=m)
        out[m] = {k: r.get(k) for k in r if k not in ('text','content')}
    return out

def core_unchanged(task):
    import re
    mat = task['material']
    seg = mat.split('ЯДРО СТАНУ ВІДСТЕЖУВАНИХ ПЕРСОНАЖІВ — УСІ СЛОТИ ОБОВ’ЯЗКОВІ\n',1)[1].split('\n',1)[0]
    core = json.loads(seg)['core']
    return {cid: {slot: {'status':'unchanged','text':'','evidence_ids':[],'reason':''} for slot in slots} for cid, slots in core.items()}
def do_memory(sc, facts, loc=None):
    t = call('get_stage_task', scene_id=sc, stage='memory')
    import re
    frag = re.findall(r'\[(f\d+)\]', t['material'])
    res = {'schema_version':4,'core':core_unchanged(t),'threads':{},
           'facts':{'add':[{'text':f,'evidence_ids':[frag[0]]} for f in facts]},
           'timeline':{'add':[]},'character_states':{'add':[],'update':[],'retire':[]},'open_threads':{'add':[]}}
    return call('save_stage_result', scene_id=sc, stage='memory', task_fingerprint=t['task_fingerprint'], result=res)

def memory_task(sc):
    import re
    t = call('get_stage_task', scene_id=sc, stage='memory')
    frag = re.findall(r'\[(f\d+)\]', t['material'])
    seg = t['material'].split('ЧИННІ ТВЕРДЖЕННЯ')[1].split('\n',2)[1]
    return t, frag, json.loads(seg)
def save_memory(sc, t, facts=(), states_add=(), states_update=(), states_retire=(), frag='f000001'):
    res = {'schema_version':4,'core':core_unchanged(t),'threads':{},
           'facts':{'add':[{'text':f,'evidence_ids':[frag]} for f in facts]},
           'timeline':{'add':[]},
           'character_states':{'add':[{'text':x,'character_ids':[],'evidence_ids':[frag]} for x in states_add],
                               'update':[{'claim_id':c,'text':x,'evidence_ids':[frag]} for c,x in states_update],
                               'retire':[{'claim_id':c,'text':x,'evidence_ids':[frag]} for c,x in states_retire]},
           'open_threads':{'add':[]}}
    return call('save_stage_result', scene_id=sc, stage='memory', task_fingerprint=t['task_fingerprint'], result=res)
def do_edit_same(sc):
    t = call('get_stage_task', scene_id=sc, stage='edit')
    if 'ERROR' in t: return t
    d = call('get_scene_text', scene_id=sc, material='draft')['text']
    return call('save_stage_result', scene_id=sc, stage='edit', task_fingerprint=t['task_fingerprint'], result=d)
def new_story(title, n=3):
    o = call('create_story', title=title, language='uk', target_words=5000, writing_mode='chat'); oid=o['id']
    st = call('get_story', story_id=oid); call('update_story', story_id=oid, expected_revision=st['revision'], content_rating={'sexual':0,'violence':0,'themes':0})
    plan = '# План\n\nРобоча назва: ' + title + '\n' + ''.join(f'\n## Сцена {i}: С{i}\nЛокація: місце {i}\nХто бере участь: Олена\nЩо відбувається: подія {i}.\n' for i in range(1, n+1))
    call('import_plan_and_characters', story_id=oid, plan_markdown=plan, characters_markdown='# Персонажі\n\n## Олена\nРоль у творі: Головна героїня.\nВік: 34\n')
    json.dump({'sid': oid}, open('state.json','w'))
    return oid
def links(sc):
    return http('GET', f'/api/stories/{sid()}')[1]['material_status'][sc]
def runs():
    return [(r['request']['mode'], r['state'], r['request'].get('scene_id'), r['id']) for r in http('GET', f'/api/stories/{sid()}/runs')[1]['runs']]
def wait_runs():
    import time
    for _ in range(40):
        if all(r[1] in ('completed','failed','cancelled','needs_review','alternative','paused') for r in runs()): return
        time.sleep(0.5)
