import pytest

from storygen.generation.copyedit_review import sentence_context, copyedit_preview
from tests.generation.test_copyedit_review import generate


@pytest.mark.parametrize('text,anchor,before,after', [
    ('Ранок. Олена знала дорогу з катівниці до виходу. Далі.', 'з катівниці', 'Олена знала дорогу ', ' до виходу.'),
    ('— Я знала, але вона знала більше! — сказала Олена.', 'але вона знала', '— Я знала, ', ' більше!'),
    ('Перший абзац.\r\nОлена побачила 🙂 двері без ручки', 'двері', 'Олена побачила 🙂 ', ' без ручки'),
    ('Вона сказала: «Я знала». Потім пішла.', 'знала', 'Вона сказала: «Я ', '».'),
    ('Вона йшла.', '', 'Вона ', 'йшла.'),
    ('Ранок. Вона йшла. Він чекав. Вечір.', 'йшла. Він', 'Вона ', ' чекав.'),
    ('Ліворуч.\nВона йшла.\nВін чекав.\nДалі.', 'йшла.\nВін', 'Вона ', ' чекав.'),
])
def test_sentence_context(text, anchor, before, after):
    start=text.index(anchor) if anchor else len('Вона ')
    assert sentence_context(text,start,start+len(anchor)) == dict(context_before=before,context_after=after)


def test_legacy_preview_includes_sentence_around_each_exact_anchor(tmp_path):
    repo,scene,_,attempt=generate(tmp_path)
    edits=copyedit_preview(repo,scene.id,attempt.id)['edits']
    assert edits[0]['context_before']=='Це не '
    assert edits[0]['context_after']==' провина.'
    assert edits[1]['context_before']=='Вона '
    assert edits[1]['context_after']==' скла.'


def test_diff_preview_includes_exact_sentence_context(tmp_path):
    from tests.generation.test_edit_classification import fixture
    repo,scene,attempt=fixture(tmp_path)
    preview=copyedit_preview(repo,scene.id,attempt.id)
    for edit in preview['edits']:
        assert edit['context_before']+edit['original']+edit['context_after'] in preview['original']
        assert (edit['context_before']+edit['original']+edit['context_after']).startswith('Вона ')
        assert edit['context_after'].endswith('.')
