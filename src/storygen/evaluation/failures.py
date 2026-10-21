"""Classify evaluator replies and safe provider diagnostics, never author text."""

import re

from openai import APIConnectionError, APITimeoutError

from .models import FailureDetail


def refusal_detail(text: str, *, content_filter: bool = False) -> FailureDetail:
    content = content_filter or bool(re.search(r'content policy|safety policy|nudity|sexual|оголен|через контент|ерот|сексуал|насильств', text, re.I))
    return FailureDetail(category='refusal_content' if content else 'refusal_unknown',
        message='Оцінювач відмовився через контент.' if content else 'Оцінювач відмовився; причина не встановлена.',
        provider_message=safe_message(text))


def safe_message(value, secret=None, documents=(), *, secrets=()):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value
    # Redact whole credentials before either length limit can split them.
    for credential in (secret,*secrets):
        if isinstance(credential,str) and credential:
            text = text.replace(credential, '[ключ приховано]')
    text = re.sub(r'(?i)\bBearer\s+[^\s,;]+', 'Bearer [приховано]', text)
    text = re.sub(r'\bsk-[A-Za-z0-9_-]+', '[ключ приховано]', text)
    text = text[:2000]
    # Error bodies sometimes echo input. Do not expose them as diagnostics.
    for document in documents:
        if (document.strip() and document in text) or any(text[i:i+24] in document for i in range(max(0, len(text)-23))):
            return 'Пояснення провайдера містить відлуння запиту; текст приховано.'
    return ' '.join(text.split())[:500]


def is_text_refusal(text: str) -> bool:
    # Only called after JSON parsing fails; phrases in documents/reports do not count.
    text = re.sub(r"^\s*(?:I'm sorry|I am sorry|Sorry)[,.!]?\s*(?:but\s+)?", '', text, flags=re.I)
    return bool(re.match(r"\s*(?:I (?:cannot|can't|am unable to) (?:evaluate|assess|review|process|assist)|(?:Вибачте[,.]?\s*)?(?:Я )?не можу (?:оцінити|оцінювати|обробити|допомогти))\b", text, re.I))


def safe_id(value, secret=None):
    if not isinstance(value, str) or (secret and secret in value):
        return None
    return value if re.fullmatch(r'[\w.:/\-]{1,120}', value, flags=re.ASCII) else None


def api_failure(exc, secret=None, documents=()) -> FailureDetail:
    body = getattr(exc, 'body', None)
    error = body.get('error', body) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    code = safe_id(error.get('code'), secret)
    kind = safe_id(error.get('type'), secret)
    status = getattr(exc, 'status_code', None)
    identities = {code, kind}
    if identities & {'content_filter', 'content_policy_violation', 'moderation_blocked'}:
        category, message = 'refusal_content', 'Провайдер відмовив через контент.'
    elif isinstance(exc, APITimeoutError):
        category, message = 'timeout', 'Перевищено час очікування відповіді оцінювача.'
    elif isinstance(exc, APIConnectionError):
        category, message = 'connection', 'Не вдалося встановити з’єднання з оцінювачем.'
    elif identities & {'insufficient_quota', 'quota_exceeded', 'insufficient_balance', 'billing_hard_limit_reached'} or status == 402:
        category, message = 'quota', 'Вичерпано квоту або баланс провайдера.'
    elif status == 401 or identities & {'invalid_api_key', 'authentication_error'}:
        category, message = 'authentication', 'Провайдер не прийняв API-ключ.'
    elif status == 403:
        category, message = 'permission', 'Провайдер заборонив доступ; це не підтверджена контентна відмова.'
    elif status == 429 or identities & {'rate_limit_exceeded', 'rate_limit_error'}:
        category, message = 'rate_limit', 'Перевищено ліміт частоти запитів провайдера.'
    else:
        category, message = 'provider_error', 'Провайдер не повідомив точну причину; перегляньте доступні коди.'
    provider_message = safe_message(error.get('message'), secret, documents)
    if category == 'provider_error' and provider_message:
        message = provider_message
    return FailureDetail(category=category, message=message, http_status=status, provider_code=code,
        provider_type=kind, provider_message=provider_message, request_id=safe_id(getattr(exc, 'request_id', None), secret))
