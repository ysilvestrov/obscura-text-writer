import io,json
import pytest
from pypdf import PdfReader
from storygen.application.exports import export_story,download_export
from storygen.generation.dependencies import save_manual_prose
from tests.authoring.test_ebook_exports import seeded


def test_pdf_a5_cover_title_contents_unicode_fonts_and_download(tmp_path):
    repo,story=seeded(tmp_path,count=7)
    path=export_story(repo,story.id,'pdf')
    reader=PdfReader(path);text=[p.extract_text() for p in reader.pages]
    assert len(reader.pages)==10  # cover, title, contents, seven short chapters
    assert 'Публічна назва' in text[1] and 'Псевдонім & Їжак' in text[1]
    assert 'Зміст' in text[2]
    assert not text[0].strip() and '2' not in text[1].splitlines()
    assert '3' in text[2].splitlines()
    for index in range(1,8):
        assert f'Сцена {index}: <Двері>' in text[index+2]
        assert f'Сцена {index}: <Двері>' in text[2]
        assert 'Ґанок & Єва <script>alert("Ї")</script>.' in text[index+2]
        assert '— Ідімо, — сказала вона.' in text[index+2]
    for page in reader.pages:
        assert float(page.mediabox.width)==pytest.approx(148*72/25.4,abs=.02)
        assert float(page.mediabox.height)==pytest.approx(210*72/25.4,abs=.02)
        for font in page['/Resources'].get('/Font',{}).get_object().values():
            font=font.get_object()
            if 'NotoSerif' in str(font.get('/BaseFont')):
                assert '/FontFile2' in font['/FontDescriptor']
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert manifest['format_details']['fonts']['license']=='OFL-1.1'
    assert manifest['format_details']['library'].startswith('ReportLab 4.')
    assert download_export(repo,story.id,path.name)==path.read_bytes()


def test_pdf_large_book_no_blank_pages_and_contents_page_numbers(tmp_path):
    repo,story=seeded(tmp_path,count=7,cover=False)
    for scene in repo.list_scenes(story.id):
        save_manual_prose(repo,scene.id,' '.join(['слово']*2200),scene.revision)
    path=export_story(repo,story.id,'pdf');reader=PdfReader(path)
    text=[p.extract_text() for p in reader.pages]
    assert len(text)>20 and all(t.strip() for t in text)
    assert sum(t.count('слово') for t in text)==15400
    # Extracted contents contains each title and its actual physical page.
    contents=text[1]
    for index in range(1,8):
        title=f'Сцена {index}: <Двері>'
        physical=next(i+1 for i,t in enumerate(text) if i>1 and title in t)
        assert f'{physical}' in contents


def test_pdf_unsupported_glyph_and_incomplete_guard(tmp_path):
    repo,story=seeded(tmp_path,count=1,cover=False)
    scene=repo.list_scenes(story.id)[0]
    save_manual_prose(repo,scene.id,'Текст 🦄',scene.revision)
    with pytest.raises(ValueError,match='U\\+1F984'):export_story(repo,story.id,'pdf',True)
    assert not (tmp_path/'stories'/story.id/'exports').exists()


def test_pdf_long_unbroken_words_titles_and_plaintext_markup(tmp_path):
    repo,story=seeded(tmp_path,count=1,cover=False)
    scene=repo.list_scenes(story.id)[0]
    repo.update_scene_metadata(scene.id,{'title':'Ї'*280},scene.revision)
    scene=repo.get_scene(scene.id)
    save_manual_prose(repo,scene.id,'<b>не жирний</b> '+'слово'*150,scene.revision)
    path=export_story(repo,story.id,'pdf')
    text=''.join(p.extract_text() for p in PdfReader(path).pages)
    assert '<b>не жирний</b>' in text
    assert text.replace('\n','').count('слово')>=150


def test_pdf_empty_incomplete_book_has_no_toc_placeholder(tmp_path):
    from storygen.domain import StoryCreate
    from storygen.storage.repository import Repository
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Порожня'))
    with pytest.raises(ValueError,match='неповний'):export_story(repo,story.id,'pdf')
    path=export_story(repo,story.id,'pdf',True)
    text=''.join(p.extract_text() for p in PdfReader(path).pages)
    assert 'НЕЗАВЕРШЕНО' in text and 'Placeholder' not in text

def test_pdf_contents_never_interprets_author_markup(tmp_path):
    repo,story=seeded(tmp_path,count=1,cover=False)
    scene=repo.list_scenes(story.id)[0]
    repo.update_scene_metadata(scene.id,{'title':'<b>Сцена</b> & <i>Текст</i>'},scene.revision)
    scene=repo.get_scene(scene.id);save_manual_prose(repo,scene.id,'Проза.',scene.revision)
    path=export_story(repo,story.id,'pdf')
    assert '<b>Сцена</b> & <i>Текст</i>' in PdfReader(path).pages[1].extract_text()


def test_pdf_optional_dependency_failure_does_not_break_md(tmp_path,monkeypatch):
    import sys
    repo,story=seeded(tmp_path,count=1,cover=False)
    monkeypatch.setitem(sys.modules,'reportlab',None)
    assert export_story(repo,story.id,'md').is_file()
    with pytest.raises(ValueError,match='ReportLab'):export_story(repo,story.id,'pdf')


def test_pdf_bad_font_hash_fails_before_publication(tmp_path,monkeypatch):
    import shutil
    from importlib.resources import files
    from storygen.publication import pdf
    root=tmp_path/'resources';fontdir=root/'resources/fonts'
    shutil.copytree(files('storygen.publication').joinpath('resources/fonts'),fontdir)
    (fontdir/'NotoSerif-Regular.ttf').write_bytes(b'broken font')
    monkeypatch.setattr(pdf,'files',lambda package:root)
    repo,story=seeded(tmp_path/'data',count=1,cover=False)
    with pytest.raises(ValueError,match='шрифти'):export_story(repo,story.id,'pdf')
    assert not (repo.root/'stories'/story.id/'exports').exists()
