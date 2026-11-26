"""MANUSCRIPT-IMPORT: a new book with its scenes and their author prose from an imported manuscript, all at once (spec §4.3).

The prose files are written first. One `BEGIN IMMEDIATE` transaction then inserts the book (with its series slot), the
scenes with their `prose` heads, the version rows, the parts (`place_imported`) and the scene order, and gives every prose
version the dependency snapshot `save_manual_prose` would give it. Any error rolls the transaction back and removes the
written files, so a failed import leaves no book, scene, version row or version file (§8: an import never changes an
existing book).
"""
import hashlib
from typing import NamedTuple

from .context_view import ContextView
from ..domain import ManuscriptImportOrigin, Scene, Story, StoryCreate, VersionRef, new_id

NO_SCENES = 'Рукопис не містить жодної сцени'
EMPTY_SCENE = 'Сцена «{title}» порожня'


class ManuscriptSceneData(NamedTuple):
    title: str
    text: str
    content_format: str
    part_title: str | None
    target_words: int
    # The part the scene belongs to: a change of index starts a new part, even under the same title (`place_imported`).
    part_index: int | None = None


def publish_manuscript(repo, story: StoryCreate, scenes, origin: ManuscriptImportOrigin, structured: bool, *,
                       series: tuple[str, int] | None = None, trial: bool = False) -> tuple[Story, list[Scene]]:
    """Create the book; `series` is (series_id, number), its slot checked in the same transaction. The series start
    snapshot is not taken here: it needs committed books (`set_story_series` takes it after its transaction too)."""
    from .authoring import _require_edition_limit
    scenes = [ManuscriptSceneData(*item) for item in scenes]
    if not scenes:
        raise ValueError(NO_SCENES)
    for item in scenes:
        if not item.text.strip():
            raise ValueError(EMPTY_SCENE.format(title=item.title))
    _require_edition_limit(story.content_rating)  # as create_story, before any write
    created = Story(id=new_id(), **story.model_dump(), initial_content_rating=story.content_rating)
    if series is not None:
        created = created.model_copy(update={'series_id': series[0], 'series_number': series[1]})
    prepared = []
    written = []
    try:
        for position, item in enumerate(scenes):
            scene = Scene(id=new_id(), story_id=created.id, title=item.title, target_words=item.target_words, position=position)
            data = item.text.encode('utf-8')
            version_id = new_id()
            version = VersionRef(id=version_id, story_id=created.id, scene_id=scene.id, kind='manual',
                                 content_format=item.content_format, sha256=hashlib.sha256(data).hexdigest(),
                                 relative_path=f'stories/{created.id}/versions/{version_id}.txt', manuscript_import=origin)
            written.append(version.relative_path)
            repo.files.write(version.relative_path, data)
            scene.heads['prose'] = version_id
            scene.head_revisions['prose'] = 1
            prepared.append((scene, version, item))
        with repo.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if series is not None:
                from .series import require_book_slot
                require_book_slot(db, *series, created.id)
            db.execute('INSERT INTO stories VALUES(?,?)', (created.id, created.model_dump_json()))
            if trial:  # LONG-PROSE-TRIAL: the book and the trial marker commit together
                from datetime import datetime, timezone
                from .long_prose_trial import claim
                claim(db, 'story', created.id, [], datetime.now(timezone.utc))
            from .scene_metadata import apply_description
            active = [scene for scene, _, _ in prepared]
            for scene in active:
                apply_description(repo, db, scene, scene.beats)
                db.execute('INSERT INTO scenes VALUES(?,?,?,?)', (scene.id, created.id, scene.position, scene.model_dump_json()))
            repo._save_scene_order(db, active)
            if structured:
                # BOOK-STRUCTURE: parts of the new book, in the same transaction as its scenes (as publish_import).
                from .book_structure import place_imported
                placed = [(scene, item.part_title, None, item.part_index) for scene, _, item in prepared]
                placed_story, _, _ = place_imported(repo._get(db, 'stories', created.id, Story), active, placed, True)
                repo._save_story(db, placed_story)
            # The rows go in before the snapshots: a scene's snapshot names the prose heads (and their sha256) of the scenes
            # before it. All heads are already on the scenes, so one view of this transaction serves every snapshot.
            for _, version, _ in prepared:
                repo._insert_version_row(db, version)
            from .snapshots import author_text_snapshot
            from ..memory.forwarding import projection_policy
            from ..book.lineage import lineage_scope
            view = _ReadOnlyView(repo, db, created.id)
            with lineage_scope():  # the lineage map of the book once, not once per scene (PERF-001)
                for scene, version, _ in prepared:
                    snapshot = author_text_snapshot(view, view.peek_scene(scene.id))
                    final = version.model_copy(update={'dependency_snapshot': snapshot, 'input_refs': list(snapshot.refs),
                                                       'manual_projection_policy': projection_policy(view, scene.id)})
                    VersionRef.model_validate_json(final.model_dump_json())
                    db.execute('UPDATE versions SET payload=? WHERE id=?', (final.model_dump_json(), final.id))
                    db.executemany('INSERT INTO dependency_edges VALUES(?,?)', [(source, final.id) for source in set(final.input_refs)])
            stored = [view.peek_scene(scene.id).model_copy(deep=True) for scene in active]
    except BaseException:
        _remove(repo, created.id, written)
        raise
    return repo.get_story(created.id), stored  # the scenes as committed


class _ReadOnlyView(ContextView):
    """The view of the snapshot loop, without deep copies: `ContextView.list_scenes` copies every scene on every call and
    the author_text snapshot asks for them several times per scene, so an import of n scenes cost O(n²) copies under the
    write lock. The snapshot path only reads what it gets (previous_scenes, previous_memory_selector, scene_series_start,
    projection_policy, location_selectors), and this view is private to the import's transaction."""
    def get_story(self, id):
        return self.peek_story(id)

    def list_scenes(self, story_id):
        return self.peek_scenes(story_id)


def _remove(repo, story_id, written):
    for relative in written:
        try:
            repo.files.resolve(relative).unlink(missing_ok=True)
        except OSError:
            pass
    for relative in (f'stories/{story_id}/versions', f'stories/{story_id}'):
        try:
            repo.files.resolve(relative).rmdir()  # only when empty
        except OSError:
            pass
