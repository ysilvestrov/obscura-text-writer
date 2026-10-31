import json
import zipfile

import pytest
from pypdf import PdfReader

from storygen.application.exports import export_story
from tests.authoring.test_ebook_exports import seeded


@pytest.mark.parametrize('format',['md','txt','fb2','epub','pdf'])
def test_author_approved_stale_book_has_no_internal_warning_in_content_or_metadata(tmp_path,format):
    repo,story=seeded(tmp_path,count=1,cover=False)
    scene=repo.list_scenes(story.id)[0]
    repo.update_scene_plan(scene.id,'Уточнений план для перевірки.',scene.revision)
    with pytest.raises(ValueError,match='неповний'):export_story(repo,story.id,format)
    path=export_story(repo,story.id,format,True)
    if format=='pdf':text='\n'.join(p.extract_text() for p in PdfReader(path).pages)
    elif format=='epub':
        with zipfile.ZipFile(path) as archive:
            text='\n'.join(archive.read(n).decode('utf-8') for n in archive.namelist() if n.endswith(('.xhtml','.opf')))
    else:text=path.read_text(encoding='utf-8')
    assert 'НЕЗАВЕРШЕНО' not in text and 'export-status' not in text
    assert 'Сцена застаріла або потребує перегляду' not in text
    assert 'Ґанок' in text
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert not manifest['complete'] and manifest['warnings'] and manifest['scenes'][0]['warnings']


@pytest.mark.parametrize('format',['fb2','epub'])
def test_empty_author_approved_book_remains_valid_without_internal_placeholder(tmp_path,format):
    repo,story=seeded(tmp_path,count=0,cover=False)
    path=export_story(repo,story.id,format,True)
    if format=='fb2':text=path.read_text(encoding='utf-8')
    else:
        with zipfile.ZipFile(path) as archive:
            text='\n'.join(archive.read(n).decode('utf-8') for n in archive.namelist() if n.endswith(('.xhtml','.opf')))
    assert 'НЕЗАВЕРШЕНО' not in text and 'export-status' not in text
