"""One serialized transaction per budget mutation; SQL schema remains 2."""
import json
from ..billing.models import BudgetError, Tariff, utcnow
from ..domain import RevisionConflict
from ..token_budget.core import digest
from .locking import AppInstanceLock


def call_lease(repo, call_id):
    return AppInstanceLock(repo.root / "billing-locks" / digest(call_id))


def tariff_key(provider, model, base_url):
    return 'billing_tariff:' + digest([provider, model, base_url.rstrip('/')])


def read(db, key):
    row = db.execute('SELECT payload FROM app_settings WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else None


def write(db, key, value):
    db.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)', (key, json.dumps(value, ensure_ascii=False)))


def calls(db, scope):
    return [item for row in db.execute("SELECT payload FROM app_settings WHERE key LIKE 'billing_call:%' ORDER BY rowid") if (item := json.loads(row[0]))['scope'] == scope]


def exposure(item):
    return item['counted_nanos']


def last_sent_call(rows):
    sent = [(e['at'], r['call_id'], r) for r in rows for e in r['events'] if e['type'] == 'sent']
    if not sent:
        return None
    at, _, item = max(sent, key=lambda entry: (entry[0], entry[1]))
    raw=item.get('usage')
    usage={key:raw[key] for key in ('prompt_tokens','completion_tokens','total_tokens','input_tokens','output_tokens')
           if isinstance(raw,dict) and type(raw.get(key)) is int and raw[key]>=0}
    return {**{key: item.get(key) for key in ('call_id', 'provider', 'model', 'state',
            'cost_source', 'counted_nanos', 'actual_nanos', 'estimated_nanos', 'reserved_nanos')}, 'sent_at': at,'usage':usage or None}


def report(db, scope):
    policy = read(db, 'billing_policy:' + scope)
    rows = calls(db, scope)
    total = sum(exposure(r) for r in rows)
    cap = policy['limit_nanos'] if policy else None
    return {'scope': scope, 'policy': policy, 'calls': len(rows), 'last_call': last_sent_call(rows), 'exposure_nanos': total,
        'limit_nanos': cap, 'available_nanos': max(0, cap - total) if cap is not None else None,
        'actual_nanos': sum(r['counted_nanos'] for r in rows if r['cost_source'] == 'provider'),
        'estimated_nanos': sum(r['counted_nanos'] for r in rows if r['cost_source'] == 'priced_usage_estimate'),
        'reserved_nanos': sum(r['counted_nanos'] for r in rows if r['state'] in {'reserved', 'sent'}),
        'unresolved_nanos': sum(r['counted_nanos'] for r in rows if r['state'] == 'unresolved')}


def event(item, name, **details):
    item['events'].append({'type': name, 'at': utcnow().isoformat(), **details})


def operation(repo, action, **data):
    if action == 'manual':
        try:
            with call_lease(repo, data['call_id']):
                return _operation(repo, action, **data)
        except RuntimeError:
            raise BudgetError('Виклик ще активний; ручна звірка недоступна') from None
    return _operation(repo, action, **data)


def _operation(repo, action, **data):
    if action in {'unpriced','reserve','limit'}:
        scope=data['scope']
        if not isinstance(scope,str) or not scope.startswith(('story:', 'cli:')) or not scope.split(':',1)[1].strip():
            raise BudgetError('Некоректний scope; потрібен story:<id> або cli:<name>')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if action == 'summary': return report(db, data['scope'])
        if action == 'calls': return calls(db, data['scope'])
        if action == 'tariff_get': return read(db, tariff_key(data['provider'], data['model'], data['base_url']))
        if action == 'tariff_set':
            tariff = Tariff.model_validate(data['tariff'])
            if not tariff.current(): raise ValueError('Тариф прострочений або ще не чинний')
            write(db, tariff_key(tariff.provider, tariff.model, tariff.base_url), tariff.model_dump(mode='json'))
            return tariff.model_dump(mode='json')
        if action == 'limit':
            scope = data['scope']
            if not scope.startswith(('story:', 'cli:')): raise ValueError('Некоректний scope')
            if scope.startswith('story:'): repo._active_story(db, scope[6:])
            previous = read(db, 'billing_policy:' + scope)
            revision = previous['revision'] if previous else 0
            if revision != data['expected_revision']: raise RevisionConflict('Бюджет змінено; оновіть сторінку')
            if data['limit_nanos'] < report(db, scope)['exposure_nanos']: raise BudgetError('Ліміт менший за вже витрачене й зарезервоване')
            policy = {'scope': scope, 'limit_nanos': data['limit_nanos'], 'default_run_limit_nanos': data.get('default_run_limit_nanos'),
                'revision': revision + 1, 'created_at': previous['created_at'] if previous else utcnow().isoformat()}
            write(db, 'billing_policy:' + scope, policy)
            return policy
        if action == 'unpriced':
            if data['scope'].startswith('story:'): repo._active_story(db,data['scope'][6:])
            if data['provider'] not in {'local', 'codex_cli'}: raise BudgetError('Непідтримуваний unpriced provider')
            if read(db, 'billing_call:' + data['call_id']): raise BudgetError('Цей виклик уже обліковано')
            item = {**data, 'state': 'reserved', 'reserved_nanos': 0, 'counted_nanos': 0,
                'actual_nanos': None, 'estimated_nanos': None, 'cost_source': 'unpriced', 'events': []}
            event(item, 'unpriced')
            write(db, 'billing_call:' + data['call_id'], item)
            return item
        if action == 'reserve':
            if read(db, 'billing_call:' + data['call_id']): raise BudgetError('Цей call ID вже обліковано; повторного виклику немає')
            scope = data['scope']
            if scope.startswith('story:'): repo._active_story(db, scope[6:])
            policy = read(db, 'billing_policy:' + scope)
            if policy is None: raise BudgetError('Спершу задайте явний ліміт бюджету')
            raw = read(db, tariff_key(data['provider'], data['model'], data['base_url']))
            if not raw: raise BudgetError('Немає чинного тарифу; оновіть каталог або задайте ручний тариф')
            tariff = Tariff.model_validate(raw)
            if not tariff.current(): raise BudgetError('Тариф прострочений; оновіть його перед викликом')
            amount = tariff.price(data['input_tokens'], data['output_tokens'])
            rows = calls(db, scope)
            if sum(exposure(r) for r in rows) + amount > policy['limit_nanos']: raise BudgetError('Недостатньо бюджету оповідання для резерву виклику')
            run_key = 'billing_run:' + digest([scope, data['run_id']])
            run = read(db, run_key)
            if run is None:
                run = {'limit_nanos': data.get('run_limit_nanos') if data.get('run_limit_nanos') is not None else policy.get('default_run_limit_nanos')}
                write(db, run_key, run)
            cap = run['limit_nanos']
            if cap is not None and sum(exposure(r) for r in rows if r['run_id'] == data['run_id']) + amount > cap:
                raise BudgetError('Недостатньо бюджету окремого запуску для резерву')
            item = {**data, 'state': 'reserved', 'reserved_nanos': amount, 'counted_nanos': amount,
                'actual_nanos': None, 'estimated_nanos': None, 'cost_source': None,
                'tariff': tariff.model_dump(mode='json'), 'events': []}
            event(item, 'reserved', amount_nanos=amount)
            write(db, 'billing_call:' + data['call_id'], item)
            return item
        item = read(db, 'billing_call:' + data['call_id'])
        if item is None: raise BudgetError('Запис виклику не знайдено')
        if action == 'sent':
            if item['state'] != 'reserved': raise BudgetError('Виклик уже відправлено або завершено')
            item['state'] = 'sent'; event(item, 'sent')
        elif action == 'settle':
            if item['state'] in {'settled', 'released'}: return item
            if item['state'] not in {'sent', 'unresolved'}: raise BudgetError('Виклик не відправлено')
            amount = data.get('reported_nanos')
            usage = data.get('usage', {})
            source = 'provider' if amount is not None else None
            if item['cost_source'] == 'unpriced':
                item.update(state='settled' if data.get('complete') else 'unresolved', usage=usage)
                event(item, item['state'])
                write(db, 'billing_call:' + item['call_id'], item)
                return item
            if amount is None and data.get('complete') and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ('prompt_tokens', 'completion_tokens')):
                amount = Tariff.model_validate(item['tariff']).price(usage['prompt_tokens'], usage['completion_tokens'])
                source = 'priced_usage_estimate'
            item.update(usage=usage, reported_diem=data.get('reported_diem'), response_id=data.get('response_id'))
            if amount is None:
                item['state'] = 'unresolved'; event(item, 'unresolved')
            else:
                item.update(state='settled', counted_nanos=amount, cost_source=source,
                    actual_nanos=amount if source == 'provider' else None, estimated_nanos=amount if source != 'provider' else None)
                event(item, 'settled', source=source, amount_nanos=amount)
        elif action == 'manual':
            if item['scope'] != data['scope']: raise BudgetError('Виклик належить іншому scope')
            active=db.execute('SELECT state FROM runs WHERE id=?',(item['run_id'],)).fetchone()
            if active and active[0] in {'queued','running','pause_requested','cancellation_requested'}:
                raise BudgetError('Запуск ще активний; дочекайтеся завершення перед ручною звіркою')
            if item['state'] not in {'reserved', 'sent', 'unresolved'}: raise BudgetError('Виклик уже звірено')
            if not data['source'].strip(): raise ValueError('Потрібне джерело звірки')
            item.update(state='settled', counted_nanos=data['amount_nanos'], actual_nanos=data['amount_nanos'], cost_source='provider')
            event(item, 'manual_reconcile', source=data['source'], amount_nanos=data['amount_nanos'])
        elif action == 'release':
            if item['state'] != 'reserved': raise BudgetError('Після відправлення резерв не звільняється без звірки')
            item.update(state='released', counted_nanos=0); event(item, 'released')
        else: raise ValueError('Невідома бюджетна операція')
        write(db, 'billing_call:' + item['call_id'], item)
        return item
