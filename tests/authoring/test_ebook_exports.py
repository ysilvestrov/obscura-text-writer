import hashlib
import io
import json
import zipfile
from xml.etree import ElementTree as ET
import pytest
from PIL import Image
from storygen.domain import StoryCreate,SceneCreate
from storygen.publication_models import PublicationData
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.application.exports import export_story


FB={'f':'http://www.gribuser.ru/xml/fictionbook/2.0'}
SOURCE='Ґанок & Єва <script>alert("Ї")</script>.\n\n— Ідімо, — сказала вона.\n  Пробіли збережено.\n'


def seeded(root,count=7,cover=True):
    repo=Repository(root);story=repo.create_story(StoryCreate(title='Робоча назва'))
    for i in range(count):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {i+1}: <Двері>'))
        save_manual_prose(repo,scene.id,SOURCE,0)
    author=repo.publication('create_signature',display_name='Псевдонім & Їжак')
    translator=repo.publication('create_signature',display_name='Перекладач')
    cover_id=None
    if cover:
        image=io.BytesIO();Image.new('RGB',(20,30),'red').save(image,format='PNG')
        cover_id=repo.publication('upload_cover',story_id=story.id,content=image.getvalue()).id
    data=PublicationData(title='Публічна назва',author_ids=[author.id],translator_ids=[translator.id],
        annotation='Про вибір.\n\nБез спойлерів.',genres=['short_story'],keywords=['двері','місто'],
        cover_id=cover_id,cycle_title='Цикл',cycle_number=2,publication_date='2026-10-22',
        publisher='Видавець',isbn='9780306406157',rights='Усі права автора',source_language='en')
    repo.publication('save_card',story_id=story.id,data=data,expected_revision=0,
        expected_signature_revisions={author.id:0,translator.id:0})
    return repo,story


@pytest.mark.parametrize('format',['fb2','epub'])
def test_seven_scene_ebooks_metadata_plaintext_and_manifest(tmp_path,format):
    repo,story=seeded(tmp_path)
    path=export_story(repo,story.id,format)
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert manifest['schema_version']==2 and manifest['complete']
    assert manifest['output_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest['metadata']['effective_title']=='Публічна назва'
    assert len(manifest['scenes'])==7
    if format=='fb2':
        root=ET.fromstring(path.read_bytes())
        assert root.find('f:description/f:title-info/f:author/f:nickname',FB).text=='Псевдонім & Їжак'
        assert len(root.findall('f:body/f:section',FB))==7
        paragraphs=root.findall('f:body/f:section/f:p',FB)
        assert paragraphs[0].text==SOURCE.split('\n')[0]
        assert root.findall('f:body/f:section/f:empty-line',FB)
        assert root.find('f:binary',FB) is not None
        assert root.find('f:description/f:publish-info',FB) is None
    else:
        with zipfile.ZipFile(path) as z:
            assert z.namelist()[0]=='mimetype' and z.getinfo('mimetype').compress_type==zipfile.ZIP_STORED
            assert z.read('mimetype')==b'application/epub+zip'
            opf=ET.fromstring(z.read('EPUB/package.opf'))
            assert len(opf.findall('{http://www.idpf.org/2007/opf}spine/{http://www.idpf.org/2007/opf}itemref'))==8
            chapter=ET.fromstring(z.read('EPUB/chapter-1.xhtml'))
            assert chapter.find('.//{http://www.w3.org/1999/xhtml}p').text==SOURCE.split('\n')[0]
            assert not chapter.findall('.//{http://www.w3.org/1999/xhtml}script')
            assert 'EPUB/cover.png' in z.namelist()


def test_fb2_missing_author_or_genre_is_not_fixed_by_allow_incomplete(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Книга'))
    with pytest.raises(ValueError,match='Автор|автор'):export_story(repo,story.id,'fb2',True)
    assert not (tmp_path/'stories'/story.id/'exports').exists()


@pytest.mark.parametrize('format',['fb2','epub'])
def test_incomplete_ebooks_are_explicit_and_bad_controls_rejected(tmp_path,format):
    repo,story=seeded(tmp_path,count=1,cover=False)
    repo.create_scene(story.id,SceneCreate(title='Немає тексту'))
    with pytest.raises(ValueError,match='неповний'):export_story(repo,story.id,format)
    path=export_story(repo,story.id,format,True)
    raw=path.read_bytes() if format=='fb2' else zipfile.ZipFile(path).read('EPUB/chapter-2.xhtml')
    assert 'НЕЗАВЕРШЕНО' in raw.decode('utf-8')
    scene=repo.list_scenes(story.id)[0]
    save_manual_prose(repo,scene.id,'Текст\x00заборонений XML символ.',scene.revision)
    with pytest.raises(ValueError,match='XML'):export_story(repo,story.id,format,True)


def test_snapshot_survives_changes_to_card_and_prose_during_blob_read(tmp_path,monkeypatch):
    repo,story=seeded(tmp_path,count=1,cover=False)
    original=repo.files.read;changed=False
    def read(path,sha):
        nonlocal changed
        if not changed:
            changed=True
            view=repo.publication_snapshot(story.id).publication
            data=PublicationData(**view.card.model_dump(exclude={'story_id','revision'}));data.title='Інша назва'
            repo.publication('save_card',story_id=story.id,data=data,expected_revision=1,
                expected_signature_revisions={p.id:p.revision for p in [*view.authors,*view.translators]})
            scene=repo.list_scenes(story.id)[0]
            save_manual_prose(repo,scene.id,'Новий текст',scene.revision)
        return original(path,sha)
    monkeypatch.setattr(repo.files,'read',read)
    path=export_story(repo,story.id,'epub')
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert manifest['metadata']['effective_title']=='Публічна назва'
    with zipfile.ZipFile(path) as z:
        assert 'Новий текст' not in z.read('EPUB/chapter-1.xhtml').decode()
    second=export_story(repo,story.id,'epub')
    other=json.loads(second.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert other['edition_id']==manifest['edition_id'] and other['export_id']!=manifest['export_id']


def test_manifest_failure_leaves_prior_download_valid_but_orphan_inaccessible(tmp_path,monkeypatch):
    from storygen.application.exports import download_export
    repo,story=seeded(tmp_path,count=1,cover=False)
    old=export_story(repo,story.id,'epub');write=repo.files.write
    def fail(relative,content):
        if relative.endswith('manifest.json'):raise OSError('Disk full')
        write(relative,content)
    monkeypatch.setattr(repo.files,'write',fail)
    with pytest.raises(OSError):export_story(repo,story.id,'epub')
    assert download_export(repo,story.id,old.name)==old.read_bytes()
    orphan=next(p for p in old.parent.glob('*.epub') if p!=old)
    with pytest.raises(KeyError):download_export(repo,story.id,orphan.name)


@pytest.mark.parametrize('format',['md','txt','fb2','epub'])
def test_fifteen_thousand_words_and_tampered_download(tmp_path,format):
    from storygen.application.exports import download_export
    from storygen.domain import StorageCorruption
    repo,story=seeded(tmp_path,count=7,cover=False)
    for scene in repo.list_scenes(story.id):
        save_manual_prose(repo,scene.id,' '.join(['слово']*2200),scene.revision)
    path=export_story(repo,story.id,format)
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert manifest['word_count']==15400
    assert download_export(repo,story.id,path.name)==path.read_bytes()
    path.write_bytes(b'tampered')
    with pytest.raises(StorageCorruption):download_export(repo,story.id,path.name)
    with pytest.raises(StorageCorruption):download_export(repo,story.id,path.with_suffix('.manifest.json').name)


def test_epub_without_optional_metadata_and_legacy_download(tmp_path):
    from storygen.application.exports import download_export
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Назва'))
    scene=repo.create_scene(story.id,SceneCreate(title='Розділ'));save_manual_prose(repo,scene.id,'Текст.',0)
    path=export_story(repo,story.id,'epub')
    with zipfile.ZipFile(path) as z:
        assert 'EPUB/cover.xhtml' not in z.namelist()
    name='a'*32+'.txt';base=f'stories/{story.id}/exports/'
    repo.files.write(base+name,b'legacy')
    repo.files.write(base+'a'*32+'.manifest.json',json.dumps({'format':'txt','story_id':story.id}).encode())
    assert download_export(repo,story.id,name)==b'legacy'


def test_fb2_requires_genre_and_rejects_dtd_or_invalid_schema(tmp_path):
    from storygen.publication.fb2 import validate
    repo,story=seeded(tmp_path,count=1,cover=False)
    view=repo.publication_snapshot(story.id).publication
    data=PublicationData(**view.card.model_dump(exclude={'story_id','revision'}));data.genres=[]
    repo.publication('save_card',story_id=story.id,data=data,expected_revision=1,
        expected_signature_revisions={p.id:p.revision for p in [*view.authors,*view.translators]})
    with pytest.raises(ValueError,match='жанр'):export_story(repo,story.id,'fb2',True)
    for raw in [b'<!DOCTYPE a><a/>',b'<FictionBook/>']:
        with pytest.raises(ValueError):validate(raw)
