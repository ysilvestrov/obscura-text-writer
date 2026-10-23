import re
from typing import Literal

from pydantic import Field

from .domain import DomainModel
from .evidence import fragment_text


class CopyEdit(DomainModel):
    fragment_id: str = Field(min_length=1)
    original: str = Field(min_length=1, max_length=160)
    replacement: str = Field(max_length=240)
    category: Literal['grammar', 'spelling', 'punctuation', 'wording']


class CopyEdits(DomainModel):
    edits: list[CopyEdit] = Field(default_factory=list, max_length=80)


class CopyEditAnchorError(ValueError):
    def __init__(self,index,count,fragment_id,reason):
        super().__init__('Редакторська правка не має однозначного дослівного оригіналу')
        self.edit_index=index
        self.edit_count=count
        self.fragment_id=fragment_id if re.fullmatch(r'f\d{6}',fragment_id) else None
        self.anchor_reason=reason


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
    for index,edit in enumerate(proposal.edits,1):
        fragment = fragments.get(edit.fragment_id)
        matches=fragment.text.count(edit.original) if fragment else 0
        if fragment is None or matches != 1:
            reason='fragment_missing' if fragment is None else 'original_missing' if matches==0 else 'original_ambiguous'
            raise CopyEditAnchorError(index,len(proposal.edits),edit.fragment_id,reason)
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


import hashlib
import json
from .dependency_models import DependencySnapshot, TargetCAS


def proposal_data(view, attempt):
    raw = attempt.context.get('copyedit_proposal')
    if attempt.stage != 'edit' or not raw or raw.get('protocol_version') not in {1,2} or attempt.state not in {'running', 'completed', 'needs_review', 'alternative'}:
        raise ValueError('Спроба не має валідованої пропозиції точкової редактури')
    scene = view.get_scene(attempt.scene_id)
    if scene.story_id != attempt.story_id:
        raise ValueError('Чужа пропозиція')
    draft = view.get_version(raw['draft_id'])
    if draft.scene_id != scene.id or draft.kind != 'draft' or not draft.complete:
        raise ValueError('Невідповідне джерело пропозиції')
    original = view.read_text(draft.id)
    if raw['protocol_version']==2:
        from .rewrite_diff import RewriteDiff
        proposal=RewriteDiff.model_validate(raw['proposal'])
    else:
        proposal = CopyEdits.model_validate(raw['proposal'])
    full_text = apply_proposal(original, proposal)
    fingerprint = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return scene, original, proposal, full_text, fingerprint


def apply_proposal(original,proposal,indices=None):
    from .rewrite_diff import RewriteDiff, apply_rewrite_diff
    if isinstance(proposal,RewriteDiff):
        return apply_rewrite_diff(original,proposal,indices)
    selected=proposal if indices is None else CopyEdits(edits=[proposal.edits[i] for i in indices])
    return apply_copyedits(original,selected)


def ensure_selectable(view, attempt, changes):
    scene, original, _, full_text, _ = proposal_data(view, attempt)
    require_editor_changes(original, full_text)
    snapshot = DependencySnapshot.model_validate(attempt.context['dependency_snapshot'])
    if changes:
        raise ValueError('Джерела пропозиції змінилися; створіть нову редакторську пропозицію')
    decisions = attempt.context.get('copyedit_decisions', [])
    if decisions:
        expected_id = decisions[-1]['result_version_id']
        expected_revision = decisions[-1]['head_revision']
    else:
        target = TargetCAS.model_validate(attempt.context['target_cas'])
        if target.scene_id != scene.id or target.head != 'prose':
            raise ValueError('Невідповідна ціль пропозиції')
        expected_id, expected_revision = target.version_id, target.head_revision
    if scene.heads.get('prose') != expected_id or scene.head_revisions.get('prose', 0) != expected_revision:
        raise ValueError('Поточна проза змінилася поза цією пропозицією; її не буде перезаписано')
    return scene


def require_editor_changes(original, candidate):
    if original == candidate:
        raise ValueError('Редактор не запропонував змін')


def validate_indices(indices, count):
    if not isinstance(indices, list) or any(type(i) is not int or i < 0 or i >= count for i in indices) or len(set(indices)) != len(indices):
        raise ValueError('Оберіть унікальні допустимі індекси правок')
    return sorted(indices)


def record_decision(attempt, scene, indices, result_id, mode, warnings):
    from .domain import now, new_id
    decision = dict(id=new_id(), created_at=now(), selected_indices=indices, result_version_id=result_id,
                    head_revision=scene.head_revisions['prose'], mode=mode, language_warnings=warnings)
    attempt.context.setdefault('copyedit_decisions', []).append(decision)
