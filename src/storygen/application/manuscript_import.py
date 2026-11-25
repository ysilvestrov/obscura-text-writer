"""MANUSCRIPT-IMPORT: the preview of an author's manuscript (spec §4.1–4.2, §3.5) and the file kept between preview and import.

The preview never creates a book: it reads the file, proposes chapters, parts and scenes and keeps the file in
`<data_dir>/manuscript-import/{import_id}.<ext>` (with the original name in `{import_id}.name`) until the import, a cancel or
24 hours pass. Backups and fsck skip the folder (`NOT_DATA`). The settings of the latest preview are kept in `{import_id}.settings.json`:
the import re-parses the file with them and compares the fingerprint.
"""
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .. import build_edition
from ..book.structure import MAX_PARTS, MAX_TITLE
from ..domain import ContentRating, ManuscriptImportOrigin, RevisionConflict, StoryCreate, new_id
from ..publication.docx_text import serialize
from ..providers.models import ProviderSettings, RoleSettings
from ..publication.manuscript_read import ManuscriptError, read_manuscript
from ..publication.manuscript_structure import ParseSettings, ProposedScene, detect, words
from ..storage.integrity import MANUSCRIPT_IMPORT_DIR

logger = logging.getLogger(__name__)
TEMP_DIR = MANUSCRIPT_IMPORT_DIR
TEMP_TTL = timedelta(hours=24)
MAX_FILE = 20 * 1024 * 1024  # every format; the DOCX reader adds its own unpacked-size limit
MAX_PARAGRAPHS = 2000
HEAD_CHARS = 160
EXTENSIONS = ('docx', 'md', 'txt')
NOT_FOUND = 'Імпорт не знайдено'
# §3.5: the upper bound of the previous memory and the settings of a memory request is this share of the role's
# `max_input_chars` (the same 1/8 the pipeline reserves for the series' future-books block, `context.py`: `max_input_chars//8`).
RESERVE_SHARE = 8
_IMPORT_ID = re.compile('[0-9a-f]{32}')
SETTINGS_SUFFIX = '.settings.json'


class ManuscriptTooLarge(ValueError):
    def __init__(self):
        super().__init__(f'Файл має бути до {MAX_FILE / (1024 * 1024):g} MiB')


def default_memory_role() -> RoleSettings:
    """The memory role the preview measures against when no book exists yet: what an unconfigured stage uses in chat
    (`chat_stages.chat_role_settings`: 131 072 context tokens, 8 192 output tokens) with the default 80 000-character input limit."""
    from .chat_stages import CHAT_CONTEXT_TOKENS, CHAT_MAX_OUTPUT_TOKENS
    return RoleSettings(provider=ProviderSettings(model='external-chat'), memory_mode='evidence_delta',
                        context_tokens=CHAT_CONTEXT_TOKENS, max_output_tokens=CHAT_MAX_OUTPUT_TOKENS)


def memory_fits(repo, role: RoleSettings | None = None):
    """`fits(text)` for `detect`: does the memory request of a scene with this prose stay within the memory role's limits.

    The request carries the prose twice (directly and as evidence fragments) plus an upper bound for the previous memory and
    the settings. It must pass both checks `_finish_context` applies: `max_input_chars` and the token budget
    (`context_tokens - max_output_tokens`), tokens estimated by the existing `token_estimate`."""
    from ..providers.requests import generation_request
    from ..token_budget.service import token_estimate
    role = role or default_memory_role()
    budget = role.context_tokens - role.max_output_tokens
    reserve = role.max_input_chars // RESERVE_SHARE
    filler = 'а' * reserve

    def fits(text: str) -> bool:
        if 2 * len(text) + reserve > role.max_input_chars:
            return False
        user = '\n\n'.join((text, text, filler))
        request = generation_request('memory', role, '', user, {})
        provider = role.provider
        return token_estimate(repo, provider.provider, provider.base_url, request)['input_tokens'] <= budget
    return fits


@dataclass(frozen=True)
class ManuscriptPreview:
    import_id: str
    fingerprint: str
    file_name: str
    title_suggestion: str | None
    chapter_source: str
    scenes: list[ProposedScene]
    parts: list[dict]
    front_matter: list[int]
    dropped: list[dict]
    warnings: list[str]
    tracked_changes: int
    edition: dict


def _checked(import_id) -> str:
    if not isinstance(import_id, str) or not _IMPORT_ID.fullmatch(import_id):
        raise KeyError(NOT_FOUND)
    return import_id


def _folder(repo):
    return repo.files.resolve(TEMP_DIR)


def _files(repo, import_id):
    folder = _folder(repo)
    if not folder.is_dir():
        return []
    return [path for path in folder.glob(f'{import_id}.*')]


def load(repo, import_id: str) -> tuple[bytes, str]:
    """(content, original file name) of a kept manuscript; KeyError for an unknown, malformed or expired id."""
    import_id = _checked(import_id)
    stored = next((path for path in _files(repo, import_id) if path.suffix[1:] in EXTENSIONS), None)
    if stored is None:
        raise KeyError(NOT_FOUND)
    try:
        content = stored.read_bytes()
    except OSError:
        raise KeyError(NOT_FOUND) from None
    name = stored.with_suffix('.name')
    try:
        file_name = name.read_text(encoding='utf-8') or stored.name
    except OSError:
        file_name = stored.name
    return content, file_name


def discard(repo, import_id: str) -> None:
    for path in _files(repo, _checked(import_id)):
        path.unlink(missing_ok=True)


def sweep_temp(repo, *, now: datetime | None = None) -> int:
    """Delete manuscript files older than 24 hours; runs on every preview and at server start."""
    folder = _folder(repo)
    if not folder.is_dir():
        return 0
    limit = (now or datetime.now(timezone.utc)).timestamp() - TEMP_TTL.total_seconds()
    removed = 0
    for path in folder.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < limit:
                path.unlink()
                removed += path.suffix[1:] in EXTENSIONS  # the name and settings files belong to their manuscript
        except OSError:
            continue
    return removed


def _fingerprint(content: bytes, settings: ParseSettings) -> str:
    canonical = json.dumps(asdict(settings), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(hashlib.sha256(content).digest() + canonical.encode('utf-8')).hexdigest()


def effective_settings(settings: ParseSettings) -> ParseSettings:
    """The edition decides whether parts exist; the request cannot widen it."""
    return replace(settings, parts_allowed=settings.parts_allowed and build_edition.current().long_prose)


def preview(repo, content: bytes, file_name: str, settings: ParseSettings, import_id: str | None = None, *,
            now: datetime | None = None, role: RoleSettings | None = None) -> ManuscriptPreview:
    """With `import_id` the kept file is parsed again and `content` is ignored."""
    sweep_temp(repo, now=now)
    if import_id is not None:
        content, file_name = load(repo, import_id)
    elif len(content) > MAX_FILE:
        raise ManuscriptTooLarge()
    settings = effective_settings(settings)
    manuscript = read_manuscript(content, file_name)  # raises ManuscriptError before anything is kept
    structure = detect(manuscript.paragraphs, settings, fits=memory_fits(repo, role))
    if import_id is None:
        import_id = new_id()
        extension = file_name.rsplit('.', 1)[-1].lower()
        repo.files.write(f'{TEMP_DIR}/{import_id}.{extension}', content)
        repo.files.write(f'{TEMP_DIR}/{import_id}.name', file_name.encode('utf-8'))
    # The import re-parses the file with the settings of the latest preview: its body names only the fingerprint.
    repo.files.write(f'{TEMP_DIR}/{import_id}{SETTINGS_SUFFIX}', json.dumps(asdict(settings), ensure_ascii=False).encode('utf-8'))
    long_prose = build_edition.current().long_prose
    return ManuscriptPreview(
        import_id=import_id, fingerprint=_fingerprint(content, settings), file_name=file_name,
        title_suggestion=structure.title_suggestion, chapter_source=structure.chapter_source,
        scenes=list(structure.scenes),
        parts=[{'index': position, 'paragraph': index, 'title': name} for position, (index, name) in enumerate(structure.parts)],
        front_matter=list(structure.front_matter),
        dropped=[{'index': index, 'text': text, 'reason': 'part_heading'} for index, text in structure.dropped],
        warnings=list(structure.warnings) + list(manuscript.warnings), tracked_changes=manuscript.tracked_changes,
        edition={'parts_allowed': long_prose, 'series_allowed': long_prose})


def paragraphs(repo, import_id: str, start: int, end: int) -> list[dict]:
    """Short descriptions of the paragraphs with index in [start, end] (inclusive, like scene ranges), at most 2 000."""
    content, file_name = load(repo, import_id)
    if start < 0 or end < start:
        raise ValueError('Некоректний діапазон абзаців')
    manuscript = read_manuscript(content, file_name)
    return [{'index': p.index, 'text_head': p.text[:HEAD_CHARS], 'words': words(p.text), 'heading_level': p.heading_level,
             'after_break': p.after_break}
            for p in manuscript.paragraphs[start:min(end + 1, start + MAX_PARAGRAPHS)]]


# --- Import: a new book from the previewed manuscript (spec §4.1–4.3) ---

STALE_PREVIEW = 'Перегляд рукопису застарів: перегляньте файл ще раз'
NO_SCENES = 'Додайте хоча б одну сцену'
BAD_BOUNDARY = 'Межа сцени має стояти на початку абзацу тексту рукопису'
UNSORTED = 'Початки сцен мають іти за зростанням'
FIRST_SCENE = 'Перша сцена має починатися з першого абзацу тексту'
UNKNOWN_PART = 'Сцена посилається на невідому частину'
PARTS_ORDER = 'Частини сцен мають іти в порядку книги'
DUPLICATE_PART = 'Номери частин мають бути унікальними'
NO_START_SNAPSHOT = 'Знімок початку серії не створено: пам’ять попередньої книги ще не побудовано'
ORIGIN_NAME_LIMIT = 255
ORIGIN_NAME_FALLBACK = 'manuscript'
STORY_MIN_WORDS = 5000  # StoryCreate.target_words lower bound


class ManuscriptApplyScene(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: int
    title: str = Field(min_length=1, max_length=200)
    part_index: int | None = None


class ManuscriptApplyPart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    index: int = Field(ge=0)
    title: str = Field(default='', max_length=MAX_TITLE)


class ManuscriptApplySeries(BaseModel):
    model_config = ConfigDict(extra='forbid')
    series_id: str = Field(min_length=1, max_length=64)
    number: int = Field(ge=1)


class ManuscriptApply(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    language: Literal['uk', 'en'] = 'uk'
    content_rating: ContentRating | None = None
    scenes: list[ManuscriptApplyScene] = Field(default_factory=list, max_length=20000)
    parts: list[ManuscriptApplyPart] = Field(default_factory=list, max_length=MAX_PARTS)
    include_front_matter: bool = False
    series: ManuscriptApplySeries | None = None


def origin_file_name(file_name: str) -> str:
    """The name kept in `ManuscriptImportOrigin`: the base name only, without unencodable surrogates, at most 255 chars."""
    name = re.split(r'[\\/]', file_name or '')[-1]
    name = name.encode('utf-8', 'ignore').decode('utf-8').strip()
    return name[:ORIGIN_NAME_LIMIT] or ORIGIN_NAME_FALLBACK


def _stored_settings(repo, import_id: str) -> ParseSettings:
    try:
        data = json.loads(repo.files.resolve(f'{TEMP_DIR}/{import_id}{SETTINGS_SUFFIX}').read_text(encoding='utf-8'))
        return ParseSettings(**{key: tuple(value) if isinstance(value, list) else value for key, value in data.items()})
    except (OSError, ValueError, TypeError):
        raise RevisionConflict(STALE_PREVIEW) from None


def _scene_ranges(body: ManuscriptApply, allowed: list[int]) -> list[list[int]]:
    """Paragraph indices of every scene: boundaries are prose paragraphs from `detect` (§8: never inside a paragraph and
    never text from the client); every included paragraph lands in exactly one scene, so nothing is dropped."""
    starts = [scene.start for scene in body.scenes]
    if not starts:
        raise ValueError(NO_SCENES)
    positions = {index: position for position, index in enumerate(allowed)}
    if any(start not in positions for start in starts):
        raise ValueError(BAD_BOUNDARY)
    if any(later <= earlier for earlier, later in zip(starts, starts[1:])):
        raise ValueError(UNSORTED)
    if starts[0] != allowed[0]:
        raise ValueError(FIRST_SCENE)
    cuts = [positions[start] for start in starts] + [len(allowed)]
    return [allowed[cuts[k]:cuts[k + 1]] for k in range(len(starts))]


def _check_parts(body: ManuscriptApply) -> dict[int, str]:
    titles = {part.index: part.title for part in body.parts}
    if len(titles) != len(body.parts):
        raise ValueError(DUPLICATE_PART)
    used = [scene.part_index for scene in body.scenes if scene.part_index is not None]
    if any(index not in titles for index in used):
        raise ValueError(UNKNOWN_PART)
    if any(later < earlier for earlier, later in zip(used, used[1:])):
        raise ValueError(PARTS_ORDER)
    return titles


def apply_import(repo, import_id: str, body) -> dict:
    """Create a new book from the kept manuscript: {story_id, scene_ids, warnings}. The file is parsed again with the
    settings of the latest preview; a fingerprint from an older preview is a conflict. The temp file is removed only
    after the book exists, so a refused import can be retried."""
    from ..book.guard import require_long_prose
    from ..storage.manuscript_store import ManuscriptSceneData, publish_manuscript
    body = ManuscriptApply.model_validate(body)
    if body.parts or body.series or any(scene.part_index is not None for scene in body.scenes):
        require_long_prose()  # §4.2: before any file or database write
    content, file_name = load(repo, import_id)
    settings = _stored_settings(repo, import_id)
    if _fingerprint(content, settings) != body.fingerprint:
        raise RevisionConflict(STALE_PREVIEW)
    manuscript = read_manuscript(content, file_name).paragraphs
    structure = detect(manuscript, settings)  # boundaries need only the prose indices; they do not depend on `fits`
    allowed = sorted(set(structure.prose_indices) | (set(structure.front_matter) if body.include_front_matter else set()))
    if not allowed:
        raise ValueError(NO_SCENES)
    ranges = _scene_ranges(body, allowed)
    part_titles = _check_parts(body)
    content_format = 'plain' if file_name.rsplit('.', 1)[-1].lower() == 'txt' else 'markdown'
    scenes = []
    for scene, indices in zip(body.scenes, ranges):
        chosen = [manuscript[index] for index in indices]
        text = serialize([p.runs for p in chosen], content_format).text
        part_title = part_titles[scene.part_index] if scene.part_index is not None else None
        scenes.append(ManuscriptSceneData(scene.title, text, content_format, part_title, sum(words(p.text) for p in chosen),
                                          scene.part_index))
    story = StoryCreate(title=body.title, language=body.language, content_rating=body.content_rating,
                        target_words=max(STORY_MIN_WORDS, sum(item.target_words for item in scenes)))
    origin = ManuscriptImportOrigin(file_name=origin_file_name(file_name), file_sha256=hashlib.sha256(content).hexdigest(),
                                    imported_at=datetime.now(timezone.utc))
    series = (body.series.series_id, body.series.number) if body.series else None
    structured = any(scene.part_index is not None for scene in body.scenes)
    created, created_scenes = publish_manuscript(repo, story, scenes, origin, structured, series=series)
    warnings = _series_start(repo, created) if series is not None else []
    discard(repo, import_id)
    return {'story_id': created.id, 'scene_ids': [scene.id for scene in created_scenes], 'warnings': warnings}


def _series_start(repo, story) -> list[str]:
    """The start snapshot, taken as entering a series takes it (`set_story_series`): only after the book is committed.
    Without the previous book's memory there is no snapshot; the author takes it later («Оновити з попередньої книги»)."""
    from ..book.series import snapshot_sources
    from ..storage import series as series_store
    if not snapshot_sources(repo.list_stories(include_trashed=True), story):
        return []  # the first book of a series has nothing to start from
    try:
        series_store.take_snapshot_if_ready(repo, story.id)
    except Exception:  # the book exists already: a failed snapshot is a warning, never a failed import
        logger.exception('Не вдалося зробити знімок початку серії для імпортованої книги')
    return [] if repo.get_story(story.id).series_start_version_id else [NO_START_SNAPSHOT]
