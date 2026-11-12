"""Consent and refusal records per role, endpoint and exact model in app_settings; SQL schema remains 2."""
from datetime import datetime, timezone
from ..providers.policy import normalize_endpoint
from .billing_store import read, write


def _key(kind, role, base_url, model):
    return f'model_{kind}:{role}:{normalize_endpoint(base_url)}:{model}'


def _add_refusal(db, key, entry):
    stored = read(db, key) or {'refusals': []}
    vector = entry['rating']
    refusals = stored['refusals']
    if any(all(a <= b for a, b in zip(old['rating'], vector)) for old in refusals):
        return stored
    stored['refusals'] = [old for old in refusals if not all(a >= b for a, b in zip(old['rating'], vector))] + [entry]
    write(db, key, stored)
    return stored


def operation(repo, action, *, role, provider, base_url, model, entry=None):
    kind = action.split('_', 1)[1] if '_' in action else ''
    if action not in {'get_consent', 'set_consent', 'delete_consent', 'get_refusal', 'add_refusal', 'delete_refusal'}:
        raise ValueError('Невідома дія політики моделі')
    key = _key(kind, role, base_url, model)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if action.startswith('get_'):
            return read(db, key)
        if action == 'set_consent':
            value = {'role': role, 'provider': provider, 'base_url': normalize_endpoint(base_url), 'model': model,
                'consented_at': datetime.now(timezone.utc).isoformat()}
            write(db, key, value)
            return value
        if action == 'add_refusal':
            return _add_refusal(db, key, entry)
        db.execute('DELETE FROM app_settings WHERE key=?', (key,))
        return None
