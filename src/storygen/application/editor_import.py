"""IMPORT-DOCX: the preview of an editor's DOCX (spec §4) and the per-scene plan the import saves (§5).

The preview never changes the story: it reads the file, matches its scenes, compares each scene with
`normalized(prose)` and keeps the file in `<data_dir>/editor-import/{import_id}.docx` until the import, a cancel
or 24 hours pass.

Status precedence of a scene: `no_prose` → `unsupported_markup` → `pending_review` → (base 'export' only)
`changed_since_export` / `unknown_base` → `over_limit` / `changed` / `comments_only` / `unchanged`.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from os.path import commonprefix
from types import SimpleNamespace
from typing import Literal

from pydantic import Field

from ..authoring.comments import InputAnchor, InputComment
from ..domain import DomainModel, new_id
from ..markdown_document import source_range_text
from ..publication.docx_import import DocxManuscript, Run, read_docx
from ..publication.docx_text import SceneText, normalized, roundtrip_ok, serialize
from ..publication.markup import chapter_paragraphs
from ..rewrite_diff import RewriteDiff, build_rewrite_diff
from .editor_import_match import Fragment, match_scenes

TEMP_DIR = 'editor-import'
TEMP_TTL = timedelta(hours=24)
# R23-COMMENTS limits: anchored and general notes together, per scene.
MAX_NOTES = 100
MAX_INSTRUCTION = 8000
MAX_GENERAL = 12000
MAX_TOTAL = 50000
QUOTE_LIMIT = 200
_WORD = re.compile(r'\w')
IMPORTED = frozenset({'changed', 'comments_only', 'over_limit'})


class ScenePreview(DomainModel):
    scene_id: str
    title: str
    status: str
    needs_choice: bool = False
    edits: int = 0
    comments: int = 0
    general_comments: int = 0
    dropped_comments: int = 0
    replace_status: str | None = None  # what changed_scenes='replace' would do with a scene that needs a choice
    warnings: list[str] = Field(default_factory=list)


class ImportPreview(DomainModel):
    import_id: str
    export_id: str | None
    fingerprint: str
    choice_required: bool
    scenes: list[ScenePreview]
    unmatched: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ScenePlan:
    status: str
    normalized: SceneText | None
    editor_text: str
    proposal: RewriteDiff | None
    general: str
    comments: list[InputComment]
    dropped: int
    warnings: list[str]
    general_count: int = 0
    needs_choice: bool = False

    @property
    def edits(self) -> int:
        return len(self.proposal.edits) if self.proposal else 0


@dataclass
class _Note:
    instruction: str
    line: str
    anchor: tuple[int, int] | None = None
    anchor_fields: dict = field(default_factory=dict)


def load_manifest(repo, story_id: str, export_id: str | None) -> dict | None:
    """The manifest of the export the file came from, or None when it is missing or damaged."""
    if not isinstance(export_id, str) or not re.fullmatch('[0-9a-f]{32}', export_id):
        return None
    path = repo.files.resolve(f'stories/{story_id}/exports/{export_id}.manifest.json')
    try:
        manifest = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if (not isinstance(manifest, dict) or manifest.get('schema_version') != 2 or manifest.get('story_id') != story_id
            or manifest.get('export_id') != export_id or not isinstance(manifest.get('scenes'), list)
            or not all(isinstance(entry, dict) and isinstance(entry.get('scene_id'), str) for entry in manifest['scenes'])):
        return None
    return manifest


def scene_order(repo, story_id: str, manifest: dict | None) -> list[tuple[str, str]]:
    """(scene_id, title) of non-trashed scenes: manifest order and export titles, else the plan order."""
    scenes = repo.list_scenes(story_id)
    if manifest is None:
        return [(scene.id, scene.title) for scene in scenes]
    active = {scene.id for scene in scenes}
    return [(entry['scene_id'], str(entry.get('title') or '')) for entry in manifest['scenes'] if entry['scene_id'] in active]


def manifest_entry(manifest: dict | None, scene_id: str) -> dict | None:
    if manifest is None:
        return None
    return next((entry for entry in manifest['scenes'] if entry['scene_id'] == scene_id), None)


def _text(runs):
    return ''.join(run.text for run in runs)


def _quote(text):
    text = ' '.join(text.split('\n'))
    return text if len(text) <= QUOTE_LIMIT else text[:QUOTE_LIMIT - 1] + '…'


def _original_quote(doc, start, end):
    if end is None or end < start:
        return ''
    if start[0] == end[0]:
        return _text(doc.paragraphs[start[0]].original)[start[1]:end[1]]
    pieces = [_text(doc.paragraphs[start[0]].original)[start[1]:]]
    pieces += [_text(doc.paragraphs[i].original) for i in range(start[0] + 1, end[0])]
    pieces.append(_text(doc.paragraphs[end[0]].original)[:end[1]])
    return '\n'.join(pieces)


def _changed_span(original, editor):
    """(prefix, suffix) lengths both views share, cut back to whole words; the editor's change lies between them."""
    prefix = len(commonprefix([original, editor]))
    while prefix and _WORD.match(original[prefix - 1]):
        prefix -= 1
    limit = min(len(original), len(editor)) - prefix
    suffix = min(len(commonprefix([original[::-1], editor[::-1]])), limit)
    while suffix and _WORD.match(original[len(original) - suffix]):
        suffix -= 1
    return prefix, suffix


def _width(source, position, char, content_format):
    """Source length of one visible character at `position` (escapes and entities are longer than one)."""
    if content_format == 'markdown':
        if source.startswith('\\' + char, position):
            return 2
        if char == ' ' and source.startswith('&#x20;', position):
            return 6
        if char == '\t' and source.startswith('&#x9;', position):
            return 5
    return 1


def _anchor(norm, paragraph, start, end, char, content_format):
    source = norm.text
    begin = norm.position(paragraph, start)
    last = norm.position(paragraph, end - 1)
    finish = last + _width(source, last, char, content_format)
    try:
        display = source_range_text(source, begin, finish, content_format)
    except ValueError:
        return None
    if not display or not source[begin:finish]:
        return None
    return {'start': begin, 'end': finish, 'source_quote': source[begin:finish], 'display_quote': display}


@dataclass(frozen=True)
class _View:
    """One view of a scene with paragraph-mark revisions applied: joined paragraphs and where doc paragraphs went."""
    paragraphs: list[tuple[Run, ...]]
    groups: list[list[int]]  # doc paragraph indices of each joined paragraph
    where: dict[int, tuple[int, int]]  # doc paragraph index -> (joined paragraph, offset of its text in it)


def _merged(runs):
    out = []
    for run in runs:
        if out and (out[-1].bold, out[-1].italic) == (run.bold, run.italic):
            out[-1] = Run(out[-1].text + run.text, run.bold, run.italic)
        elif run.text:
            out.append(run)
    return tuple(out)


def _view(doc, fragment, name: Literal['original', 'editor']) -> _View:
    """Word semantics: an inserted mark joins a paragraph with the next one in the original view, a deleted mark
    in the editor's view; a wholly inserted (deleted) paragraph so adds nothing to the original (editor's) view."""
    flag = 'mark_inserted' if name == 'original' else 'mark_deleted'
    paragraphs, groups, where = [], [], {}
    runs, group, base = [], [], 0
    for index in range(fragment.first, fragment.last):
        paragraph = doc.paragraphs[index]
        own = getattr(paragraph, name)
        where[index] = (len(paragraphs), base)
        runs += own
        group.append(index)
        base += len(_text(own))
        if getattr(paragraph, flag):
            if index + 1 < fragment.last:
                continue
            if not base:
                break  # an empty last paragraph joins the next heading and adds nothing to the scene
        paragraphs.append(_merged(runs))
        groups.append(group)
        runs, group, base = [], [], 0
    return _View(paragraphs, groups, where)


def _notes(doc, fragment, view, norm, prose_paragraphs, content_format, anchored_allowed):
    notes = []
    for comment in sorted((c for c in doc.comments if c.start and fragment.first - 1 <= c.start[0] < fragment.last),
                          key=lambda c: c.start):
        author = comment.author.strip()
        text = comment.text.strip() or '(порожня примітка)'
        who = f'Редактор ({author})' if author else 'Редактор'
        instruction = f'{who}: {text}'
        start, end = comment.start, comment.end
        quote, inserted, anchor = _original_quote(doc, start, end), False, None
        first, last = view.where.get(start[0]), view.where.get(end[0]) if end else None
        if first and last and first[0] == last[0] < len(view.paragraphs):
            index, begin, finish = first[0], first[1] + start[1], last[1] + end[1]
            group = view.groups[index]
            original = _text(view.paragraphs[index])
            editor = ''.join(_text(doc.paragraphs[i].editor) for i in group)
            changed = any(doc.paragraphs[i].changed for i in group)
            prefix, suffix = _changed_span(original, editor) if changed else (len(original), 0)
            if begin == finish and changed and prefix <= begin <= len(original) - suffix:
                quote, inserted = editor[prefix:len(editor) - suffix], True
            clean = not changed or finish <= prefix or begin >= len(original) - suffix
            if (anchored_allowed and begin < finish and clean and index < len(prose_paragraphs)
                    and _text(prose_paragraphs[index]) == original):
                anchor = _anchor(norm, index, begin, finish, original[finish - 1], content_format)
        mark = ' (вставлено редактором)' if inserted else ''
        line = f'{who} до «{_quote(quote)}»{mark}: {text}' if quote else f'{who}: {text}'
        notes.append(_Note(instruction, line, (anchor['start'], anchor['end']) if anchor else None, anchor or {}))
    kept_end = -1
    for note in sorted((n for n in notes if n.anchor), key=lambda n: n.anchor[0]):
        if note.anchor[0] < kept_end:
            note.anchor = None  # overlaps an earlier anchored note: becomes a general comment
        else:
            kept_end = note.anchor[1]
    return notes


def _limited(notes):
    general, comments, dropped, total, count = [], [], 0, 0, 0
    for note in notes:
        if note.anchor:
            size, fits = len(note.instruction), len(note.instruction) <= MAX_INSTRUCTION
        else:
            size = len(note.line) + (1 if general else 0)
            fits = len('\n'.join([*general, note.line])) <= MAX_GENERAL
        if count >= MAX_NOTES or not fits or total + size > MAX_TOTAL:
            dropped += 1
            continue
        count += 1
        total += size
        if note.anchor:
            comments.append(InputComment(id=f'editor-import-{len(comments) + 1}', instruction=note.instruction,
                                         anchor=InputAnchor(**note.anchor_fields)))
        else:
            general.append(note.line)
    return '\n'.join(general), comments, dropped, len(general)


def _skip(status, warnings=()):
    return ScenePlan(status, None, '', None, '', [], 0, list(warnings))


def plan_scene(repo, story_id, scene, fragment: Fragment, doc: DocxManuscript, manifest_entry: dict | None, *,
               base: Literal['export', 'current']) -> ScenePlan:
    """What importing one matched scene means; base 'current' is the comparison of changed_scenes='replace'."""
    head = scene.heads.get('prose')
    if head is None:
        return _skip('no_prose')
    ref = repo.get_version(head)
    prose, content_format = repo.read_text(head), ref.content_format
    if not roundtrip_ok(prose, content_format):
        return _skip('unsupported_markup', ['Розмітку прози не можна передати через DOCX без змін; сцену не імпортовано.'])
    if any(a.state == 'needs_review' for a in repo.list_attempts(story_id, scene_id=scene.id, context_key='editor_import')):
        return _skip('pending_review', ['Спершу вирішіть пропозицію попереднього імпорту редакції.'])
    norm = normalized(prose, content_format)
    body = doc.paragraphs[fragment.first:fragment.last]
    original_view = _view(doc, fragment, 'original')
    editor_text = serialize(_view(doc, fragment, 'editor').paragraphs, content_format).text
    warnings = []
    if content_format == 'plain' and any(run.bold or run.italic for p in body for run in p.editor):
        warnings.append('Проза у простому тексті: курсив і жирний з DOCX не переносяться.')
    if fragment.first > 0 and doc.paragraphs[fragment.first - 1].changed:
        warnings.append('Правку в заголовку сцени не імпортовано: заголовок не є прозою.')
    if base == 'export':
        status = None
        if manifest_entry is not None:
            if manifest_entry.get('version_id') != head:
                status = 'changed_since_export'
                warnings.append('Прозу сцени змінено після експорту.')
        elif serialize(original_view.paragraphs, content_format).text != norm.text:
            status = 'unknown_base'
            warnings.append('Експорт не знайдено; редактор правив без режиму виправлень або прозу змінено.')
        if status:
            return ScenePlan(status, norm, editor_text, None, '', [], 0, warnings, needs_choice=True)
    proposal = None
    has_comments = any(c.start and fragment.first - 1 <= c.start[0] < fragment.last for c in doc.comments)
    if editor_text == norm.text:
        status = 'comments_only' if has_comments else 'unchanged'
    else:
        try:
            proposal = build_rewrite_diff(norm.text, editor_text)
            status = 'changed'
        except ValueError:
            status = 'over_limit'
            if not editor_text.strip():
                warnings.append('Редактор видалив увесь текст сцени.')
            else:
                warnings.append('Лише чернетка: правки не вміщуються в перегляд.')
    prose_paragraphs = list(chapter_paragraphs(SimpleNamespace(text=prose, content_format=content_format)))
    notes = _notes(doc, fragment, original_view, norm, prose_paragraphs, content_format, anchored_allowed=status != 'over_limit')
    general, comments, dropped, general_count = _limited(notes)
    if dropped:
        warnings.append(f'Примітки понад межі не імпортовано: {dropped}.')
    return ScenePlan(status, norm, editor_text, proposal, general, comments, dropped, warnings, general_count)


def _draft_comments(repo, scene_id):
    state = repo.get_comment_state(scene_id)
    notes = state['comment_set']
    if not notes or not state['source_matches_current']:
        return 0
    return len(notes.comments) + (1 if notes.general.strip() else 0)


def _where(fragments, scenes, index):
    for fragment in fragments:
        if fragment.first - 1 <= index < fragment.last:
            place = 'заголовок' if index == fragment.first - 1 else f'абзац {index - fragment.first + 1}'
            if fragment.scene_id:
                return fragment.scene_id, f'«{scenes[fragment.scene_id].title}», {place}'
            return None, f'Фрагмент «{fragment.heading}», {place}'
    return None, f'Абзац {index + 1} документа'


def sweep_temp(repo, *, now: datetime | None = None) -> int:
    """Delete import files older than 24 hours; runs on every preview and at server start."""
    folder = repo.files.resolve(TEMP_DIR)
    if not folder.is_dir():
        return 0
    limit = (now or datetime.now(timezone.utc)).timestamp() - TEMP_TTL.total_seconds()
    removed = 0
    for path in folder.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < limit:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


@dataclass(frozen=True)
class _Item:
    scene: object
    fragment: Fragment
    entry: dict | None
    plan: ScenePlan
    counted: ScenePlan  # the plan the preview counts: base 'current' for a scene that needs a choice
    preview: ScenePreview


@dataclass(frozen=True)
class _Summary:
    doc: DocxManuscript
    items: list[_Item]
    fingerprint: str
    unmatched: list[str]
    warnings: list[str]

    @property
    def choice_required(self) -> bool:
        return any(item.plan.needs_choice for item in self.items)


def _summary(repo, story_id: str, content: bytes) -> _Summary:
    """The read-only part of the preview; the save rebuilds it from the kept file to check the fingerprint."""
    repo.get_story(story_id)
    doc = read_docx(content)
    if doc.story_id != story_id:
        raise ValueError('Файл з іншого твору')
    manifest = load_manifest(repo, story_id, doc.export_id)
    warnings = []
    if manifest is None:
        warnings.append('Експорт, з якого зроблено файл, не знайдено або його маніфест пошкоджено: '
                        'сцени, правлені без режиму виправлень, потребують вашого вибору.')
    fragments, match_warnings = match_scenes(doc, scene_order(repo, story_id, manifest))
    warnings += match_warnings
    scenes = {scene.id: scene for scene in repo.list_scenes(story_id)}
    reader_warnings: dict[str, list[str]] = {}
    for item in doc.warnings:
        if item.paragraph is None:
            warnings.append(item.text)
            continue
        scene_id, place = _where(fragments, scenes, item.paragraph)
        (reader_warnings.setdefault(scene_id, []) if scene_id else warnings).append(f'{place}: {item.text}')
    inside = [c for c in doc.comments if c.start and any(
        f.scene_id and f.first - 1 <= c.start[0] < f.last for f in fragments)]
    if len(inside) < len(doc.comments):
        warnings.append(f'Примітки поза розпізнаними сценами не імпортовано: {len(doc.comments) - len(inside)}.')
    items, identity = [], []
    for fragment in fragments:
        if not fragment.scene_id:
            continue
        scene = scenes[fragment.scene_id]
        identity.append([scene.id, scene.heads.get('prose'), scene.head_revisions.get('prose')])
        entry = manifest_entry(manifest, scene.id)
        plan = plan_scene(repo, story_id, scene, fragment, doc, entry, base='export')
        counted, replace_status = plan, None
        if plan.needs_choice:
            counted = plan_scene(repo, story_id, scene, fragment, doc, entry, base='current')
            replace_status = counted.status
        scene_warnings = list(dict.fromkeys(plan.warnings + counted.warnings + reader_warnings.get(scene.id, [])))
        if plan.needs_choice or plan.status in IMPORTED:
            existing = _draft_comments(repo, scene.id)
            if existing:
                scene_warnings.append(f'У чинній чернетці є коментарі ({existing}); вони лишаться в попередній версії чернетки.')
        preview = ScenePreview(scene_id=scene.id, title=scene.title, status=plan.status, needs_choice=plan.needs_choice,
            edits=counted.edits, comments=len(counted.comments), general_comments=counted.general_count,
            dropped_comments=counted.dropped, replace_status=replace_status, warnings=scene_warnings)
        items.append(_Item(scene, fragment, entry, plan, counted, preview))
    digest = hashlib.sha256(content).hexdigest()
    fingerprint = hashlib.sha256(json.dumps({'file_sha256': digest, 'export_id': doc.export_id, 'scenes': identity},
                                            sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return _Summary(doc, items, fingerprint, [f.heading for f in fragments if not f.scene_id], warnings)


def preview_import(repo, story_id: str, content: bytes, *, now: datetime | None = None) -> ImportPreview:
    sweep_temp(repo, now=now)
    summary = _summary(repo, story_id, content)
    import_id = new_id()
    repo.files.write(f'{TEMP_DIR}/{import_id}.docx', content)
    return ImportPreview(import_id=import_id, export_id=summary.doc.export_id, fingerprint=summary.fingerprint,
                         choice_required=summary.choice_required, scenes=[item.preview for item in summary.items],
                         unmatched=summary.unmatched, warnings=summary.warnings)


class ImportResult(DomainModel):
    imported: list[str]
    draft_only: list[str]  # over_limit: the editor's text became the draft, without a proposal (§5.1); also in imported
    skipped: list[dict]  # {scene_id, status}; unchanged scenes are not listed
    warnings: list[str]


STALE_PREVIEW = 'Твір змінився після зведення; перегляньте його ще раз'
WHOLE_SCENE_DELETED = 'редактор вилучив увесь текст сцени'


def _temp_path(import_id):
    if not isinstance(import_id, str) or not re.fullmatch('[0-9a-f]{32}', import_id):
        raise KeyError('Імпорт не знайдено')
    return f'{TEMP_DIR}/{import_id}.docx'


def _proposal_factory(repo, story_id, scene_id, plan, attempt_id, origin, scene_index):
    """Builds the model-less edit proposal of a changed scene inside the save transaction (§5.2)."""
    from ..domain import StageAttempt
    from ..generation.context import make_context
    from ..rewrite_diff import rewrite_warnings
    from .chat_stages import chat_role_settings
    settings = chat_role_settings(repo, story_id, 'edit')

    def factory(draft_ref, view):
        scene = view.get_scene(scene_id)
        draft_text = view.read_text(draft_ref.id)
        ctx = make_context(view, view.story, scene, 'edit', settings, [draft_text], [draft_ref.id],
                           {'copyedit_draft_id': draft_ref.id})
        attempt = StageAttempt(id=attempt_id, story_id=story_id, scene_id=scene_id, stage='edit', state='needs_review',
                               context=ctx.model_dump(), partial_path=f'stories/{story_id}/runs/{attempt_id}/partial.txt')
        attempt.context.update(
            copyedit_proposal={'protocol_version': 2, 'draft_id': draft_ref.id, 'proposal': plan.proposal.model_dump()},
            editor_import={'import_id': origin.import_id, 'export_id': origin.export_id, 'scene_index': scene_index},
            editor_warnings=rewrite_warnings(draft_text, plan.editor_text, plan.proposal.edits))
        return attempt
    return factory


def _save_scene(repo, story_id, item, plan, origin, scene_index):
    from ..authoring.comments import CommentPayload
    from ..domain import RevisionConflict
    scene = repo.get_scene(item.scene.id)
    head = scene.heads.get('prose')
    if head != item.scene.heads.get('prose') or scene.head_revisions.get('prose') != item.scene.head_revisions.get('prose'):
        raise RevisionConflict(STALE_PREVIEW)
    content_format = repo.get_version(head).content_format
    text = plan.editor_text if plan.status == 'over_limit' else plan.normalized.text
    factory = None
    if plan.status == 'changed':
        attempt_id = new_id()
        # The partial goes first: a stray file after a failed transaction is harmless, an attempt without one is not.
        with repo.files.open_partial(f'stories/{story_id}/runs/{attempt_id}/partial.txt') as out:
            out.write(plan.editor_text.encode('utf-8'))
        factory = _proposal_factory(repo, story_id, scene.id, plan, attempt_id, origin, scene_index)
    repo.save_draft_with_comments(scene.id, text, content_format, scene.revision,
        repo.get_comment_state(scene.id)['expected_comments_revision'],
        CommentPayload(general=plan.general, comments=plan.comments),
        expected_source_version_id=scene.heads.get('draft'), editor_import=origin, attempt_factory=factory)


def apply_import(repo, story_id: str, import_id: str, fingerprint: str,
                 changed_scenes: Literal['skip', 'replace'] | None) -> ImportResult:
    """Save the previewed import (§5): per scene, draft, comments and (for `changed`) the proposal in one transaction."""
    from ..domain import EditorImportOrigin, RevisionConflict
    path = repo.files.resolve(_temp_path(import_id))
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        raise KeyError('Імпорт не знайдено; завантажте файл ще раз') from None
    if changed_scenes not in (None, 'skip', 'replace'):
        raise ValueError('Невідомий вибір для змінених сцен')
    summary = _summary(repo, story_id, content)
    if summary.fingerprint != fingerprint:
        raise RevisionConflict(STALE_PREVIEW)
    if summary.choice_required and changed_scenes is None:
        raise ValueError('Оберіть, що робити зі сценами, зміненими після експорту')
    origin = EditorImportOrigin(import_id=import_id, export_id=summary.doc.export_id)
    imported, draft_only, skipped, warnings = [], [], [], list(summary.warnings)
    for index, item in enumerate(summary.items):
        plan = item.plan
        if plan.needs_choice and changed_scenes == 'replace':
            plan = item.counted
        if plan.status not in IMPORTED:
            if plan.status != 'unchanged':
                skipped.append({'scene_id': item.scene.id, 'status': plan.status})
            continue
        if not plan.editor_text.strip():
            skipped.append({'scene_id': item.scene.id, 'status': plan.status})
            warnings.append(f'«{item.scene.title}»: {WHOLE_SCENE_DELETED}; сцену не імпортовано.')
            continue
        _save_scene(repo, story_id, item, plan, origin, index)
        imported.append(item.scene.id)
        if plan.status == 'over_limit':
            draft_only.append(item.scene.id)
        warnings += [f'«{item.scene.title}»: {text}' for text in item.preview.warnings]
    path.unlink(missing_ok=True)
    return ImportResult(imported=imported, draft_only=draft_only, skipped=skipped, warnings=warnings)


def cancel_import(repo, story_id: str, import_id: str) -> None:
    """«Скасувати» of the preview dialog: nothing is written, the kept file is deleted."""
    repo.get_story(story_id)
    repo.files.resolve(_temp_path(import_id)).unlink(missing_ok=True)
