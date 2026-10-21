"""Exact source spans shared by memory evidence and bounded copy edits."""
import re

from pydantic import Field

from .domain import DomainModel


class SourceFragment(DomainModel):
    id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)


def fragment_text(text: str) -> list[SourceFragment]:
    # A physical nonempty line is one contiguous source span. Never join dialogue
    # across attribution, normalize punctuation, or invent a matching quote.
    fragments = []
    for match in re.finditer(r'[^\r\n]+', text):
        raw = match.group()
        stripped = raw.strip()
        if not stripped:
            continue
        start = match.start() + len(raw) - len(raw.lstrip())
        end = match.end() - (len(raw) - len(raw.rstrip()))
        fragments.append(SourceFragment(id=f'f{len(fragments)+1:06d}', start=start, end=end, text=text[start:end]))
    return fragments


def render_fragments(text: str) -> str:
    return '\n\n'.join(f'[{f.id}]\n{f.text}' for f in fragment_text(text))
