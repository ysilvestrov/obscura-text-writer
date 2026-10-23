"""Pure token-budget rules. Empirical admission is not a tokenizer guarantee."""
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def endpoint_identity(url):
    parts = urlsplit(url)
    host = parts.hostname or ''
    if host in {'localhost', '127.0.0.1', '::1'}:
        host = 'loopback'
    return urlunsplit((parts.scheme.lower(), host + (':' + str(parts.port) if parts.port else ''), parts.path.rstrip('/'), '', ''))


def content_class(request):
    text = '\n'.join(m.get('content', '') for m in request.get('messages', []) if m.get('role') == 'user')
    try:
        json.loads(text)
        return 'json'
    except (ValueError, TypeError):
        letters = [c for c in text if c.isalpha()]
        count = sum('\u0400' <= c <= '\u052f' for c in letters)
        return 'cyrillic' if letters and count / len(letters) >= 0.2 else 'ascii'


def measure(provider, base_url, request, tokenizer_revision='unknown'):
    shape = {'provider': provider, 'endpoint': endpoint_identity(base_url), 'model': request.get('model'),
        'tokenizer_revision': tokenizer_revision, 'messages': [{k: v for k, v in m.items() if k != 'content'} for m in request.get('messages', [])],
        'system_prompt_hash': digest([m.get('content', '') for m in request.get('messages', []) if m.get('role') in {'system', 'developer'}]),
        'response_format': request.get('response_format'), 'provider_options': {k: request[k] for k in ('venice_parameters', 'provider') if k in request}}
    return {'identity': digest(shape), 'identity_details': shape, 'request_hash': digest(request),
        'body_bytes': len(canonical(request).encode('utf-8')), 'content_class': content_class(request)}


def estimate(item, profile=None, *, now=None):
    fallback = {'input_tokens': item['body_bytes'] + 256, 'method': 'utf8_body_conservative',
        'confidence': 'heuristic', 'profile_id': None, 'reasons': []}
    if not profile:
        fallback['reasons'] = ['no_active_profile']
        return fallback
    reasons = []
    if not profile.get('eligible') or not profile.get('active'):
        reasons.append('profile_not_active')
    if profile.get('identity') != item['identity']:
        reasons.append('identity_mismatch')
    if not profile.get('min_bytes', 0) <= item['body_bytes'] <= profile.get('max_bytes', 0):
        reasons.append('outside_verified_range')
    now = now or datetime.now(timezone.utc)
    try:
        if (now - datetime.fromisoformat(profile['created_at'])).total_seconds() > 7 * 86400:
            reasons.append('profile_expired')
    except (KeyError, ValueError, TypeError):
        reasons.append('invalid_profile_date')
    if reasons:
        fallback['reasons'] = reasons
        return fallback
    return {'input_tokens': math.ceil(item['body_bytes'] * profile['coefficient'] * 1.20) + 256,
        'method': 'verified_empirical_profile', 'confidence': 'empirical_holdout', 'profile_id': profile['id'], 'reasons': []}


def valid_observation(row):
    return type(row.get('prompt_tokens')) is int and row['prompt_tokens'] > 0 and type(row.get('body_bytes')) is int and row['body_bytes'] > 0


def build_profile(observations):
    unique = {}
    for row in observations:
        if valid_observation(row):
            key = row['request_hash']
            if key not in unique or row['prompt_tokens'] > unique[key]['prompt_tokens']:
                unique[key] = row
    rows = sorted(unique.values(), key=lambda r: r['request_hash'])
    reasons = []
    identities = {r['identity'] for r in rows}
    if len(identities) != 1:
        reasons.append('mixed_or_missing_identity')
    if len(rows) < 40:
        reasons.append('insufficient_samples')
    train, holdout = rows[:-10], rows[-10:]
    sizes = [r['body_bytes'] for r in rows]
    if not sizes or max(sizes) < 4 * min(sizes):
        reasons.append('insufficient_size_range')
    classes = Counter(r['content_class'] for r in rows)
    if any(classes[k] < 5 or not any(r['content_class'] == k for r in train) or not any(r['content_class'] == k for r in holdout) for k in ('ascii', 'cyrillic', 'json')):
        reasons.append('insufficient_content_coverage')
    coefficient = max((r['prompt_tokens'] / r['body_bytes'] for r in train), default=0)
    surpluses = [math.ceil(r['body_bytes'] * coefficient * 1.20) + 256 - r['prompt_tokens'] for r in holdout]
    under = sum(value < 0 for value in surpluses)
    if under:
        reasons.append('holdout_underestimate')
    return {'id': digest(rows), 'identity': next(iter(identities)) if len(identities) == 1 else None,
        'eligible': not reasons, 'active': False, 'created_at': datetime.now(timezone.utc).isoformat(), 'reasons': reasons,
        'coefficient': coefficient, 'min_bytes': min(sizes, default=0), 'max_bytes': max(sizes, default=0),
        'distinct_samples': len(rows), 'train_samples': len(train), 'holdout_samples': len(holdout),
        'holdout_underestimates': under, 'holdout_min_surplus_tokens': min(surpluses, default=None),
        'holdout_max_surplus_tokens': max(surpluses, default=None),
        'margin_multiplier': 1.20, 'margin_add_tokens': 256,
        'content_classes': dict(classes), 'observation_hash': digest(rows)}
