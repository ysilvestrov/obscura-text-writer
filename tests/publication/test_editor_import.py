"""IMPORT-DOCX: the preview of an editor's DOCX (spec §4, comments §5.3)."""
import io
import os
import re
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from storygen.application import editor_import
from storygen.application.editor_import import load_manifest, plan_scene, preview_import, sweep_temp
from storygen.application.editor_import_match import match_scenes
from storygen.application.exports import export_story
from storygen.authoring.comments import CommentPayload, validate_comment_set
from storygen.domain import SceneCreate, StageAttempt, new_id
from storygen.generation.dependencies import save_manual_prose
from storygen.publication.docx_import import read_docx
from tests.authoring.test_ebook_exports import seeded

T = '<w:t xml:space="preserve">'
TEXTS = ('Перша сцена. Ранок був тихий.',
         'Він *швидко* пішов \\* додому.\n\n— Ідімо, — сказала вона.',
         'Третя сцена. Вечір.')


def book(tmp_path, texts=TEXTS, empty_scene=False):
    repo, story = seeded(tmp_path, count=len(texts), cover=False)
    for scene, text in zip(repo.list_scenes(story.id), texts):
        save_manual_prose(repo, scene.id, text, repo.get_scene(scene.id).revision, content_format='markdown')
    if empty_scene:
        repo.create_scene(story.id, SceneCreate(title='Порожня'))
    content = export_story(repo, story.id, 'docx', allow_incomplete=empty_scene).read_bytes()
    return repo, story, repo.list_scenes(story.id), content


def run(text):
    return f'<w:r>{T}{text}</w:t></w:r>'


def tracked(old, new):
    return (f'<w:del w:id="90" w:author="Р"><w:r><w:delText xml:space="preserve">{old}</w:delText></w:r></w:del>'
            f'<w:ins w:id="91" w:author="Р">{run(new)}</w:ins>')


def ranged(cid, inner):
    return f'<w:commentRangeStart w:id="{cid}"/>{inner}<w:commentRangeEnd w:id="{cid}"/>'


def split(xml, phrase, middle):
    """Put run-level XML in place of a phrase that sits inside one plain run."""
    assert xml.count(phrase) == 1
    return xml.replace(phrase, f'</w:t></w:r>{middle}<w:r>{T}')


def edit(content, change=lambda xml: xml, comments=(), custom=None):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output, 'w') as target:
        for name in source.namelist():
            data = source.read(name)
            if name == 'word/document.xml':
                data = change(data.decode('utf-8')).encode('utf-8')
            elif name == 'docProps/custom.xml' and custom:
                data = custom(data.decode('utf-8')).encode('utf-8')
            target.writestr(name, data)
        if comments:
            body = ''.join(f'<w:comment w:id="{cid}" w:author="{author}"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:comment>'
                           for cid, author, text in comments)
            target.writestr('word/comments.xml',
                '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + body + '</w:comments>')
    return output.getvalue()


def statuses(preview):
    return [item.status for item in preview.scenes]


def plan_of(repo, story, content, scene_id, base='export'):
    doc = read_docx(content)
    manifest = load_manifest(repo, story.id, doc.export_id)
    fragments, _ = match_scenes(doc, editor_import.scene_order(repo, story.id, manifest))
    fragment = next(f for f in fragments if f.scene_id == scene_id)
    entry = editor_import.manifest_entry(manifest, scene_id)
    return plan_scene(repo, story.id, repo.get_scene(scene_id), fragment, doc, entry, base=base)


def checked(plan):
    payload = CommentPayload(general=plan.general, comments=plan.comments)
    validate_comment_set(plan.normalized.text, 'markdown', payload)
    return payload


def test_unchanged_file(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    preview = preview_import(repo, story.id, content)
    assert statuses(preview) == ['unchanged'] * 3
    assert [item.scene_id for item in preview.scenes] == [scene.id for scene in scenes]
    assert preview.choice_required is False and preview.unmatched == [] and preview.warnings == []
    assert (tmp_path / 'editor-import' / f'{preview.import_id}.docx').read_bytes() == content


def test_changed_scene_counts_edits(tmp_path):
    repo, story, _, content = book(tmp_path)
    preview = preview_import(repo, story.id, edit(content, lambda xml: split(xml, 'пішов', tracked('пішов', 'побіг'))))
    assert statuses(preview) == ['unchanged', 'changed', 'unchanged']
    assert preview.scenes[1].edits == 1 and preview.choice_required is False


def test_plain_edit_without_tracking(tmp_path):
    repo, story, _, content = book(tmp_path)
    preview = preview_import(repo, story.id, edit(content, lambda xml: xml.replace('пішов', 'побіг')))
    assert statuses(preview) == ['unchanged', 'changed', 'unchanged']
    assert preview.scenes[1].edits == 1


def test_comments_only(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    changed = edit(content, lambda xml: split(xml, 'сказала вона', ranged(5, run('сказала вона'))),
                   [(5, 'Редакторка', 'Точніше')])
    preview = preview_import(repo, story.id, changed)
    assert statuses(preview) == ['unchanged', 'comments_only', 'unchanged']
    assert (preview.scenes[1].comments, preview.scenes[1].general_comments) == (1, 0)
    plan = plan_of(repo, story, changed, scenes[1].id)
    checked(plan)
    anchor = plan.comments[0].anchor
    assert anchor.display_quote == 'сказала вона' and plan.comments[0].instruction == 'Редактор (Редакторка): Точніше'


def test_anchor_ends_after_italic_run_and_escape(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    one = edit(content, lambda xml: xml.replace(f'<w:r>{T}Він </w:t></w:r>', f'<w:commentRangeStart w:id="1"/><w:r>{T}Він </w:t></w:r>')
               .replace('швидко</w:t></w:r>', 'швидко</w:t></w:r><w:commentRangeEnd w:id="1"/>'), [(1, 'Р', 'Курсив')])
    plan = plan_of(repo, story, one, scenes[1].id)
    checked(plan)
    assert [(c.anchor.source_quote, c.anchor.display_quote) for c in plan.comments] == [('Він *швидко', 'Він швидко')]
    two = edit(content, lambda xml: split(xml, 'пішов * додому', ranged(2, run('пішов * додому'))), [(2, 'Р', 'Зірка')])
    plan = plan_of(repo, story, two, scenes[1].id)
    checked(plan)
    assert [(c.anchor.source_quote, c.anchor.display_quote) for c in plan.comments] == [('пішов \\* додому', 'пішов * додому')]


def test_changed_since_export(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    save_manual_prose(repo, scenes[1].id, 'Зовсім інший текст.', scenes[1].revision, content_format='markdown')
    preview = preview_import(repo, story.id, content)
    item = preview.scenes[1]
    assert item.status == 'changed_since_export' and item.needs_choice and preview.choice_required
    assert item.replace_status == 'changed' and item.edits >= 1
    assert statuses(preview)[0] == 'unchanged' and preview.scenes[0].replace_status is None


def test_unknown_base(tmp_path):
    repo, story, _, content = book(tmp_path)
    export_id = read_docx(content).export_id
    (tmp_path / 'stories' / story.id / 'exports' / f'{export_id}.manifest.json').unlink()
    preview = preview_import(repo, story.id, edit(content, lambda xml: split(xml, 'пішов', tracked('пішов', 'побіг'))))
    assert statuses(preview) == ['unchanged', 'changed', 'unchanged'] and not preview.choice_required
    assert any('експорт' in warning.lower() for warning in preview.warnings)
    preview = preview_import(repo, story.id, edit(content, lambda xml: xml.replace('пішов', 'побіг')))
    item = preview.scenes[1]
    assert item.status == 'unknown_base' and item.needs_choice and preview.choice_required
    assert item.replace_status == 'changed'


def test_over_limit(tmp_path):
    long = ' '.join(f'Слово{i} друге{i}.' for i in range(450))
    repo, story, scenes, content = book(tmp_path, (TEXTS[0], long, TEXTS[2]))
    changed = edit(content, lambda xml: split(re.sub(r'друге(\d+)', r'інше\1', xml), 'Слово7 ', ranged(3, run('Слово7 '))),
                   [(3, 'Р', 'Примітка')])
    preview = preview_import(repo, story.id, changed)
    item = preview.scenes[1]
    assert item.status == 'over_limit' and (item.edits, item.comments, item.general_comments) == (0, 0, 1)
    plan = plan_of(repo, story, changed, scenes[1].id)
    assert plan.proposal is None and 'інше449' in plan.editor_text and 'Примітка' in plan.general


def test_no_prose_and_unsupported_markup(tmp_path, monkeypatch):
    repo, story, _, content = book(tmp_path, empty_scene=True)
    preview = preview_import(repo, story.id, content)
    assert statuses(preview) == ['unchanged'] * 3 + ['no_prose']
    monkeypatch.setattr(editor_import, 'roundtrip_ok', lambda prose, content_format: False)
    preview = preview_import(repo, story.id, content)
    assert statuses(preview) == ['unsupported_markup'] * 3 + ['no_prose']


def test_pending_review(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    repo.save_attempt(StageAttempt(id=new_id(), story_id=story.id, scene_id=scenes[2].id, stage='edit', state='needs_review',
                                   context={'editor_import': {'import_id': 'x'}}, partial_path='x.txt'))
    assert statuses(preview_import(repo, story.id, content)) == ['unchanged', 'unchanged', 'pending_review']


def test_overlapping_comments(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    nested = ('<w:commentRangeStart w:id="1"/><w:commentRangeStart w:id="2"/>' + run('сказала ')
              + ranged(3, run('вона')) + '<w:commentRangeEnd w:id="2"/><w:commentRangeEnd w:id="1"/>')
    changed = edit(content, lambda xml: split(xml, 'сказала вона', nested),
                   [(1, 'А', 'Перша'), (2, 'Б', 'Друга'), (3, 'В', 'Вкладена')])
    item = preview_import(repo, story.id, changed).scenes[1]
    assert (item.status, item.comments, item.general_comments) == ('comments_only', 1, 2)
    plan = plan_of(repo, story, changed, scenes[1].id)
    checked(plan)
    assert plan.comments[0].instruction == 'Редактор (А): Перша'
    assert 'Б' in plan.general and 'Друга' in plan.general and 'Вкладена' in plan.general and '«вона»' in plan.general


def test_comment_on_inserted_text_is_general(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    middle = (f'<w:del w:id="90" w:author="Р"><w:r><w:delText xml:space="preserve">пішов</w:delText></w:r></w:del>'
              f'<w:ins w:id="91" w:author="Р">{ranged(4, run("побіг"))}</w:ins>')
    changed = edit(content, lambda xml: split(xml, 'пішов', middle), [(4, 'Р', 'Нове слово')])
    item = preview_import(repo, story.id, changed).scenes[1]
    assert (item.status, item.edits, item.comments, item.general_comments) == ('changed', 1, 0, 1)
    plan = plan_of(repo, story, changed, scenes[1].id)
    checked(plan)
    assert '«побіг»' in plan.general and 'вставлено редактором' in plan.general and 'Нове слово' in plan.general


def test_comment_limits(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    ids = range(1, 106)
    inner = ''.join(f'<w:commentRangeStart w:id="{i}"/>' for i in ids) + run('сказала вона') + ''.join(
        f'<w:commentRangeEnd w:id="{i}"/>' for i in ids)
    changed = edit(content, lambda xml: split(xml, 'сказала вона', inner), [(i, 'Р', f'Примітка {i}') for i in ids])
    item = preview_import(repo, story.id, changed).scenes[1]
    assert item.comments + item.general_comments == 100 and item.dropped_comments == 5
    plan = plan_of(repo, story, changed, scenes[1].id)
    checked(plan)


def test_foreign_story_rejected(tmp_path):
    repo, story, _, content = book(tmp_path)
    foreign = edit(content, custom=lambda xml: xml.replace(story.id, 'f' * 32))
    with pytest.raises(ValueError, match='^Файл з іншого твору$'):
        preview_import(repo, story.id, foreign)
    assert not (tmp_path / 'editor-import').exists() or not list((tmp_path / 'editor-import').iterdir())


def test_draft_comments_warning(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    scene = scenes[1]
    payload = CommentPayload(general='Загальне', comments=[])
    repo.save_draft_with_comments(scene.id, 'Робоча чернетка.', 'markdown', scene.revision, 0, payload,
                                  expected_source_version_id=scene.heads.get('draft'))
    changed = edit(content, lambda xml: xml.replace('пішов', 'побіг'))
    item = preview_import(repo, story.id, changed).scenes[1]
    assert any('коментар' in warning and '1' in warning for warning in item.warnings)
    assert not any('коментар' in warning for warning in preview_import(repo, story.id, changed).scenes[0].warnings)


def test_reader_warnings_land_in_scene(tmp_path):
    repo, story, _, content = book(tmp_path)
    changed = edit(content, lambda xml: xml.replace('Вечір.', 'Вечір.</w:t></w:r><w:r><w:drawing/><w:t>'))
    preview = preview_import(repo, story.id, changed)
    assert any('абзац 1' in warning for warning in preview.scenes[2].warnings)
    assert all(not item.warnings for item in preview.scenes[:2])


def test_sweep(tmp_path):
    repo, story, _, content = book(tmp_path)
    old = preview_import(repo, story.id, content).import_id
    fresh = preview_import(repo, story.id, content).import_id
    old_path = tmp_path / 'editor-import' / f'{old}.docx'
    stamp = time.time() - 25 * 3600
    os.utime(old_path, (stamp, stamp))
    assert sweep_temp(repo, now=datetime.now(timezone.utc)) == 1
    assert not old_path.exists() and (tmp_path / 'editor-import' / f'{fresh}.docx').exists()
    assert sweep_temp(repo, now=datetime.now(timezone.utc) + timedelta(hours=25)) == 1


def test_fingerprint_changes_with_prose_head(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    first = preview_import(repo, story.id, content)
    again = preview_import(repo, story.id, content)
    assert first.fingerprint == again.fingerprint and first.import_id != again.import_id
    save_manual_prose(repo, scenes[0].id, 'Новий початок.', scenes[0].revision, content_format='markdown')
    assert preview_import(repo, story.id, content).fingerprint != first.fingerprint


TWINS = (TEXTS[0], 'Початок.\n\n— Так.\n\n— Так.', TEXTS[2])
INS_MARK = '<w:pPr><w:rPr><w:ins w:id="80" w:author="Р"/></w:rPr></w:pPr>'
DEL_MARK = '<w:pPr><w:rPr><w:del w:id="81" w:author="Р"/></w:rPr></w:pPr>'
TWIN = f'<w:p><w:r>{T}— Так.</w:t></w:r></w:p>'
FIRST = f'<w:p><w:r>{T}Початок.</w:t></w:r></w:p>'
EMPTY = '<w:p></w:p>'


def inserted_paragraph(text):
    return f'<w:p>{INS_MARK}<w:ins w:id="82" w:author="Р">{run(text)}</w:ins></w:p>'


def deleted_paragraph(text):
    inner = f'<w:del w:id="83" w:author="Р"><w:r><w:delText xml:space="preserve">{text}</w:delText></w:r></w:del>' if text else ''
    return f'<w:p>{DEL_MARK}{inner}</w:p>'


def with_comment_on_first_twin(xml):
    return xml.replace(TWIN, f'<w:p>{ranged(6, run("— Так."))}</w:p>', 1)


def drop_manifest(tmp_path, story, content):
    (tmp_path / 'stories' / story.id / 'exports' / f'{read_docx(content).export_id}.manifest.json').unlink()


@pytest.mark.parametrize('manifest', [True, False])
def test_tracked_paragraph_insertion_keeps_anchor_on_its_paragraph(tmp_path, manifest):
    repo, story, scenes, content = book(tmp_path, TWINS)
    if not manifest:
        drop_manifest(tmp_path, story, content)
    changed = edit(content, lambda xml: with_comment_on_first_twin(
        xml.replace(FIRST, FIRST + inserted_paragraph('Нове.') + inserted_paragraph(''), 1)), [(6, 'Р', 'Перше')])
    item = preview_import(repo, story.id, changed).scenes[1]
    assert (item.status, item.needs_choice, item.comments) == ('changed', False, 1)
    plan = plan_of(repo, story, changed, scenes[1].id)
    checked(plan)
    assert [(c.anchor.start, c.anchor.end) for c in plan.comments] == [(10, 16)]
    assert plan.editor_text == 'Початок.\nНове.\n\n\n— Так.\n\n— Так.'


@pytest.mark.parametrize('manifest', [True, False])
def test_tracked_paragraph_deletion_leaves_no_empty_line(tmp_path, manifest):
    repo, story, scenes, content = book(tmp_path, TWINS)
    if not manifest:
        drop_manifest(tmp_path, story, content)
    changed = edit(content, lambda xml: xml.replace(TWIN + EMPTY, deleted_paragraph('— Так.') + deleted_paragraph(''), 1))
    assert preview_import(repo, story.id, changed).scenes[1].status == 'changed'
    assert plan_of(repo, story, changed, scenes[1].id).editor_text == 'Початок.\n\n— Так.'


def test_tracked_split_and_merge_of_paragraphs(tmp_path):
    repo, story, scenes, content = book(tmp_path, TWINS)
    drop_manifest(tmp_path, story, content)
    split_first = f'<w:p>{INS_MARK}<w:r>{T}Поча</w:t></w:r></w:p><w:p><w:r>{T}ток.</w:t></w:r></w:p>'
    merged = edit(content, lambda xml: xml.replace(FIRST + EMPTY, FIRST + f'<w:p>{DEL_MARK}</w:p>', 1))
    plan = plan_of(repo, story, merged, scenes[1].id)
    assert plan.status == 'changed' and plan.editor_text == 'Початок.\n— Так.\n\n— Так.'
    split = edit(content, lambda xml: with_comment_on_first_twin(xml.replace(FIRST, split_first, 1)), [(6, 'Р', 'Перше')])
    plan = plan_of(repo, story, split, scenes[1].id)
    checked(plan)
    assert plan.status == 'changed' and plan.editor_text == 'Поча\nток.\n\n— Так.\n\n— Так.'
    assert [(c.anchor.start, c.anchor.end) for c in plan.comments] == [(10, 16)]
