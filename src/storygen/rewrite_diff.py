"""Versioned positional proposals built by the application, never by an LLM."""
import difflib
import re
from typing import Literal

from pydantic import Field
from .domain import DomainModel

MAX_CHARS = 80000
MAX_TOKENS = 12000
MAX_EDITS = 400


class DiffEdit(DomainModel):
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=0, strict=True)
    original: str
    replacement: str


class RewriteDiff(DomainModel):
    algorithm_version: Literal[1] = 1
    candidate_text: str = Field(min_length=1, max_length=MAX_CHARS)
    edits: list[DiffEdit] = Field(max_length=MAX_EDITS)


def _tokens(text):
    if len(text) > MAX_CHARS:
        raise ValueError('Редактура з diff: текст перевищує 80000 символів; текст не обрізано')
    spans = list(re.finditer(r"\w+(?:[’']\w+)*|\s+|[^\w\s]", text))
    if len(spans) > MAX_TOKENS:
        raise ValueError('Редактура з diff: перевищено 12000 одиниць порівняння; текст не обрізано')
    return spans


def build_rewrite_diff(original: str, candidate: str) -> RewriteDiff:
    if not original.strip() or not candidate.strip():
        raise ValueError('Редактура з diff не може вилучити всю сцену')
    a, b = _tokens(original), _tokens(candidate)
    edits = []
    for tag, i, j, k, l in difflib.SequenceMatcher(None, [x.group() for x in a], [x.group() for x in b], autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        start = a[i].start() if i < len(a) else len(original)
        end = a[j-1].end() if j > i else start
        replacement = ''.join(x.group() for x in b[k:l])
        gap = original[edits[-1].end:start] if edits else ''
        if (edits and start-edits[-1].end <= 24 and end-edits[-1].start <= 240
                and not re.search(r'[\r\n.!?…]', original[edits[-1].start:end])):
            previous = edits.pop()
            edits.append(DiffEdit(start=previous.start, end=end,
                original=original[previous.start:end], replacement=previous.replacement+gap+replacement))
        else:
            edits.append(DiffEdit(start=start, end=end, original=original[start:end], replacement=replacement))
        if len(edits) > MAX_EDITS:
            raise ValueError('Редактура з diff: понад 400 змін; потрібен менший фрагмент, текст не обрізано')
    proposal = RewriteDiff(candidate_text=candidate, edits=edits)
    apply_rewrite_diff(original, proposal)
    return proposal


def apply_rewrite_diff(original: str, proposal: RewriteDiff, indices=None) -> str:
    if len(original) > MAX_CHARS or not proposal.candidate_text.strip():
        raise ValueError('Непридатний текст редактури з diff')
    previous_end, previous_span = 0, None
    for edit in proposal.edits:
        span = (edit.start, edit.end)
        if (edit.end < edit.start or edit.end > len(original) or edit.start < previous_end
                or span == previous_span or original[edit.start:edit.end] != edit.original
                or edit.original == edit.replacement):
            raise ValueError('Пошкоджені позиції або джерело редакторської зміни')
        previous_end, previous_span = edit.end, span
    def assemble(chosen):
        result = original
        for i in sorted(chosen, reverse=True):
            edit = proposal.edits[i]
            result = result[:edit.start]+edit.replacement+result[edit.end:]
        return result
    if assemble(range(len(proposal.edits))) != proposal.candidate_text:
        raise ValueError('Зміни diff не відтворюють збережений кандидат')
    selected = list(range(len(proposal.edits))) if indices is None else indices
    if (not isinstance(selected, list) or any(type(i) is not int or i < 0 or i >= len(proposal.edits) for i in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError('Оберіть унікальні допустимі індекси правок')
    result = assemble(selected)
    if len(result)>MAX_CHARS:
        raise ValueError('Вибраний текст перевищує 80000 символів; текст не обрізано')
    if not result.strip():
        raise ValueError('Редактура не може вилучити всю сцену')
    return result


def rewrite_warnings(original, candidate, edits=()):
    from .copyediting import protected_numbers, protected_negations
    warnings = ['Зміни прози можуть змінювати зміст; перевірте кожну вибрану правку.']
    if protected_numbers(original) != protected_numbers(candidate):
        warnings.append('Редактура змінює числові факти.')
    if protected_negations(original) != protected_negations(candidate):
        warnings.append('Редактура змінює заперечення.')
    if original.count('\n') != candidate.count('\n'):
        warnings.append('Редактура змінює переноси рядків або абзаци.')
    if len(candidate) > len(original)*1.35 or len(candidate) < len(original)*.65:
        warnings.append('Обсяг редактури істотно відрізняється від чернетки.')
    if sum(max(len(e.original),len(e.replacement)) for e in edits)>len(original)*.35:
        warnings.append('Правки охоплюють понад 35% чернетки; уважно перевірте збереження змісту.')
    return warnings
