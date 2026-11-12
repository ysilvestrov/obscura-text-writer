"""Timeline summary versions and heads (#68, MEMORY-SUMMARY): CAS on the story revision, like scene heads.

A summary is a story version (`scene_id=None`, kind `timeline_summary`, JSON) whose input_refs are the selected memory of
every scene of its block (and, for an author correction, the previous summary version). The heads live in
Story.timeline_summary_heads; a new head invalidates what was built with the previous one."""
import json

from ..domain import RevisionConflict, Story

SCHEMA_VERSION = 1


def summary_payload(block, memory_version_id: str, text: str, origin: str, language: str) -> str:
    return json.dumps({'schema_version': SCHEMA_VERSION, 'block_key': block.key, 'scene_ids': list(block.scene_ids),
                       'memory_version_id': memory_version_id, 'text': text, 'origin': origin, 'language': language},
                      ensure_ascii=False)


def read_summary(view, version_id: str) -> dict:
    ref = view.get_version(version_id)
    if ref.kind != 'timeline_summary':
        raise ValueError('Це не версія підсумку хронології')
    return json.loads(view.read_text(version_id))


def check_text(text: str, limit: int) -> str:
    text = text.strip()
    if not text:
        raise ValueError('Підсумок не може бути порожнім')
    if len(text) > limit:
        raise ValueError(f'Підсумок довший за {limit} символів')
    return text


def save_summary_version(repo, story_id: str, block, memory_ids: list[str], text: str, origin: str, language: str,
                         previous_id: str | None = None, run_id: str | None = None):
    if len(memory_ids) != len(block.scene_ids) or not all(memory_ids):
        raise ValueError('Кожна сцена блоку потребує вибраної пам’яті')
    refs = list(memory_ids) + ([previous_id] if previous_id else [])
    return repo.save_version(story_id, None, 'timeline_summary', summary_payload(block, memory_ids[-1], text, origin, language), refs, run_id)


def publish_summary(repo, story_id: str, block_key: str, version_id: str, expected_revision: int) -> Story:
    from .context_view import ContextView
    from .invalidation import invalidate_in_transaction
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        if story.revision != expected_revision:
            raise RevisionConflict('Твір уже змінено; підсумок не опубліковано.')
        view = ContextView(repo, db, story_id)
        ref = view.get_version(version_id)
        if ref.story_id != story_id or ref.kind != 'timeline_summary' or ref.scene_id is not None:
            raise ValueError('Версія не є підсумком цього твору')
        if json.loads(view.read_text(version_id)).get('block_key') != block_key:
            raise ValueError('Підсумок належить іншому блоку')
        heads = dict(story.timeline_summary_heads)
        previous = heads.get(block_key)
        if previous == version_id:
            return story
        if previous is None and len(heads) >= 1000:
            raise ValueError('Забагато підсумків хронології')
        heads[block_key] = version_id
        story = story.model_copy(update={'timeline_summary_heads': heads, 'revision': story.revision + 1})
        repo._save_story(db, story)
        if previous:
            invalidate_in_transaction(repo, db, [previous], exclude={version_id})
        return story


def save_author_summary(repo, story_id: str, block_key: str, text: str, expected_version_id: str, expected_revision: int) -> Story:
    from ..memory.summary_blocks import BLOCK_LIMIT, PART_LIMIT, SummaryBlock
    story = repo.get_story(story_id)
    if story.revision != expected_revision or story.timeline_summary_heads.get(block_key) != expected_version_id:
        raise RevisionConflict('Підсумок уже змінено; оновіть панель. Ваш текст не збережено.')
    current = read_summary(repo, expected_version_id)
    part = block_key.startswith('part:')
    text = check_text(text, PART_LIMIT if part else BLOCK_LIMIT)
    previous = repo.get_version(expected_version_id)
    memory_ids = [id for id in previous.input_refs if id != expected_version_id and repo.get_version(id).kind == 'memory']
    block = SummaryBlock(block_key, '', tuple(current['scene_ids']), 0, 0, part)
    ref = save_summary_version(repo, story_id, block, memory_ids, text, 'author', current.get('language', story.language), expected_version_id)
    return publish_summary(repo, story_id, block_key, ref.id, expected_revision)
