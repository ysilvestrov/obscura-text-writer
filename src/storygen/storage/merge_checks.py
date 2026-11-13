"""MEMORY-MERGE fsck: a merge head must name a memory_merge version of its story with the same merge key.

A head for a point that no longer exists is not an issue: it is simply never used."""
import json


def check_merge_heads(report, root, stories, versions):
    from .integrity import contained_path
    for story in stories.values():
        for key, version_id in story.memory_merge_heads.items():
            ref = versions.get(version_id)
            valid = bool(ref and ref.story_id == story.id and ref.scene_id is None and ref.kind == 'memory_merge')
            if valid:
                try:
                    valid = json.loads(contained_path(root, ref.relative_path).read_text(encoding='utf-8')).get('merge_key') == key
                except (OSError, ValueError):
                    valid = False
            if not valid:
                report.add('invalid_memory_merge_head', story.id, f'Голова злиття {key} не вказує на злиття пам’яті цієї точки')
