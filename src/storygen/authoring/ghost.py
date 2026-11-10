"""Ghost Mode (#55): splitting an AI draft into rewrite blocks and measuring verbatim overlap.

`web/static/ghost-blocks.js` mirrors `ghost_blocks`; both are checked against `tests/fixtures/ghost_blocks.json`."""
import re
from dataclasses import dataclass, asdict

GHOST_MIN_BLOCK_CHARS = 160
SEPARATORS = {'***', '* * *', '---', '___'}
_GAP = re.compile(r'\n\s*\n')
_HEADING = re.compile(r'#{1,6}(\s|$)')
_TOKEN = re.compile(r"[\w'-]+")


@dataclass(frozen=True)
class GhostBlock:
    kind: str
    start: int
    end: int

    def as_dict(self):
        return asdict(self)


def normalize(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _paragraphs(text):
    """(start, end) of each non-empty paragraph after strip, in LF text."""
    out = []
    position = 0
    for gap in [*_GAP.finditer(text), None]:
        stop = gap.start() if gap else len(text)
        chunk = text[position:stop]
        stripped = chunk.strip()
        if stripped:
            lead = len(chunk) - len(chunk.lstrip())
            out.append((position + lead, position + lead + len(stripped)))
        if gap:
            position = gap.end()
    return out


def ghost_blocks(text: str) -> list[GhostBlock]:
    text = normalize(text)
    blocks: list[GhostBlock] = []
    current: list[tuple[int, int]] = []
    fragment_start = 0  # index in `blocks` where the current fragment (between separators) begins

    def size(parts):
        return sum(end - start for start, end in parts)

    def close(boundary):
        nonlocal current
        if not current:
            return
        short = boundary and size(current) < GHOST_MIN_BLOCK_CHARS
        heading = bool(_HEADING.match(text[current[0][0]:current[0][1]]))
        if short and not heading and len(blocks) > fragment_start and blocks[-1].kind == 'text':
            previous = blocks.pop()
            blocks.append(GhostBlock('text', previous.start, current[-1][1]))
        else:
            blocks.append(GhostBlock('text', current[0][0], current[-1][1]))
        current = []

    for start, end in _paragraphs(text):
        body = text[start:end]
        if body in SEPARATORS:
            close(True)
            blocks.append(GhostBlock('separator', start, end))
            fragment_start = len(blocks)
            continue
        if _HEADING.match(body) and current:
            close(True)
        current.append((start, end))
        if size(current) >= GHOST_MIN_BLOCK_CHARS:
            close(False)
    close(True)
    return blocks


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower().replace('’', "'").replace('ʼ', "'"))


def overlap_4gram(author: str, draft: str) -> float | None:
    """Share of the author's 4-token windows that also occur in the draft; None when the author text is shorter than 4 tokens."""
    mine = _tokens(author)
    if len(mine) < 4:
        return None
    theirs = _tokens(draft)
    if len(theirs) < 4:
        return 0.0
    known = {tuple(theirs[i:i + 4]) for i in range(len(theirs) - 3)}
    windows = [tuple(mine[i:i + 4]) for i in range(len(mine) - 3)]
    return round(sum(window in known for window in windows) / len(windows), 4)


def save_ghost_rewrite(repo, scene_id: str, *, source_draft_id: str, text: str, content_format, expected_revision: int, client_stats: dict):
    """Save the author's rewrite as a manual draft whose author_lineage is the AI draft (#55); the AI draft is untouched."""
    from ..domain import AuthorLineage, GhostRewriteStats
    from ..generation.dependencies import save_manual_draft
    source = repo.get_version(source_draft_id)
    if source.scene_id != scene_id or source.kind != 'draft' or not source.complete:
        raise ValueError('Переписати по пам’яті можна лише повну чернетку цієї сцени')
    original = repo.read_text(source_draft_id)
    blocks = sum(block.kind == 'text' for block in ghost_blocks(original))
    skipped = client_stats['blocks_skipped']
    if skipped > blocks:
        raise ValueError('Пропущених блоків більше, ніж блоків у чернетці')
    stats = GhostRewriteStats(source_draft_id=source_draft_id, blocks=blocks, blocks_written=blocks - skipped, blocks_skipped=skipped,
        peeks=client_stats['peeks'], peek_ms=client_stats['peek_ms'], pastes_blocked=client_stats['pastes_blocked'],
        overlap_4gram=overlap_4gram(text, original), min_block_chars=GHOST_MIN_BLOCK_CHARS)
    return save_manual_draft(repo, scene_id, text, expected_revision, content_format or source.content_format,
        author_lineage=AuthorLineage(parent_version_id=source_draft_id), ghost_rewrite=stats)
