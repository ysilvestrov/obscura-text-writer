"""Editor bench (#260 part 2): the error injector and the scorer, without any network."""
import random
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from editor_bench.inject import CATEGORIES, inject  # noqa: E402
from editor_bench.score import score  # noqa: E402

WORDS = ('Старий рибалка довго дивився на море, що темніло під вечір. Він згадував, як колись виходив на човні '
         'щоранку — навіть тоді, коли хвилі билися об берег. Тепер руки боліли, але серце ще кликало його до води. '
         'Нарешті він підвівся, узяв сітку й повільно пішов стежкою, яку знав напам’ять. Сусіди казали, що він '
         'мабуть збожеволів, проте він тільки всміхався у відповідь. Протягом багатьох років вони звикли до його '
         'дивацтв, і ніхто вже не дивувався. Наступного ранку він знову сидів на камені — тихий, зосереджений, '
         'майже нерухомий. Вітер приносив запах солі, а чайки кричали над головою. Раптом він побачив далеко '
         'вітрило, яке повільно наближалося до берега. Звичайно, це міг бути будь-хто, але старий відчув, що це '
         'повертається його син. ')
MORE = ('Хлопець зійшов на пісок, і батько одразу впізнав його ходу. Вони обнялися мовчки, бо слова здавалися '
        'зайвими. Мати також вибігла з хати, витираючи руки об фартух. Ніколи раніше село не бачило такої радості, '
        'хоча свята тут любили. Згодом сусіди принесли вино, хліб і печену рибу. Діти бігали між столами, а собаки '
        'гавкали на чужих коней. Приблизно опівночі музики заграли старовинну пісню. Дівчата співали тихо, '
        'зовсім не так, як на весіллях. Дійсно, ця ніч запам’яталася всім надовго. Поки старші розмовляли, '
        'молодь танцювала біля вогнища. Завжди хтось починав сварку, але цього разу всі мирилися. Взагалі, '
        'рибалки рідко говорять про свої почуття. Учитель прочитав вірш, який написав учора ввечері. Писар '
        'записував імена гостей, щоб нікого не забути. Корчмар рахував гроші, зітхаючи над кожною монетою. '
        'Наступна весна принесла дощі, і поля зазеленіли рано. Хлібороби раділи, бо минулий рік був посушливий. '
        'Священник благословив човни, коли рибалки вийшли в море. Над затокою кружляли птахи, ніби вітаючи людей. '
        'Тепер син лишився вдома, і батько навчав його ремесла. Вони плели сіті, лагодили весла, фарбували човен. '
        'Старий розповідав про шторми, яких бачив чимало. Син слухав уважно, хоча деякі історії знав напам’ять. '
        'Вечорами вони сиділи на порозі, дивлячись на зорі. Кожен думав про своє, але обом було спокійно. '
        'Життя тривало, неквапливе й просте, як течія ріки. ')


def text():
    # Enough distinct sentences for 30 mistakes, each in its own sentence; no repeated paragraphs, so alignment is real.
    return WORDS + MORE


def test_injection_is_deterministic_and_fills_each_category():
    first, gold = inject(text(), seed=7)
    again, gold_again = inject(text(), seed=7)
    assert (first, gold) == (again, gold_again)
    assert first != text()
    assert {c: sum(m.category == c for m in gold) for c in CATEGORIES} == {c: 10 for c in CATEGORIES}
    assert inject(text(), seed=8)[0] != first


def test_each_mistake_sits_in_its_own_sentence_and_differs_from_the_right_form():
    _, gold = inject(text(), seed=3)
    assert len({m.sentence for m in gold}) == len(gold)
    assert all(m.wrong != m.right for m in gold)


def test_a_text_too_short_for_the_mistakes_is_refused():
    with pytest.raises(ValueError, match='(?i)замало'):
        inject(WORDS, seed=1)


def test_an_editor_that_restores_the_original_fixes_everything():
    broken, gold = inject(text(), seed=5)
    result = score(gold, broken, text())
    assert {c: result[c] for c in CATEGORIES} == {c: {'fixed': 10, 'missed': 0, 'other': 0, 'fixed_lenient': 10} for c in CATEGORIES}
    assert result['off_gold_tokens'] == 0


def test_an_editor_that_changes_nothing_misses_everything():
    broken, gold = inject(text(), seed=5)
    result = score(gold, broken, broken)
    assert {c: result[c] for c in CATEGORIES} == {c: {'fixed': 0, 'missed': 10, 'other': 0, 'fixed_lenient': 0} for c in CATEGORIES}
    assert result['off_gold_tokens'] == 0


def test_half_fixed_and_one_rewritten_sentence_are_counted_exactly():
    original = text()
    broken, gold = inject(original, seed=11)
    # Fix every second mistake by applying its right form at its span, from the end.
    fixed_ids = {id(m) for m in gold[::2]}
    edited = broken
    for m in sorted(gold, key=lambda m: m.start, reverse=True):
        if id(m) in fixed_ids:
            edited = edited[:m.start] + m.right + edited[m.start + len(m.wrong):]
    # An off-gold change: a word replaced where no mistake was inserted.
    free = [m.start() for m in __import__('re').finditer(r'(?<=\. )[^\W\d]{4,} [^\W\d]{4,}', broken)
            if not any(g.start <= m.end() + 1 and m.start() - 1 <= g.start + len(g.wrong) for g in gold)]
    at = free[0]
    word = broken[at:].split(' ', 1)[0]
    at += sum(len(m.right) - len(m.wrong) for m in gold if id(m) in fixed_ids and m.start < at)
    edited = edited[:at] + 'Бриз' + edited[at + len(word):]
    result = score(gold, broken, edited)
    assert sum(result[c]['fixed'] for c in CATEGORIES) == len(fixed_ids)
    assert sum(result[c]['missed'] for c in CATEGORIES) == len(gold) - len(fixed_ids)
    assert result['off_gold_tokens'] == 1


def test_a_wrong_correction_counts_as_other():
    broken, gold = inject(text(), seed=2)
    m = gold[0]
    edited = broken[:m.start] + m.right + 'х' + broken[m.start + len(m.wrong):]
    result = score(gold, broken, edited)
    assert result[m.category]['other'] == 1


def test_a_fix_with_a_neighbouring_change_is_lenient_but_not_strict():
    broken, gold = inject(text(), seed=2)
    m, found = next((g, f) for g in gold if g.category == 'spelling'
                    for f in [re.match(r'(\s+)([^\W\d]+)', broken[g.start + len(g.wrong):])] if f)
    tail = broken[m.start + len(m.wrong):]
    gap, word = found.groups()
    edited = broken[:m.start] + m.right + gap + 'Бриз' + tail[len(gap) + len(word):]
    result = score(gold, broken, edited)
    assert result[m.category]['other'] == 1 and result[m.category]['fixed'] == 0
    assert result[m.category]['fixed_lenient'] == 1


def test_a_wrong_correction_is_not_lenient_either():
    broken, gold = inject(text(), seed=2)
    m = gold[0]
    edited = broken[:m.start] + m.right + 'х' + broken[m.start + len(m.wrong):]
    assert score(gold, broken, edited)[m.category]['fixed_lenient'] == 0


def test_the_share_of_words_kept_shows_a_shortened_text():
    broken, gold = inject(text(), seed=2)
    assert score(gold, broken, broken)['words_kept'] == 1.0
    half = broken[:len(broken) // 2]
    assert 0.45 < score(gold, broken, half)['words_kept'] < 0.55
