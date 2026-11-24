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
from tests.publication.editor_import_helpers import T, edit, ranged, run, split, tracked

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
    assert plan.editor_text == 'Початок.\n\nНове.\n\n\n— Так.\n\n— Так.'


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
    # Only the empty separator paragraph was removed: Word still shows two paragraphs, so nothing changed.
    assert plan.status == 'unchanged' and plan.editor_text == 'Початок.\n\n— Так.\n\n— Так.'
    split = edit(content, lambda xml: with_comment_on_first_twin(xml.replace(FIRST, split_first, 1)), [(6, 'Р', 'Перше')])
    plan = plan_of(repo, story, split, scenes[1].id)
    checked(plan)
    assert plan.status == 'changed' and plan.editor_text == 'Поча\n\nток.\n\n— Так.\n\n— Так.'
    assert [(c.anchor.start, c.anchor.end) for c in plan.comments] == [(10, 16)]


@pytest.mark.parametrize('manifest', [True, False])
def test_tracked_paragraph_move_keeps_anchor(tmp_path, manifest):
    repo, story, scenes, content = book(tmp_path, TWINS)
    if not manifest:
        drop_manifest(tmp_path, story, content)
    moved_to = (f'<w:p><w:pPr><w:rPr><w:moveTo w:id="84" w:author="Р"/></w:rPr></w:pPr>'
                f'<w:moveTo w:id="85" w:author="Р">{run("— Так.")}</w:moveTo></w:p>')
    moved_from = (f'<w:p><w:pPr><w:rPr><w:moveFrom w:id="86" w:author="Р"/></w:rPr></w:pPr>'
                  f'<w:moveFrom w:id="87" w:author="Р">{run("— Так.")}</w:moveFrom></w:p>')

    def change(xml):
        head, tail = xml.rsplit(TWIN, 1)
        return with_comment_on_first_twin((head + moved_from + tail).replace(FIRST, FIRST + moved_to, 1))

    changed = edit(content, change, [(6, 'Р', 'Перше')])
    item = preview_import(repo, story.id, changed).scenes[1]
    assert (item.status, item.needs_choice, item.comments) == ('changed', False, 1)
    plan = plan_of(repo, story, changed, scenes[1].id)
    checked(plan)
    assert [(c.anchor.start, c.anchor.end) for c in plan.comments] == [(10, 16)]
    assert plan.editor_text == 'Початок.\n\n— Так.\n\n— Так.\n'


# --- §5: saving the import ---------------------------------------------------------------------------------------

EDITED = TEXTS[1].replace('пішов', 'побіг')


def imported(repo, story, content, changed_scenes=None):
    preview = preview_import(repo, story.id, content)
    return preview, editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, changed_scenes)


def import_attempts(repo, story, scene_id):
    return repo.list_attempts(story.id, scene_id=scene_id, context_key='editor_import')


def test_imported_proposal_is_selectable(tmp_path):
    from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
    repo, story, scenes, content = book(tmp_path)
    prose_head = scenes[1].heads['prose']
    preview, result = imported(repo, story, edit(content, lambda xml: split(xml, 'пішов', tracked('пішов', 'побіг'))))
    assert result.imported == [scenes[1].id] and result.skipped == [] and result.draft_only == []
    [attempt] = import_attempts(repo, story, scenes[1].id)
    assert attempt.run_id is None and attempt.state == 'needs_review' and attempt.stage == 'edit'
    assert attempt.context['editor_import'] == {'import_id': preview.import_id, 'export_id': preview.export_id, 'scene_index': 1}
    assert attempt.context['target_cas']['version_id'] == prose_head
    assert repo.files.read_partial(attempt.partial_path) == EDITED
    view = copyedit_preview(repo, scenes[1].id, attempt.id)
    assert view['can_apply'], view['reason']
    assert view['preview'] == EDITED and len(view['edits']) == 1
    select_copyedits(repo, scenes[1].id, attempt.id, list(range(len(view['edits']))), view['expected_revision'],
                     view['proposal_fingerprint'])
    scene = repo.get_scene(scenes[1].id)
    assert scene.heads['prose'] != prose_head and repo.read_text(scene.heads['prose']) == EDITED
    assert repo.get_attempt(attempt.id).state == 'completed'
    assert not (tmp_path / 'editor-import' / f'{preview.import_id}.docx').exists()


def comment_on_speech(content):
    return edit(content, lambda xml: split(xml, 'сказала вона', ranged(5, run('сказала вона'))), [(5, 'Редакторка', 'Точніше')])


def test_comments_only_saves_draft_and_comments_without_attempt(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    prose_head = scenes[1].heads['prose']
    _, result = imported(repo, story, comment_on_speech(content))
    assert result.imported == [scenes[1].id] and result.draft_only == []
    scene = repo.get_scene(scenes[1].id)
    assert scene.heads['prose'] == prose_head and repo.read_text(scene.heads['draft']) == TEXTS[1]
    state = repo.get_comment_state(scenes[1].id)
    notes = state['comment_set']
    assert state['source_matches_current'] and notes.source_version_id == scene.heads['draft']
    assert [(c.instruction, c.anchor.display_quote) for c in notes.comments] == [('Редактор (Редакторка): Точніше', 'сказала вона')]
    assert import_attempts(repo, story, scenes[1].id) == []
    assert repo.list_attempts(story.id) == []


def test_over_limit_saves_editor_text_as_draft(tmp_path):
    long = ' '.join(f'Слово{i} друге{i}.' for i in range(450))
    repo, story, scenes, content = book(tmp_path, (TEXTS[0], long, TEXTS[2]))
    changed = edit(content, lambda xml: split(re.sub(r'друге(\d+)', r'інше\1', xml), 'Слово7 ', ranged(3, run('Слово7 '))),
                   [(3, 'Р', 'Примітка')])
    _, result = imported(repo, story, changed)
    assert result.imported == [scenes[1].id] and result.draft_only == [scenes[1].id]
    scene = repo.get_scene(scenes[1].id)
    assert repo.read_text(scene.heads['draft']) == long.replace('друге', 'інше')
    assert repo.read_text(scene.heads['prose']) == long
    notes = repo.get_comment_state(scenes[1].id)['comment_set']
    assert notes.comments == [] and 'Примітка' in notes.general
    assert repo.list_attempts(story.id) == []


def test_whole_scene_deleted_is_skipped(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    changed = edit(content, lambda xml: xml.replace(run('Третя сцена. Вечір.'), ''))
    _, result = imported(repo, story, changed)
    assert result.imported == [] and result.skipped == [{'scene_id': scenes[2].id, 'status': 'over_limit'}]
    assert any('редактор вилучив увесь текст сцени' in w for w in result.warnings)
    assert repo.get_scene(scenes[2].id).heads.get('draft') == scenes[2].heads.get('draft')


def test_fingerprint_conflict(tmp_path):
    from storygen.domain import RevisionConflict
    repo, story, scenes, content = book(tmp_path)
    preview = preview_import(repo, story.id, edit(content, lambda xml: xml.replace('пішов', 'побіг')))
    save_manual_prose(repo, scenes[0].id, 'Новий початок.', scenes[0].revision, content_format='markdown')
    before = {scene.id: repo.get_scene(scene.id).revision for scene in scenes}
    with pytest.raises(RevisionConflict, match='Твір змінився після зведення'):
        editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)
    assert {scene.id: repo.get_scene(scene.id).revision for scene in scenes} == before
    assert repo.list_attempts(story.id) == []


def test_choice_required(tmp_path):
    from storygen.generation.copyedit_review import copyedit_preview
    repo, story, scenes, content = book(tmp_path)
    save_manual_prose(repo, scenes[1].id, 'Зовсім інший текст.', scenes[1].revision, content_format='markdown')
    preview = preview_import(repo, story.id, content)
    with pytest.raises(ValueError):
        editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)
    result = editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, 'skip')
    assert result.imported == [] and result.skipped == [{'scene_id': scenes[1].id, 'status': 'changed_since_export'}]
    assert repo.list_attempts(story.id) == []
    _, result = imported(repo, story, content, 'replace')
    assert result.imported == [scenes[1].id] and result.skipped == []
    [attempt] = import_attempts(repo, story, scenes[1].id)
    view = copyedit_preview(repo, scenes[1].id, attempt.id)
    assert view['original'] == 'Зовсім інший текст.' and view['preview'] == TEXTS[1] and view['can_apply']


def test_second_import_is_pending_review(tmp_path):
    repo, story, _, content = book(tmp_path)
    changed = edit(content, lambda xml: xml.replace('пішов', 'побіг'))
    imported(repo, story, changed)
    preview = preview_import(repo, story.id, changed)
    assert statuses(preview) == ['unchanged', 'pending_review', 'unchanged']


def test_draft_version_marked(tmp_path):
    import hashlib
    repo, story, scenes, content = book(tmp_path)
    preview, _ = imported(repo, story, edit(content, lambda xml: xml.replace('пішов', 'побіг')))
    ref = repo.get_version(repo.get_scene(scenes[1].id).heads['draft'])
    assert ref.editor_import.import_id == preview.import_id and ref.editor_import.export_id == preview.export_id
    assert ref.sha256 == hashlib.sha256(TEXTS[1].encode('utf-8')).hexdigest()
    assert ref.input_refs == [] and ref.dependency_snapshot is None


def test_cancel_removes_temp(tmp_path):
    repo, story, _, content = book(tmp_path)
    preview = preview_import(repo, story.id, content)
    path = tmp_path / 'editor-import' / f'{preview.import_id}.docx'
    assert path.exists()
    editor_import.cancel_import(repo, story.id, preview.import_id)
    assert not path.exists()
    with pytest.raises(KeyError):
        editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)
    with pytest.raises(KeyError):
        editor_import.cancel_import(repo, story.id, '../../secret')


def edit_all(content):
    return edit(content, lambda xml: xml.replace('Ранок', 'Світанок').replace('пішов', 'побіг').replace('Вечір', 'Ніч'))


def test_failed_scene_is_skipped_and_others_imported(tmp_path, monkeypatch):
    import storygen.generation.context as context
    repo, story, scenes, content = book(tmp_path)
    preview = preview_import(repo, story.id, edit_all(content))
    assert statuses(preview) == ['changed'] * 3
    original = context.make_context

    def broken(repo_, story_, scene, *args, **kwargs):
        if scene.id == scenes[1].id:
            raise RuntimeError('context failed')
        return original(repo_, story_, scene, *args, **kwargs)
    monkeypatch.setattr(context, 'make_context', broken)
    result = editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)
    assert result.imported == [scenes[0].id, scenes[2].id]
    assert result.skipped == [{'scene_id': scenes[1].id, 'status': 'changed'}]
    assert any(w.startswith(f'«{scenes[1].title}»: сцену не імпортовано') and 'context failed' in w for w in result.warnings)
    scene = repo.get_scene(scenes[1].id)  # the failed scene rolled back: draft, comments and attempt alike
    assert scene.revision == scenes[1].revision and scene.heads.get('draft') == scenes[1].heads.get('draft')
    assert repo.get_comment_state(scenes[1].id)['comment_set'] is None and import_attempts(repo, story, scenes[1].id) == []
    assert [len(import_attempts(repo, story, s.id)) for s in (scenes[0], scenes[2])] == [1, 1]


def test_scene_conflict_is_skipped_not_raised(tmp_path, monkeypatch):
    repo, story, scenes, content = book(tmp_path)
    preview = preview_import(repo, story.id, edit_all(content))
    real = repo.save_draft_with_comments

    def racing(scene_id, *args, **kwargs):
        if scene_id == scenes[1].id:  # another tab saves the scene's draft just before the import writes it
            real(scene_id, 'Чужа чернетка.', 'markdown', repo.get_scene(scene_id).revision, 0, CommentPayload(),
                 expected_source_version_id=None)
        return real(scene_id, *args, **kwargs)
    monkeypatch.setattr(repo, 'save_draft_with_comments', racing)
    result = editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)
    assert result.imported == [scenes[0].id, scenes[2].id]
    assert result.skipped == [{'scene_id': scenes[1].id, 'status': 'changed'}]
    assert repo.read_text(repo.get_scene(scenes[1].id).heads['draft']) == 'Чужа чернетка.'
    assert import_attempts(repo, story, scenes[1].id) == []


@pytest.mark.unrated_stories
def test_import_works_in_unrated_story(tmp_path):
    from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
    repo, story, scenes, content = book(tmp_path)
    assert repo.get_story(story.id).content_rating is None
    _, result = imported(repo, story, edit(content, lambda xml: xml.replace('пішов', 'побіг')))
    assert result.imported == [scenes[1].id] and result.skipped == []
    [attempt] = import_attempts(repo, story, scenes[1].id)
    view = copyedit_preview(repo, scenes[1].id, attempt.id)
    assert view['can_apply'], view['reason']
    select_copyedits(repo, scenes[1].id, attempt.id, list(range(len(view['edits']))), view['expected_revision'],
                     view['proposal_fingerprint'])
    assert repo.read_text(repo.get_scene(scenes[1].id).heads['prose']) == EDITED


def test_import_over_equal_draft_keeps_previous_version(tmp_path):
    """I-1: a draft equal to normalized(prose) still gets a new marked version; the author's notes stay with the old one."""
    repo, story, scenes, content = book(tmp_path)
    sid = scenes[1].id
    saved = repo.save_draft_with_comments(sid, TEXTS[1], 'markdown', repo.get_scene(sid).revision, 0,
                                          CommentPayload(general='Моя власна нотатка'), expected_source_version_id=None)
    old_draft, old_notes = saved['version'].id, saved['comment_set']
    dependent = repo.save_version(story.id, sid, 'memory', 'Пам’ять сцени.', [old_draft])
    preview, result = imported(repo, story, comment_on_speech(content))
    assert any('попередній версії чернетки' in w for w in preview.scenes[1].warnings)
    assert result.imported == [sid]
    scene = repo.get_scene(sid)
    new_draft = repo.get_version(scene.heads['draft'])
    assert new_draft.id != old_draft and new_draft.editor_import.import_id == preview.import_id
    assert repo.read_text(new_draft.id) == TEXTS[1]
    notes = repo.get_comment_state(sid)['comment_set']
    assert notes.source_version_id == new_draft.id and notes.general == ''
    kept = repo.get_comment_set(sid, old_notes.id)
    assert kept.source_version_id == old_draft and kept.general == 'Моя власна нотатка'
    # Identical bytes invalidate nothing: what depended on the old draft stays fresh.
    assert not repo.get_version(dependent.id).stale and not repo.get_version(scene.heads['prose']).stale


def test_failed_scene_leaves_no_orphan_files(tmp_path, monkeypatch, caplog):
    """I-2: a scene whose transaction fails removes the draft blob and the partial it wrote; fsck and backup stay clean."""
    import storygen.generation.context as context
    from storygen.storage.backup import require_integrity
    from storygen.storage.integrity import check_integrity
    repo, story, scenes, content = book(tmp_path)
    assert check_integrity(tmp_path).ok
    preview = preview_import(repo, story.id, edit_all(content))

    def broken(*args, **kwargs):
        raise ValueError('Контекст не вміщується')
    monkeypatch.setattr(context, 'make_context', broken)
    with caplog.at_level('ERROR', logger='storygen.application.editor_import'):
        result = editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)
    assert result.imported == [] and len(result.skipped) == 3
    report = check_integrity(tmp_path)
    assert report.ok, [i.code for i in report.issues]
    require_integrity(tmp_path)
    assert list((tmp_path / 'stories' / story.id).glob('runs/*/partial.txt')) == []
    assert [r for r in caplog.records if r.exc_info] and len(caplog.records) == 3


def test_concurrent_apply_creates_one_proposal(tmp_path, monkeypatch):
    """I-3: a second apply that passed the upfront pending_review check is refused inside the scene transaction."""
    from storygen.storage.integrity import check_integrity
    repo, story, scenes, content = book(tmp_path)
    changed = edit(content, lambda xml: xml.replace('пішов', 'побіг'))
    preview = preview_import(repo, story.id, changed)
    stale = editor_import._summary(repo, story.id, changed)  # request B has built its summary
    editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)  # request A finished
    draft = repo.get_scene(scenes[1].id).heads['draft']
    repo.files.write(f'editor-import/{preview.import_id}.docx', changed)
    monkeypatch.setattr(editor_import, '_summary', lambda *args: stale)
    result = editor_import.apply_import(repo, story.id, preview.import_id, preview.fingerprint, None)
    assert result.imported == [] and result.skipped == [{'scene_id': scenes[1].id, 'status': 'pending_review'}]
    assert any('Спершу вирішіть пропозицію попереднього імпорту' in w for w in result.warnings)
    assert len([a for a in import_attempts(repo, story, scenes[1].id) if a.state == 'needs_review']) == 1
    assert repo.get_scene(scenes[1].id).heads['draft'] == draft
    assert check_integrity(tmp_path).ok


def accept_all(repo, scene_id, attempt_id):
    from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
    view = copyedit_preview(repo, scene_id, attempt_id)
    assert view['can_apply'], view['reason']
    select_copyedits(repo, scene_id, attempt_id, list(range(len(view['edits']))), view['expected_revision'],
                     view['proposal_fingerprint'])


def custom_prose_editor(repo, story):
    """An editor role in prose mode with its own prose-mode prompt and a context too small for the proposal."""
    from storygen.authoring.blueprints import save_role_settings
    from storygen.prompt_contracts import expected_contract
    from storygen.providers.models import ProviderSettings, RoleSettings
    role = RoleSettings(provider=ProviderSettings(model='local-test'), edit_mode='prose', context_tokens=512,
                        max_output_tokens=256, max_input_chars=40)
    prompt = repo.save_version(story.id, None, 'prompt', 'Редагуй прозу.', [], prompt_contract=expected_contract('edit', role))
    save_role_settings(repo, story.id, 'editor', role.model_copy(update={'prompt_version_id': prompt.id}),
                       repo.get_story(story.id).revision)


@pytest.mark.parametrize('configured', [False, True])
def test_accepting_one_imported_scene_keeps_the_next_selectable(tmp_path, configured):
    repo, story, scenes, content = book(tmp_path)
    if configured:
        custom_prose_editor(repo, story)
    _, result = imported(repo, story, edit_all(content))
    assert result.imported == [s.id for s in scenes] and result.skipped == []
    [first] = import_attempts(repo, story, scenes[0].id)
    assert first.context['dependency_snapshot']['scope'] == 'patches'
    accept_all(repo, scenes[0].id, first.id)
    [second] = import_attempts(repo, story, scenes[1].id)
    accept_all(repo, scenes[1].id, second.id)
    assert repo.read_text(repo.get_scene(scenes[1].id).heads['prose']) == EDITED


def test_paragraph_split_in_word_stays_two_paragraphs(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    split_paragraph = edit(content, lambda xml: xml.replace(' Ранок', f'</w:t></w:r></w:p><w:p><w:r>{T}Ранок', 1))
    _, result = imported(repo, story, split_paragraph)
    assert result.imported == [scenes[0].id]
    [attempt] = import_attempts(repo, story, scenes[0].id)
    accept_all(repo, scenes[0].id, attempt.id)
    assert repo.read_text(repo.get_scene(scenes[0].id).heads['prose']) == 'Перша сцена.\n\nРанок був тихий.'


def test_formatting_markdown_cannot_carry_is_warned(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    middle = f'<w:r><w:rPr><w:i/></w:rPr>{T}сцена.</w:t></w:r><w:r>{T}Ранок</w:t></w:r>'
    changed = edit(content, lambda xml: split(xml, 'сцена. Ранок', middle))
    plan = plan_of(repo, story, changed, scenes[0].id)
    assert plan.status == 'changed' and plan.editor_text == 'Перша *сцена.*Ранок був тихий.'
    assert editor_import.FORMATTING_LOST in plan.warnings
    plain = plan_of(repo, story, edit(content, lambda xml: xml.replace('пішов', 'побіг')), scenes[1].id)
    assert plain.status == 'changed' and editor_import.FORMATTING_LOST not in plain.warnings
