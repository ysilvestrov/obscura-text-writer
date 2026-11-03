"""Round-two only: shared $10 ledger and targeted escalation; no product settings."""
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from .runner import digest


LIMIT=Decimal('10.00')
RATES={
    'gemini-3.5-flash-lite':('0.30','2.50'),
    'gemini-4-argon':('2','10'),
    'claude-haiku-5-5':('0.10','0.50'),
    'claude-opus-5-5':('4','20'),
}


def _money(value):
    amount=Decimal(str(value))
    if not amount.is_finite() or amount<0:raise ValueError('Invalid money')
    return amount


def _connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=30,isolation_level=None)
    db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('limit_usd',str(LIMIT)))
    if db.execute('SELECT value FROM metadata WHERE key=?',('limit_usd',)).fetchone()!= (str(LIMIT),):
        db.close();raise ValueError('Research budget limit changed; review ledger')
    db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, identity TEXT NOT NULL, reserve TEXT NOT NULL, '
               'charged TEXT, result TEXT)')
    return db


def _balance(db):
    return LIMIT-sum((_money(charged if charged is not None else reserve)
                      for reserve,charged in db.execute('SELECT reserve,charged FROM calls')),Decimal(0))


def balance(path):
    db=_connect(path)
    try:return _balance(db)
    finally:db.close()


def paid_call(path,call_id,identity,reserve,send,calculate_cost):
    """Reserve durably before HTTP. One attempt per ID; no uncertain replay.

    Missing/bad usage and errors hold the full reserve. Result is cached before
    returning, so a process crash cannot cause a paid replay. A provider charge
    above its reserve is recorded in full and blocks further calls if exhausted.
    Costs are tariff calculations, not a provider billing receipt. Never include
    credentials or private manuscript data in identity/result.
    """
    reserve=_money(reserve)
    if reserve<=0:raise ValueError('Positive budget reservation required')
    stamp=digest(identity);db=_connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT identity,result FROM calls WHERE id=?',(call_id,)).fetchone()
        if row:
            db.commit()
            if row[0]!=stamp:raise ValueError('Paid call identity mismatch')
            if row[1] is None:raise ValueError('Paid call uncertain; reconcile before retry')
            return json.loads(row[1])
        if any(_money(charged)>_money(held) for held,charged in db.execute('SELECT reserve,charged FROM calls') if charged is not None):
            raise ValueError('Provider exceeded reserve; review before further dispatch')
        if _balance(db)<reserve:raise ValueError('Insufficient shared research budget')
        db.execute('INSERT INTO calls(id,identity,reserve) VALUES (?,?,?)',(call_id,stamp,str(reserve)))
        db.commit()
        result=send()  # Any exception leaves a durable uncertain reservation.
        cost=calculate_cost(result)
        charged=None if cost is None else str(_money(cost))
        encoded=json.dumps(result,ensure_ascii=False,allow_nan=False)
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE calls SET charged=?,result=? WHERE id=?',(charged,encoded,call_id))
        db.commit()
        return result
    finally:
        db.close()


def settle_saved(path,call_id,calculate_cost):
    """Explicit recalculation from an already saved reply, never sends HTTP."""
    db=_connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT result FROM calls WHERE id=?',(call_id,)).fetchone()
        if not row or row[0] is None:raise ValueError('No saved result; uncertain calls require manual reconciliation')
        cost=calculate_cost(json.loads(row[0]))
        if cost is not None:db.execute('UPDATE calls SET charged=? WHERE id=?',(str(_money(cost)),call_id))
        db.commit()
    finally:db.close()


def usage_cost(model,usage,*,day=None):
    day=date.fromisoformat(day) if day else date.today()
    # Re-check official catalog before extending this short-lived snapshot.
    if not date(2026,10,29)<=day<=date(2026,11,5) or model not in RATES:
        raise ValueError('Unknown or expired research tariff')
    if not isinstance(usage,dict):return None
    if model.startswith('gemini-'):
        values=[usage.get(k) for k in ['promptTokenCount','candidatesTokenCount']]
        if any(type(v) is not int or v<0 for v in values):return None
        input_tokens,output=values
        if usage.get('toolUsePromptTokenCount',0):return None  # No tools allowed by this experiment.
        thoughts=usage.get('thoughtsTokenCount')
        total=usage.get('totalTokenCount')
        if thoughts is None:
            if type(total) is not int or total<input_tokens+output:return None
            output_tokens=total-input_tokens
        else:
            if type(thoughts) is not int or thoughts<0:return None
            output_tokens=output+thoughts
            if total is not None and (type(total) is not int or total!=input_tokens+output_tokens):return None
    else:
        values=[usage.get(k) for k in ['input_tokens','output_tokens']]
        if any(type(v) is not int or v<0 for v in values):return None
        input_tokens,output_tokens=values
        if usage.get('cache_creation_input_tokens',0) or usage.get('cache_read_input_tokens',0):return None
    a,b=RATES[model]
    if model=='claude-haiku-5-5' and input_tokens>100000:a,b='0.50','2.50'
    return (Decimal(input_tokens)*Decimal(a)+Decimal(output_tokens)*Decimal(b))/Decimal(1000000)


def escalation_cases(cases,adjudicated_rows):
    """Union of C1/C2 failures -> complete template quartets for BOTH senior models.

    Rows must have a human-checked boolean failed, including partial misses and
    extras. Technical failures require review, not automatic semantic selection.
    """
    by_id={case['id']:case for case in cases};templates=set()
    for row in adjudicated_rows:
        if row['config'] not in {'C1','C2'}:continue
        if row['case'] not in by_id or type(row.get('failed')) is not bool:
            raise ValueError('Invalid or unadjudicated escalation row')
        if row['failed']:templates.add(by_id[row['case']]['template'])
    return [case['id'] for case in cases if case['template'] in templates]
