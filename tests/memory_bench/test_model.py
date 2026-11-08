import math

from memory_bench.model import CHARS_PER_TOKEN, Record, render, tokens_conservative, tokens_realistic
from storygen.memory.projection import project_memory
from storygen.token_budget.core import canonical
from tests.memory_bench.conftest import NUMBERS


def manual_records():
    rec=lambda c,cat,t,chars=(),scene=1,kind=None:Record(c,cat,t,tuple(chars),scene,scene,kind)
    records=(rec('f1','facts','Марія живе біля моря'),rec('s1','character_states','Марія без халата',['c1'],2),
        rec('s2','character_states','Іде дощ'))
    timeline=(rec('h1','timeline','Марія прийшла',kind='timeline'),rec('t1','open_threads','Ключ знайшовся',scene=2,kind='retired_thread'),
        rec('h2','timeline','Остап поїхав',scene=2,kind='timeline'))
    return records,timeline


def test_render_matches_project_memory_for_same_records(journal_fixture):
    records,timeline=manual_records()
    assert render(records,timeline)==project_memory(journal_fixture,[],NUMBERS).text


def test_render_empty_sections():
    assert render([],[]).count('Немає.')==4


def test_tokens_conservative_matches_core_fallback():
    assert tokens_conservative('Марія')==len(canonical('Марія').encode('utf-8'))+256


def test_tokens_realistic_is_ceil():
    assert tokens_realistic('a'*10)==math.ceil(10/CHARS_PER_TOKEN)


def test_render_summary_placeholder_length():
    assert len(render([],[],summary_chars=600))-len(render([],[]))>=600
