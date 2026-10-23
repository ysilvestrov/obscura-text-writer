"""Read-only ledger validation; expired historical tariffs are not corruption."""
import json
from ..billing.models import Tariff


def check_billing(report, db, stories):
    for key,raw in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'billing_%' ORDER BY key"):
        try:
            item=json.loads(raw)
            if key.startswith('billing_call:'):
                assert key=='billing_call:'+item['call_id']
                assert item['state'] in {'reserved','sent','settled','released','unresolved'}
                assert item['scope'].startswith(('story:','cli:'))
                if item['scope'].startswith('story:'):assert item['scope'][6:] in stories
                for field in ('reserved_nanos','counted_nanos'):
                    assert type(item[field]) is int and item[field]>=0
                assert item['events'] and all('type' in e and 'at' in e for e in item['events'])
                if item['provider'] in {'venice','openrouter'}:
                    tariff=Tariff.model_validate(item['tariff'])
                    assert tariff.provider==item['provider'] and tariff.model==item['model']
                else:assert item['cost_source']=='unpriced'
                if item.get('attempt_id'):
                    row=db.execute('SELECT story_id,run_id FROM stage_attempts WHERE id=?',(item['attempt_id'],)).fetchone()
                    assert row and item['scope']=='story:'+row[0]
                    assert row[1] is None or row[1]==item['run_id']
            elif key.startswith('billing_policy:'):
                assert key=='billing_policy:'+item['scope']
                assert type(item['limit_nanos']) is int and item['limit_nanos']>=0
                assert type(item['revision']) is int and item['revision']>0
            elif key.startswith('billing_tariff:'):Tariff.model_validate(item)
            elif key.startswith('billing_run:'):
                assert item['limit_nanos'] is None or type(item['limit_nanos']) is int and item['limit_nanos']>=0
        except (ValueError,TypeError,KeyError,AssertionError):
            report.add('invalid_billing',key,'Пошкоджений формат або власність бюджетного запису')
