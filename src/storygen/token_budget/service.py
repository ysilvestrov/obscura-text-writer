"""Runtime facade; text stays in the attempt, observations retain only metadata."""
from .core import measure, estimate, valid_observation


def token_estimate(repo, provider, base_url, request):
    item = measure(provider, base_url, request)
    profiles = repo.token_records('profile') if repo is not None and provider != 'codex_cli' else []
    profile = next((p for p in profiles if p['identity'] == item['identity']), None)
    prediction = estimate(item, profile)
    if provider == 'codex_cli':
        prediction.update(method='cli_envelope_conservative',reasons=['cli_tokenizer_unknown'])
    return {**prediction, 'request_hash': item['request_hash'], 'body_bytes': item['body_bytes'], 'identity': item['identity']}


def record_usage(repo, provider, base_url, request, usage, source_id):
    if provider == 'codex_cli': return None
    item = {**measure(provider, base_url, request), 'prompt_tokens': usage.get('prompt_tokens'), 'source_id': source_id}
    if not valid_observation(item): return None
    repo.record_token_observation(item)
    return item


def build(repo, identity):
    return repo.token_profile_action(identity, 'build')


def activate(repo, identity):
    return repo.token_profile_action(identity, 'activate')
