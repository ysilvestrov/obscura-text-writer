from .models import money, Tariff


def set_limit(repo, scope, limit_usd, expected_revision, default_run_limit_usd=None):
    return repo.billing('limit', scope=scope, limit_nanos=money(limit_usd), expected_revision=expected_revision,
        default_run_limit_nanos=money(default_run_limit_usd) if default_run_limit_usd is not None else None)


def summary(repo, scope): return repo.billing('summary', scope=scope)


def reserve(repo, **values): return repo.billing('reserve', **values)


def mark_sent(repo, call_id): return repo.billing('sent', call_id=call_id)


def save_tariff(repo, tariff): return repo.billing('tariff_set', tariff=tariff.model_dump(mode='json'))


def settle(repo, call_id, usage, complete, reported_usd=None, reported_diem=None, response_id=None):
    # USD=0 with positive DiEM is not a zero tariff-equivalent inference.
    reported = money(reported_usd) if reported_usd is not None else None
    if reported == 0 and reported_diem is not None and money(reported_diem) > 0: reported = None
    return repo.billing('settle', call_id=call_id, usage=usage, complete=complete, reported_nanos=reported,
        reported_diem=reported_diem, response_id=response_id)
