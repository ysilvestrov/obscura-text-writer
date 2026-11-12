"""Story and prose language (STORY-LANGUAGE, #32): one place for the effective language and the prompt registry."""
from importlib.resources import files
from typing import Literal

Language = Literal['uk', 'en']

BOTH = frozenset({'uk', 'en'})
UK_ONLY = frozenset({'uk'})

# '<name>_<version>' -> (package, file name stem, languages). Files are resources/<name>_<language>_<version>.txt.
PROMPTS: dict[str, tuple[str, str, frozenset]] = {
    'prepare_v1': ('storygen.generation', 'prepare', BOTH),
    'brief_v2': ('storygen.generation', 'brief', BOTH),
    'brief_v3': ('storygen.generation', 'brief', BOTH),
    'writer_v1': ('storygen.generation', 'writer', BOTH),
    'writer_v2': ('storygen.generation', 'writer', BOTH),
    'editor_v1': ('storygen.generation', 'editor', BOTH),
    'copyeditor_v1': ('storygen.generation', 'copyeditor', BOTH),
    'rewrite_editor_v1': ('storygen.generation', 'rewrite_editor', BOTH),
    'memory_delta_v4': ('storygen.generation', 'memory_delta', BOTH),
    # Unreachable since memory_mode is always evidence_delta; kept for default_prompt('memory') compatibility.
    'memory_v1': ('storygen.generation', 'memory', UK_ONLY),
    'assisted_writer_v1': ('storygen.generation', 'assisted_writer', BOTH),
    'impact_check_v1': ('storygen.generation', 'impact_check', BOTH),
    'impact_delta_v1': ('storygen.generation', 'impact_delta', BOTH),
    'impact_part_v1': ('storygen.generation', 'impact_part', BOTH),
    'impact_part_v2': ('storygen.generation', 'impact_part', BOTH),
    'review_part_v3': ('storygen.generation', 'review_part', BOTH),
    'review_part_v4': ('storygen.generation', 'review_part', BOTH),
    'publication_metadata_v1': ('storygen.generation', 'publication_metadata', BOTH),
    # Calibrated on Ukrainian only (EVAL-002): English prose is not evaluated.
    'evaluator_v1': ('storygen.evaluation', 'evaluator', UK_ONLY),
}


def story_language(story) -> Language:
    return story.language


def prose_language(story, scene) -> Language:
    """The language prose of a scene is written in: the scene override, otherwise the story language."""
    return (scene.prose_language if scene is not None else None) or story.language


def load_prompt(key: str, language: Language) -> str:
    if key not in PROMPTS:
        raise ValueError(f'Unknown prompt {key}')
    package, name, languages = PROMPTS[key]
    if language not in languages:
        raise ValueError(f'Prompt {key} has no {language} version')
    version = key.rsplit('_', 1)[1]
    return files(package).joinpath('resources', f'{name}_{language}_{version}.txt').read_text(encoding='utf-8')
