"""MEMORY-SUMMARY fsck: a summary head must name a timeline_summary version of its story with the same block key.

A head for a block that no longer exists is not an issue: it is simply never used."""
import json


def check_summary_heads(report, root, stories, versions):
    from .integrity import contained_path
    for story in stories.values():
        for block_key, version_id in story.timeline_summary_heads.items():
            ref = versions.get(version_id)
            valid = bool(ref and ref.story_id == story.id and ref.scene_id is None and ref.kind == 'timeline_summary')
            if valid:
                try:
                    valid = json.loads(contained_path(root, ref.relative_path).read_text(encoding='utf-8')).get('block_key') == block_key
                except (OSError, ValueError):
                    valid = False
            if not valid:
                report.add('invalid_summary_head', story.id, f'Голова підсумку {block_key} не вказує на підсумок цього блоку')
