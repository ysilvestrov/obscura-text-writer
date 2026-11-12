"""One memory-role call that summarises the timeline of a block (#68, MEMORY-SUMMARY-S05).

The input is the timeline entries of the block's scenes in the selected memory of its last scene, never prose. The call
runs only on the author's request; the result is a `timeline_summary` version published with CAS on the story revision."""
import hashlib
import json
import re

from ..domain import RevisionConflict
from ..memory.summary_blocks import limit, summary_blocks
from .context import ContextBundle, ContextOverflow

LANGUAGE_MISMATCH = {'uk': 'Підсумок написано не українською', 'en': 'Підсумок написано не англійською'}


def _block(story, scenes, block_key):
    block = next((b for b in summary_blocks(story, scenes) if b.key == block_key), None)
    if block is None:
        raise ValueError('Такого блоку немає або він ще неповний')
    return block


def block_inputs(view, story, scenes, block):
    """Memory version of every scene of the block; ValueError names the first scene without fresh memory."""
    by_id = {s.id: s for s in scenes}
    memory_ids = []
    for number, scene_id in enumerate(block.scene_ids, block.first_number):
        scene = by_id[scene_id]
        memory_id = scene.heads.get('memory')
        if not memory_id:
            raise ValueError(f'Сцена {number} «{scene.title}» ще не має пам’яті')
        if view.get_version(memory_id).stale:
            raise ValueError(f'Пам’ять сцени {number} «{scene.title}» застаріла; оновіть її')
        memory_ids.append(memory_id)
    return memory_ids


def _timeline(view, scenes, block, memory_id, language):
    from ..memory.journal import load_memory
    from ..memory.projection import _timeline_events
    from .context_labels import label
    journal = load_memory(view.read_text(memory_id))
    numbers = {s.id: n for n, s in enumerate(sorted(scenes, key=lambda s: s.position), 1)}
    def scene_number(version_id):
        try:
            return numbers.get(view.get_version(version_id).scene_id)
        except KeyError:  # the prose of a scene in the trash: not part of any block
            return None
    source = {id: scene_number(id) for id in journal.source_prose_ids}
    lines = []
    for event in _timeline_events(journal):
        number = source.get(event.source_version_id)
        if number is not None and block.first_number <= number <= block.last_number:
            lines.append(label('memory_scene_prefix', language, number=number) + event.text)
    return lines


def build_summary_context(repo, story_id: str, block_key: str) -> ContextBundle:
    from ..authoring.blueprints import get_role_settings
    from ..language import load_prompt
    from ..providers.requests import generation_request
    from ..rating.guard import enforce_edition_limit
    from ..token_budget.service import token_estimate
    view = repo.context_view(story_id)
    story = view.get_story(story_id)
    scenes = view.list_scenes(story_id)
    block = _block(story, scenes, block_key)
    by_id = {s.id: s for s in scenes}
    enforce_edition_limit(story)
    for scene_id in block.scene_ids:
        enforce_edition_limit(story, by_id[scene_id])
    memory_ids = block_inputs(view, story, scenes, block)
    role = get_role_settings(repo, story_id).get('memory')
    if not role or not role.provider.model.strip():
        raise ValueError('Налаштуйте модель ролі «Пам’ять»')
    language = story.language
    system = load_prompt('timeline_summary_v1', language)
    user = json.dumps({'story_title': story.title, 'part_title': block.title if block.part else None,
                       'scenes': [{'number': n, 'title': by_id[i].title} for n, i in enumerate(block.scene_ids, block.first_number)],
                       'timeline': _timeline(view, scenes, block, memory_ids[-1], language), 'max_chars': limit(block)},
                      ensure_ascii=False)
    body = generation_request('timeline_summary', role, system, user, {})
    prediction = token_estimate(repo, role.provider.provider, role.provider.base_url, body)
    chars = len(json.dumps(body, ensure_ascii=False, separators=(',', ':')))
    budget = role.context_tokens - role.max_output_tokens
    if prediction['input_tokens'] > budget or chars > role.max_input_chars:
        raise ContextOverflow(prediction['input_tokens'], budget, chars, max_input_chars=role.max_input_chars)
    fingerprint = hashlib.sha256(json.dumps({'request': body, 'block': block_key, 'memory': memory_ids}, ensure_ascii=False,
                                            sort_keys=True).encode()).hexdigest()
    return ContextBundle(story_id=story_id, scene_id=None, stage='timeline_summary', scene_revision=None, story_revision=story.revision,
                         settings=role, system_text=system, user_text=user, input_refs=memory_ids, fingerprint=fingerprint,
                         estimated_tokens=prediction['input_tokens'], estimate_method=prediction['method'], api_request=body,
                         token_estimate=prediction,
                         fragments={'summary_block_key': block_key, 'summary_scene_ids': json.dumps(list(block.scene_ids)),
                                    'summary_limit': str(limit(block)), 'summary_language': language,
                                    'summary_part': 'true' if block.part else 'false'})


def validate_summary(text: str, max_chars: int, language: str) -> str:
    from ..storage.timeline_summaries import check_text
    text = check_text(text, max_chars)
    cyrillic = len(re.findall('[а-яА-ЯіІїЇєЄґҐ]', text))
    latin = len(re.findall('[a-zA-Z]', text))
    if (language == 'en' and cyrillic >= latin) or (language != 'en' and latin >= cyrillic):
        raise ValueError(LANGUAGE_MISMATCH['en' if language == 'en' else 'uk'])
    return text


def finish_summary(repo, attempt, context, text: str, run_id: str | None):
    """Validate, save a model version and publish it; a revision conflict leaves the version unpublished."""
    from ..memory.summary_blocks import SummaryBlock
    from ..storage.timeline_summaries import publish_summary, save_summary_version
    fragments = context.fragments
    text = validate_summary(text, int(fragments['summary_limit']), fragments['summary_language'])
    key = fragments['summary_block_key']
    block = SummaryBlock(key, '', tuple(json.loads(fragments['summary_scene_ids'])), 0, 0, fragments['summary_part'] == 'true')
    ref = save_summary_version(repo, context.story_id, block, list(context.input_refs), text, 'model', fragments['summary_language'], run_id=run_id)
    attempt.result_version_id = ref.id
    try:
        publish_summary(repo, context.story_id, key, ref.id, context.story_revision)
        attempt.state = 'completed'
    except RevisionConflict:
        attempt.state = 'alternative'
        attempt.error = 'Твір змінився під час виклику; підсумок збережено, але не опубліковано. Перебудуйте його.'
    return repo.save_attempt(attempt)


def readiness(repo, request) -> dict:
    result = {'ready': False, 'reason': None, 'roles': {}, 'calls': 0, 'evaluator': None, 'warnings': []}
    try:
        context = build_summary_context(repo, request.story_id, request.summary_block_key)
        result['roles'] = {'memory': context.settings.provider.model_dump(include={'provider', 'model'})}
        if context.settings.provider.provider in {'venice', 'openrouter'} and repo.billing('summary', scope='story:' + request.story_id)['limit_nanos'] is None:
            raise ValueError('Спершу задайте явний ліміт бюджету оповідання')
        result.update(ready=True, calls=1, estimated_tokens=context.estimated_tokens,
                      input_budget=context.settings.context_tokens - context.settings.max_output_tokens)
    except (ValueError, KeyError) as exc:
        result['reason'] = str(exc) if isinstance(exc, ValueError) else 'Матеріал не знайдено'
    return result
