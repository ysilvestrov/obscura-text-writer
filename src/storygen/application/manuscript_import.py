"""MANUSCRIPT-IMPORT: the preview of an author's manuscript (spec §4.1–4.2, §3.5) and the file kept between preview and import.

The preview never creates a book: it reads the file, proposes chapters, parts and scenes and keeps the file in
`<data_dir>/manuscript-import/{import_id}.<ext>` (with the original name in `{import_id}.name`) until the import, a cancel or
24 hours pass. Backups and fsck skip the folder (`NOT_DATA`).
"""
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone

from .. import build_edition
from ..domain import new_id
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
                removed += path.suffix != '.name'  # the name file belongs to its manuscript
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
