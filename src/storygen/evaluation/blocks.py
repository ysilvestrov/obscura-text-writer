"""Persistent, story-scoped refusal circuit breaker; not a content filter."""

from ..domain import now


from ..evaluation_identity import evaluator_identity, block_key


def get_block(repo, story_id, config):
    return repo.read_refusal_block(story_id, block_key(story_id, config).rsplit(':', 1)[1])


def block_evaluator(repo, story_id, config, failure, run_id, attempt_id):
    if not failure.category.startswith('refusal_'):
        raise ValueError('Технічна помилка не блокує оцінювача')
    payload = {'story_id': story_id, 'identity': evaluator_identity(config), 'failure': failure.model_dump(),
               'created_at': now(), 'run_id': run_id, 'attempt_id': attempt_id}
    return repo.record_refusal_block(story_id, block_key(story_id, config).rsplit(':', 1)[1], payload)


def blocked_message(block):
    return 'Оцінювач заблоковано для цього оповідання після відмови. ' + block['failure']['message']


def require_available(repo, story_id, config):
    block = get_block(repo, story_id, config)
    if block:
        raise ValueError(blocked_message(block))
