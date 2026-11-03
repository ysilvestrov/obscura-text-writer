import pytest
from storygen.impact.models import fingerprint


def registry():
    return {
        'S1':dict(kind='source',side='new',version_id='a',document_hash='a-hash',start=0,end=10,text='Так.\r\nНі.🙂',change_id='c1'),
        'S2':dict(kind='source',side='new',version_id='b',document_hash='b-hash',start=0,end=4,text='Інак',change_id='c2'),
        'T1':dict(kind='target',version_id='target',document_hash='t-hash',start=0,end=4,text='Текст',material='prose'),
    }


def endpoint(ref,quote,start=0):
    return dict(ref=ref,start=start,end=start+len(quote),quote=quote)


def pair(left='S1',right='T1'):
    r=registry()
    return dict(type='contradiction',left=endpoint(left,r[left]['text']),right=endpoint(right,r[right]['text']),explanation='Несумісні твердження.')


def api():
    import storygen.review as module
    assert hasattr(module,'evidence'), 'Новий контракт адресованих доказів ще не реалізовано'
    return module.evidence


def test_offsets_preserve_crlf_and_unicode():
    e=api();r=registry()
    s=e.statement(r,endpoint('S1','Ні.🙂',6))
    assert s['start']==6 and s['quote']=='Ні.🙂' and s['role']=='source'
    with pytest.raises(ValueError):e.statement(r,endpoint('S1','Так.\nНі.🙂'))
    with pytest.raises(ValueError):e.statement(r,endpoint('S1','Ні.🙂',5))


def test_known_ref_is_not_permission_to_quote_outside_delivered_span():
    e=api();r=registry();r['S1'].update(start=20,end=30)
    s=e.statement(r,endpoint('S1','Так.',0))
    assert s['start']==20 and s['end']==24
    with pytest.raises(ValueError):e.statement(r,endpoint('S1','',0))
    with pytest.raises(ValueError):e.statement(r,endpoint('S1','Невідомий текст',10))


def test_pair_classification_and_gap():
    e=api();r=registry()
    out=e.classify_candidates([pair(),pair('S1','S2')],r,[])
    assert [c['kind'] for c in out['concerns']]==['question','question']
    assert all(c['subtype']=='premise_conflict' for c in out['concerns'])
    out=e.classify_candidates([pair()],r,[])
    assert out['concerns'][0]['kind']=='issue'
    gap=dict(type='information_gap',target=endpoint('T1','Текст'),source_refs=[],missing_information='Кому належить предмет?',why_needed='Без власника не можна перевірити перехід предмета.')
    out=e.classify_candidates([gap],r,[])
    assert out['concerns'][0]['subtype']=='information_gap'


def test_priority_suppresses_only_exact_statement():
    e=api();r=registry()
    a=e.statement(r,pair()['left']);b=e.statement(r,pair('S2','T1')['left'])
    decision=dict(preferred_statement_id=a['id'],superseded_statement_id=b['id'])
    out=e.classify_candidates([pair('S1','S2'),pair('S2','T1'),pair()],r,[decision],statements={a['id']:a,b['id']:b})
    assert len(out['suppressed'])==2
    assert len(out['concerns'])==1 and out['concerns'][0]['kind']=='issue'
    # Another statement from the same source remains current.
    another=pair('S2','T1');another['left']=endpoint('S2','Ін',0)
    out=e.classify_candidates([another],r,[decision],statements={a['id']:a,b['id']:b})
    assert out['rejected'][0]['code']=='authority_ambiguous'


def test_priority_rejects_chains_cycles_and_foreign_statements():
    e=api();r=registry()
    a=e.statement(r,endpoint('S1','Так.'));b=e.statement(r,endpoint('S1','Ні.🙂',6));c=e.statement(r,endpoint('S2','Інак'))
    ss={s['id']:s for s in [a,b,c]}
    def d(x,y):return dict(preferred_statement_id=x['id'],superseded_statement_id=y['id'])
    assert len(e.validate_priorities([d(a,b),d(a,c)],ss))==2
    for decisions in [[d(a,b),d(b,c)],[d(a,b),d(b,a)],[d(a,b),d(c,b)],[d(a,a)]]:
        with pytest.raises(ValueError):e.validate_priorities(decisions,ss)
    with pytest.raises(ValueError):e.validate_priorities([dict(preferred_statement_id='unknown',superseded_statement_id=b['id'])],ss)


def test_partial_candidates_are_isolated_and_target_pair_rejected():
    e=api();bad=pair();bad['right']['quote']='Чужий'
    out=e.classify_candidates([pair(),bad,pair('T1','T1')],registry(),[])
    assert len(out['concerns'])==1 and len(out['rejected'])==2
    assert out['execution_state']=='partial'


def test_duplicate_pair_orientation_keeps_provenance():
    e=api();a=pair();b=dict(a,left=a['right'],right=a['left'],explanation='Інше пояснення.')
    out=e.classify_candidates([a,b],registry(),[])
    assert len(out['concerns'])==1
    assert len(out['concerns'][0]['provenance'])==2


def test_conflicts_are_not_transitive():
    e=api();r=registry();r['S3']={**r['S2'],'version_id':'c','document_hash':'c-hash'}
    ab=pair('S1','S2');bc=dict(type='contradiction',left=endpoint('S2','Інак'),right=endpoint('S3','Інак'),explanation='Другий конфлікт.')
    out=e.classify_candidates([ab,bc],r,[])
    assert len(out['conflicts'])==2
    assert len(out['concerns'])==2
