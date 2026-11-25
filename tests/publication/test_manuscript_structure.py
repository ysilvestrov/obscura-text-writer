from storygen.publication.manuscript_read import ManuscriptParagraph
from storygen.publication.manuscript_structure import ParseSettings, detect, prose_indices, split_points, words


def doc(*specs):
    """Each spec: text, or (text, {heading_level, after_break, is_title})."""
    result = []
    for i, spec in enumerate(specs):
        text, opts = (spec, {}) if isinstance(spec, str) else spec
        result.append(ManuscriptParagraph(i, text, (), opts.get('h'), opts.get('brk', False), opts.get('title', False)))
    return result


def prose(n_words, prefix='слово'):
    return ' '.join(f'{prefix}{i}' for i in range(n_words)) + '.'


def titles(structure):
    return [s.title for s in structure.scenes]


def test_markers_win_over_styles():
    paras = doc(('Глава 1', {}), 'Текст один.', ('Глава 2', {'h': 1}), 'Текст два.', ('Підзаголовок', {'h': 1}), 'Ще.')
    structure = detect(paras, ParseSettings())
    assert structure.chapter_source == 'markers'
    assert titles(structure) == ['Глава 1', 'Глава 2']


def test_chapter_level_is_highest_repeated():
    paras = doc(('Один', {'h': 0}), ('Під', {'h': 1}), 'А.', ('Два', {'h': 0}), 'Б.')
    structure = detect(paras, ParseSettings())
    assert structure.chapter_source == 'level:1'
    assert titles(structure) == ['Один', 'Два']
    assert structure.scenes[0].start == 1  # deeper heading stays prose


def test_part_heading_excluded_from_level():
    paras = doc(('Part One', {'h': 0}), ('Перша', {'h': 1}), 'А.', ('Друга', {'h': 1}), 'Б.')
    structure = detect(paras, ParseSettings())
    assert structure.chapter_source == 'level:2'
    assert structure.parts == ((0, 'Part One'),)
    assert titles(structure) == ['Перша', 'Друга']
    assert [s.part_index for s in structure.scenes] == [0, 0]


def test_part_marker_needs_number():
    paras = doc(('Книга пам\'яті', {'h': 0}), ('Книга друга', {'h': 0}), ('Глава 1', {}), 'А.', ('Глава 2', {}), 'Б.')
    structure = detect(paras, ParseSettings())
    assert [name for _, name in structure.parts] == ['Книга друга']
    assert structure.title_suggestion == "Книга пам'яті"


def test_parts_skipped_when_not_allowed():
    paras = doc(('Частина 1', {'h': 0}), ('Глава 1', {}), 'А.', ('Глава 2', {}), 'Б.')
    structure = detect(paras, ParseSettings(parts_allowed=False))
    assert structure.parts == ()
    assert structure.dropped == ((0, 'Частина 1'),)
    assert any('частини доступні у виданні з довгою прозою' in w for w in structure.warnings)
    assert all(s.part_index is None for s in structure.scenes)


def test_separator_splits_chapter():
    paras = doc('Глава 1', 'Раз.', '* * *', 'Два.', '⁂', 'Три.', 'Глава 2', 'Чотири.')
    structure = detect(paras, ParseSettings())
    assert titles(structure) == ['Глава 1 (1)', 'Глава 1 (2)', 'Глава 1 (3)', 'Глава 2']
    assert 2 not in structure.prose_indices and 4 not in structure.prose_indices
    assert [s.proposed for s in structure.scenes] == [False, False, False, False]


def test_blank_line_is_not_separator():
    paras = doc('Глава 1', 'Раз.', ('Два.', {'brk': True}), 'Глава 2', 'Три.')
    assert titles(detect(paras, ParseSettings())) == ['Глава 1', 'Глава 2']


def test_prologue_over_50_words():
    paras = doc(prose(60), 'Глава 1', 'А.', 'Глава 2', 'Б.')
    structure = detect(paras, ParseSettings())
    assert titles(structure)[0] == 'Пролог'
    assert structure.front_matter == ()


def test_short_front_matter_kept_aside():
    paras = doc('Присвята коханій.', 'Глава 1', 'А.', 'Глава 2', 'Б.')
    structure = detect(paras, ParseSettings())
    assert structure.front_matter == (0,)
    assert 0 not in structure.prose_indices
    assert titles(structure) == ['Глава 1', 'Глава 2']


def test_title_from_title_style():
    paras = doc(('Мій роман', {'title': True}), 'Глава 1', 'А.', 'Глава 2', 'Б.')
    structure = detect(paras, ParseSettings())
    assert structure.title_suggestion == 'Мій роман'
    assert structure.front_matter == ()


def test_title_from_first_heading_before_chapters():
    paras = doc(('Мій роман', {'h': 0}), ('Глава 1', {'h': 1}), 'А.', ('Глава 2', {'h': 1}), 'Б.')
    assert detect(paras, ParseSettings()).title_suggestion == 'Мій роман'


def test_no_headings_one_chapter_with_warning():
    structure = detect(doc('А.', 'Б.', 'В.'), ParseSettings())
    assert len(structure.scenes) == 1 and structure.chapter_source == 'none'
    assert structure.warnings


def test_long_scene_gets_proposed_split():
    paras = doc(*[prose(100, f'п{i}х') for i in range(60)])
    structure = detect(paras, ParseSettings())
    assert len(structure.scenes) == 3
    assert [s.proposed for s in structure.scenes] == [False, True, True]
    for scene in structure.scenes:
        assert 1800 <= scene.words <= 2200
    assert sum(s.words for s in structure.scenes) == 6000


def test_split_prefers_break_then_non_dialogue():
    paras = doc(*[(prose(100), {}) for _ in range(30)])
    # target for 2 parts is paragraph 15; break at 13 beats the exact boundary 15
    paras[13] = ManuscriptParagraph(13, paras[13].text, (), None, True, False)
    assert split_points(paras, 0, 29, 2) == [13]
    plain = doc(*[prose(100) for _ in range(30)])
    plain[15] = ManuscriptParagraph(15, '— ' + plain[15].text, (), None, False, False)
    assert split_points(plain, 0, 29, 2) == [14]


def test_single_long_paragraph_warns():
    structure = detect(doc(prose(3000)), ParseSettings())
    assert len(structure.scenes) == 1
    assert 'довгий абзац без меж' in structure.scenes[0].warnings


def test_fits_false_triggers_split():
    paras = doc(*[prose(100) for _ in range(20)])
    limit = 1200
    structure = detect(paras, ParseSettings(), fits=lambda text: words(text) <= limit)
    assert len(structure.scenes) == 2
    assert all(s.words <= limit for s in structure.scenes)
    assert structure.scenes[1].proposed


def test_fits_never_true_keeps_split_with_warning():
    structure = detect(doc(prose(10), prose(10)), ParseSettings(), fits=lambda text: False)
    assert any(s.warnings for s in structure.scenes)


def test_chapter_source_override():
    paras = doc(('Один', {'h': 0}), ('А', {'h': 1}), 'т.', ('Б', {'h': 1}), 'т.', ('Два', {'h': 0}), 'т.')
    structure = detect(paras, ParseSettings(chapter_source=2))
    assert titles(structure) == ['А', 'Б']
    assert structure.chapter_source == 'level:2'


def test_marker_titles_and_numbers():
    paras = doc('Глава I. Початок', 'А.', 'Розділ перша — Кінець', 'Б.', 'Chapter Three: Dawn', 'В.', 'Глава про щось', 'Г.')
    structure = detect(paras, ParseSettings())
    assert titles(structure) == ['Початок', 'Кінець', 'Dawn']


def test_prose_indices_helper():
    paras = doc('Глава 1', 'А.', '***', 'Б.', 'Глава 2', 'В.')
    assert prose_indices(paras, ParseSettings()) == [1, 3, 5]
