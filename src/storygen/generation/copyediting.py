import re
from typing import Literal

from pydantic import Field

from ..domain import DomainModel
from .evidence import fragment_text


class CopyEdit(DomainModel):
    fragment_id: str = Field(min_length=1)
    original: str = Field(min_length=1, max_length=160)
    replacement: str = Field(max_length=240)
    category: Literal['grammar', 'spelling', 'punctuation', 'wording']


class CopyEdits(DomainModel):
    edits: list[CopyEdit] = Field(default_factory=list, max_length=80)


def protected_numbers(text: str) -> list[str]:
    # A conservative lexical guard, not a semantic proof. It intentionally
    # rejects number reformatting as well as number changes in this mode.
    words = r'нуль|один|одна|одне|одну|одного|два|дві|двох|три|трьох|чотири|п’ять|п\x27ять|шість|сім|вісім|дев’ять|дев\x27ять|десять|двадцять|тридцять|сорок|сорока|п’ятдесят|сто|перший|перша|перше|другий|друга|друге|третій|третя|третє'
    return re.findall(r'\d+(?:[.,:/-]\d+)*|\b(?:' + words + r')\b', text.casefold())


def protected_negations(text: str) -> list[str]:
    return re.findall(r'\b(?:не|ні|ніколи|ніхто|ніщо|нікому|нічого)\b', text.casefold())


def apply_copyedits(text: str, proposal: CopyEdits) -> str:
    fragments = {f.id: f for f in fragment_text(text)}
    patches = []
    for edit in proposal.edits:
        fragment = fragments.get(edit.fragment_id)
        if fragment is None or fragment.text.count(edit.original) != 1:
            raise ValueError('Редакторська правка не має однозначного дослівного оригіналу')
        if '\n' in edit.replacement or '\r' in edit.replacement:
            raise ValueError('Точкова правка не може додавати абзаци')
        if protected_numbers(edit.original) != protected_numbers(edit.replacement):
            raise ValueError('Точкова редактура змінила числовий факт')
        if protected_negations(edit.original) != protected_negations(edit.replacement):
            raise ValueError('Точкова редактура змінила заперечення')
        if len(edit.replacement) > max(24, len(edit.original) * 3):
            raise ValueError('Точкова правка розширюється до переписування')
        if edit.original == edit.replacement:
            continue
        start = fragment.start + fragment.text.index(edit.original)
        patches.append((start, start + len(edit.original), edit.replacement))
    patches.sort()
    if any(right[0] < left[1] for left, right in zip(patches, patches[1:])):
        raise ValueError('Редакторські правки перетинаються')
    changed = sum(max(end - start, len(replacement)) for start, end, replacement in patches)
    if changed > len(text) * .35:
        raise ValueError('Правки охоплюють понад 35% тексту; потрібна окрема редакторська версія')
    result = text
    for start, end, replacement in reversed(patches):
        result = result[:start] + replacement + result[end:]
    if not result.strip():
        raise ValueError('Редактура не може вилучити всю сцену')
    if protected_numbers(text) != protected_numbers(result) or protected_negations(text) != protected_negations(result):
        raise ValueError('Сукупність правок змінила числовий факт або заперечення')
    return result
