"""A book with two fully written scenes for the `revise` skill scenarios (CLAUDE-SKILLS), built without any model.

The plan, the scenes' prose and the memory all mention the city Одеса, so a scenario can ask to replace it.

    python integrations/claude/tools/revise_setup.py --work C:/tmp/r40fx [--mode obscura]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]

from scripts.skills_stand import obscura_call, start_stand  # noqa: E402

FIXTURE = Path(__file__).resolve().parent/'fixture'
REVISE_TITLE = 'Маяк на Ланжероні'
OLD_STEM = 'Одес'
NEW_CITY = 'Херсон'
NEW_STEM = 'Херсон'
MEMORY_FACT = 'Анна живе на маяку під Одесою.'
BRIEFS = [
    {'objective': 'Анна знаходить лист без підпису з попередженням і вирішує чатувати в четвер.',
     'beats': ['Анна відкриває скриньку й знаходить конверт без марки й підпису.',
               'Петро приходить через зламаний човен і просить ключ від човнової хати.',
               'Вони читають лист разом; Петро розповідає про нічного чужинця; Анна вирішує чатувати в четвер.'],
     'constraints': [], 'proposed_changes': [], 'introduced': []},
    {'objective': 'Анна чатує в ліхтарній кімнаті й бачить, що попередження було правдою.',
     'beats': ['Анна перевіряє лампу й двері.', 'Вона чує кроки на сходах.', "У дверях з'являється сіра кепка."],
     'constraints': [], 'proposed_changes': [], 'introduced': []}]


def fixture_text(name):
    return (FIXTURE/'revise'/name).read_text(encoding='utf-8')


def _core_unchanged(task):
    """The memory core answer: every slot of every tracked character stays as it is."""
    head = task['material'].split('ЯДРО СТАНУ ВІДСТЕЖУВАНИХ ПЕРСОНАЖІВ — УСІ СЛОТИ ОБОВ’ЯЗКОВІ\n', 1)[1].split('\n', 1)[0]
    core = json.loads(head)['core']
    return {cid: {slot: {'status': 'unchanged', 'text': '', 'evidence_ids': [], 'reason': ''} for slot in slots}
            for cid, slots in core.items()}


def _memory_result(task):
    """One fact about the city, with the evidence of the first fragment that names it (taken from the task material)."""
    fragments = re.findall(r'\[(f\d+)\]([^\[]*)', task['material'])
    evidence = next((fid for fid, text in fragments if OLD_STEM in text), None)
    if evidence is None:
        raise SystemExit('у матеріалі пам’яті немає фрагмента з містом')
    return {'schema_version': 4, 'core': _core_unchanged(task), 'threads': {},
            'facts': {'add': [{'text': MEMORY_FACT, 'evidence_ids': [evidence]}]},
            'timeline': {'add': []}, 'character_states': {'add': [], 'update': [], 'retire': []},
            'open_threads': {'add': []}}


def _stage(base, scene, stage, result):
    task = obscura_call(base, 'get_stage_task', {'scene_id': scene, 'stage': stage})
    result = result(task) if callable(result) else result
    obscura_call(base, 'save_stage_result', {'scene_id': scene, 'stage': stage,
                                             'task_fingerprint': task['task_fingerprint'], 'result': result})
    return task


def prepare_revise(base, writing_mode='chat'):
    """The book with two written scenes (plan, brief, draft, prose, memory); (story id, [scene ids])."""
    story = obscura_call(base, 'create_story', {'title': REVISE_TITLE, 'language': 'uk', 'writing_mode': 'chat',
                                                'content_rating': {'sexual': 0, 'violence': 0, 'themes': 0}})
    obscura_call(base, 'import_plan_and_characters', {
        'story_id': story['id'], 'plan_markdown': fixture_text('plan.md'),
        'characters_markdown': (FIXTURE/'characters.md').read_text(encoding='utf-8')})
    scenes = [s['id'] for s in obscura_call(base, 'get_story', {'story_id': story['id']})['scenes']]
    for number, scene in enumerate(scenes, 1):
        prose = fixture_text(f'prose-{number}.md')
        _stage(base, scene, 'brief', BRIEFS[number-1])
        context = obscura_call(base, 'get_scene_context', {'scene_id': scene})
        obscura_call(base, 'save_draft', {'scene_id': scene, 'text': prose, 'draft_version_id': None,
                                          'expected_revision': context['revision'],
                                          'context_fingerprint': context['context_fingerprint']})
        edit = obscura_call(base, 'get_stage_task', {'scene_id': scene, 'stage': 'edit'})
        if edit['result_format'] != 'prose':
            raise SystemExit(f"очікувався edit у форматі prose, а не {edit['result_format']}")
        obscura_call(base, 'save_stage_result', {'scene_id': scene, 'stage': 'edit',
                                                 'task_fingerprint': edit['task_fingerprint'], 'result': prose})
        _stage(base, scene, 'memory', _memory_result)
    if writing_mode != 'chat':
        import httpx
        revision = obscura_call(base, 'get_story', {'story_id': story['id']})['revision']
        reply = httpx.put(f"{base}/api/stories/{story['id']}/writing-mode", timeout=60,
                          json={'writing_mode': writing_mode, 'expected_revision': revision})
        reply.raise_for_status()
    return story['id'], scenes


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Книга з двома написаними сценами для сценаріїв revise.')
    parser.add_argument('--work', required=True)
    parser.add_argument('--mode', choices=['chat', 'obscura'], default='chat')
    args = parser.parse_args(argv)
    with start_stand(Path(args.work)) as stand:
        story, scenes = prepare_revise(stand.base, args.mode)
        state = obscura_call(stand.base, 'get_story', {'story_id': story})
        print('story', story, 'writing_mode:', state.get('writing_mode'))
        for scene in state['scenes']:
            print(' ', scene['position'], scene['title'], 'state=', scene['state'], 'validity=', scene['validity'],
                  'links=', scene['links'])
        for scene in scenes:
            memory = obscura_call(stand.base, 'get_scene_text', {'scene_id': scene, 'material': 'memory'})
            print(' memory', scene, 'version_id=', memory.get('version_id'),
                  OLD_STEM in json.dumps(memory, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
