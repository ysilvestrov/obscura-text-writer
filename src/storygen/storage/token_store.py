"""Atomic token observations and explicit profile admission; no story revisions."""
import json
from ..token_budget.core import build_profile, estimate


def records(repo, kind):
    if kind not in {'observation', 'profile'}: raise ValueError('Невідомий тип token records')
    with repo.db.connection() as db:
        return [json.loads(r[0]) for r in db.execute('SELECT payload FROM app_settings WHERE key LIKE ? ORDER BY key', ('token_' + kind + ':%',))]


def _write(db, key, payload):
    db.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)', (key, json.dumps(payload, ensure_ascii=False)))


def record(repo, item):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        key = 'token_observation:' + item['identity'] + ':' + item['request_hash']
        previous = db.execute('SELECT payload FROM app_settings WHERE key=?', (key,)).fetchone()
        if previous and json.loads(previous[0])['prompt_tokens'] >= item['prompt_tokens']: return
        _write(db, key, item)
        profile_key = 'token_profile:' + item['identity']
        saved = db.execute('SELECT payload FROM app_settings WHERE key=?', (profile_key,)).fetchone()
        if saved:
            profile = json.loads(saved[0])
            result = estimate(item, profile)
            if result['method'] == 'verified_empirical_profile' and item['prompt_tokens'] > result['input_tokens']:
                profile.update(active=False, deactivated_reason='observed_underestimate')
                _write(db, profile_key, profile)


def profile_action(repo, identity, action):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM app_settings WHERE key LIKE ? ORDER BY key', ('token_observation:' + identity + ':%',))]
        candidate = build_profile(rows)
        key = 'token_profile:' + identity
        saved = db.execute('SELECT payload FROM app_settings WHERE key=?', (key,)).fetchone()
        if action == 'build': profile = candidate
        elif saved:
            profile = json.loads(saved[0])
            if action == 'activate':
                if not profile['eligible'] or profile['observation_hash'] != candidate['observation_hash']:
                    raise ValueError('Профіль не пройшов перевірку або спостереження змінилися; сформуйте новий звіт')
                probe = {'identity': identity, 'body_bytes': profile['min_bytes']}
                if estimate(probe, {**profile, 'active': True})['method'] != 'verified_empirical_profile':
                    raise ValueError('Профіль прострочений; сформуйте новий звіт')
                profile['active'] = True
            elif action == 'deactivate': profile['active'] = False
            else: raise ValueError('Невідома дія профілю')
        else: raise ValueError('Спершу сформуйте профіль')
        _write(db, key, profile)
        return profile
