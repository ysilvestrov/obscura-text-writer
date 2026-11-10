import json

import pytest

from memory_bench.strategies import Params, product
from storygen.memory.projection import MemoryItem, render_memory
from storygen.memory.selection import SelectionInput
from tests.retrieval_bench.helpers import scene
from tests.retrieval_bench.test_cli import SECRETS, run_cli


def item(claim,section,text,chars=(),scene_number=1,owner=None):
    line=f'одяг: {text}' if section=='core' else '— '+text
    return MemoryItem(claim,section,owner,line,text,tuple(chars),'clothing' if section=='core' else None,scene_number)


def product_scene(targets=('t_far',)):
    items=(item('core','core','Марія в халаті',['c1'],9,'c1'),)+tuple(
        item(f'f{n}','facts',f'Маяк і море номер {n} '+'слово '*20) for n in range(20))+(
        item('t_far','open_threads','Хтось бачив вовка біля маяка'),)
    inp=SelectionInput(items,'s10',10,('c1',),('c1',),{'c1':'Марія'},'вовка')
    base=scene(targets=targets)
    return type(base)(**{**base.__dict__,'product':inp}),items


def test_product_keeps_full_section_while_it_fits():
    s,items=product_scene()
    sel=product(s,Params(10**9,'realistic','upper'))
    assert not sel.overflow and set(sel.record_ids)=={i.claim_id for i in items}
    assert sel.chars==len(render_memory(list(items),['c1'],{'c1':'Марія'}))


def test_product_selects_under_budget_core_first_then_fts():
    s,_=product_scene()
    sel=product(s,Params(120,'realistic','upper'))
    assert not sel.overflow and sel.tokens_realistic<=120
    assert 'core' in sel.record_ids and 't_far' in sel.record_ids and sel.dropped_by_budget>0


def test_product_reports_overflow_when_the_core_does_not_fit():
    s,_=product_scene()
    sel=product(s,Params(1,'realistic','upper'))
    assert sel.overflow and sel.record_ids==('core',)


def test_product_requires_real_data():
    with pytest.raises(ValueError):
        product(scene(),Params(100,'realistic','upper'))


def test_cli_reports_product_apart_from_existing_keys(synthetic_repo):
    repo,story_id,info=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--synthetic','','--context','32768'])
    assert out.returncode==0,out.stderr
    data=json.loads(out.stdout)
    assert set(data['product'])=={'32768'} and set(data['product']['32768'])=={'conservative','realistic'}
    assert data['product']['32768']['conservative']['scene_count']==data['story']['scene_count']
    assert 'product' not in data['real']['32768']['conservative']
    for secret in SECRETS+[story_id]:
        assert secret not in out.stdout
