"""EXPORT-001-S06: a readable Markdown file with the current plan and characters; built on request, never stored."""
import re

from ..characters.models import load_characters
from ..markdown_document import escape_plain_markdown
from ..plan_sections import split_plan

LABELS = {
    'uk': dict(plan='План', scene='Сцена', characters='Персонажі', no_plan='_План не створено._',
               no_characters='_Персонажів не додано._', from_scene='від сцени', trashed='від сцени в кошику', suffix='план'),
    'en': dict(plan='Plan', scene='Scene', characters='Characters', no_plan='_No plan yet._',
               no_characters='_No characters yet._', from_scene='from scene', trashed='from a scene in the trash', suffix='plan'),
}


def _file_name(title, suffix):
    # Keep letters of any script; drop characters that are unsafe in file names.
    base = re.sub(r'[\/:*?"<>|\x00-\x1f]+', ' ', title).strip(' .') or 'story'
    return f'{base[:80]}-{suffix}.md'


def plan_markdown(repo, story_id):
    """Return (file name, UTF-8 bytes); one read snapshot for scenes, plans and characters."""
    view = repo.context_view(story_id)
    story = view.get_story(story_id)
    words = LABELS.get(story.language, LABELS['uk'])
    scenes = sorted(view.list_scenes(story_id), key=lambda s: s.position)
    numbers = {s.id: (index + 1, s.title) for index, s in enumerate(scenes)}
    out = ['# ' + escape_plain_markdown(story.title), '## ' + words['plan']]
    source_plan = view.active_source(story_id, 'source_plan')
    if source_plan:
        notes = split_plan(view.read_text(source_plan.id))[0].strip()
        if notes:out.append(notes)
    for number, scene in enumerate(scenes, 1):
        # A scene keeps its imported beats until the author saves a plan version (SCENE-PLAN-TEMPLATE).
        text = view.read_text(scene.heads['plan']) if scene.heads.get('plan') else scene.beats
        out.append(f"### {words['scene']} {number}: {escape_plain_markdown(scene.title)}")
        out.append(text.strip() or words['no_plan'])
    out.append('## ' + words['characters'])
    cards = load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []
    if cards:
        for card in cards:
            out.append('### ' + escape_plain_markdown(card.name))
            lines = []
            for entry in card.entries:
                note = ''
                if entry.availability == 'from_scene':
                    found = numbers.get(entry.available_from_scene_id)
                    note = f" ({words['from_scene']} {found[0]}: {escape_plain_markdown(found[1])})" if found else f" ({words['trashed']})"
                lines.append('- ' + entry.text.strip().replace('\n', '\n  ') + note)
            if lines:out.append('\n'.join(lines))
    else:
        source = view.active_source(story_id, 'source_characters')
        text = view.read_text(source.id).strip() if source else ''
        out.append(text or words['no_characters'])
    return _file_name(story.title, words['suffix']), ('\n\n'.join(out) + '\n').encode('utf-8')
