"""R-48 PR 2 (review M-3): `MentionIndex` finds a mention exactly when `mentions` does, under the same stem rule."""
import pytest

from storygen.memory.selection import MentionIndex, mentions, name_stems

TEXTS = [
    'Оля побачила Марка біля воріт.',
    'Марко й Олю ніхто не чекав. ОЛЬГА мовчала.',
    'Іван Петрович сів; петровичу налили чаю.',
    'Ліну, Ліна, Ліни — усі форми.',
    "О'Браєн та д’Артаньян зустрілися.",
    'Ян і Ева.',
    '',
]
NAMES = ['Марко', 'Оля', 'Ольга', 'Іван Петрович', 'Ліна', "О'Браєн", 'Д’Артаньян', 'Ян', 'Ева', 'Хазяїн, Бос',
         'Жан-Поль', 'Невідомий']


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('name', NAMES)
def test_mention_index_agrees_with_mentions(text, name):
    stems = name_stems(name)
    assert (MentionIndex(text).first(stems) is not None) == mentions(text, stems)


def test_first_is_the_earliest_word():
    index = MentionIndex('Оля побачила Марка, потім Марко пішов, Оля лишилась.')
    assert index.first(name_stems('Марко')) == 2
    assert index.first(name_stems('Оля')) == 0
    assert index.first(name_stems('Боб')) is None
    assert index.first(()) is None
