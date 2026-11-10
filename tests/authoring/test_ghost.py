"""#55: block split (shared vectors with the browser) and verbatim 4-gram overlap."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from storygen.authoring.ghost import GHOST_MIN_BLOCK_CHARS, ghost_blocks, normalize, overlap_4gram

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((ROOT / 'tests/fixtures/ghost_blocks.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('vector', VECTORS, ids=[v['name'] for v in VECTORS])
def test_shared_vectors(vector):
    assert [b.as_dict() for b in ghost_blocks(vector['text'])] == vector['blocks']


def _split(name):
    text = next(v['text'] for v in VECTORS if v['name'] == name)
    return normalize(text), [b.as_dict() for b in ghost_blocks(text)]


def test_block_rules():
    _, dialogue = _split('short_dialogue')
    assert len(dialogue) == 1, 'short replies are glued until the block reaches two lines; the short tail joins it'
    text, middle = _split('separator_middle')
    assert [b['kind'] for b in middle] == ['text', 'separator', 'text']
    assert text[middle[1]['start']:middle[1]['end']] == '***'
    assert text[middle[0]['start']:middle[0]['end']].endswith('Хвіст.'), 'short remainder before a separator joins the previous block'
    text, heading = _split('heading_starts_block')
    assert len(heading) == 2 and all(text[b['start']] == '#' for b in heading), 'a heading always starts a block'
    text, crlf = _split('crlf')
    assert text[crlf[0]['start']:].startswith('Рядок один.') and chr(13) not in text
    _, long = _split('long_paragraphs')
    assert len(long) == 2 and all(b['end'] - b['start'] >= GHOST_MIN_BLOCK_CHARS for b in long)
    text, astral = _split('supplementary_unicode')
    assert astral == [{'kind': 'text', 'start': 0, 'end': len(text)}], 'lengths are code points, not UTF-16 units'
    assert ghost_blocks('') == []


def test_browser_mirror_matches_vectors():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/ghost_blocks.mjs')], capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


def test_overlap_4gram():
    draft = 'Вона відчинила двері й побачила порожній коридор, де пахло дощем.'
    assert overlap_4gram(draft, draft) == 1.0
    assert overlap_4gram('Зовсім інші слова тут стоять поруч.', draft) == 0.0
    assert overlap_4gram('Вона відчинила двері й тихо вийшла.', draft) == round(1 / 3, 4)
    assert overlap_4gram('Три слова лише', draft) is None
    assert overlap_4gram(draft, 'Коротко дуже') == 0.0


def test_overlap_tokens_keep_apostrophes_and_hyphens():
    draft = "М’ята пам'ять ніяк не відпускала південно-східний вітер."
    author = "Мʼята пам’ять ніяк не відпускала"
    assert overlap_4gram(author, draft) == 1.0
    assert overlap_4gram('південно східний вітер дув сильно', draft) == 0.0
