"""Story and prose language (STORY-LANGUAGE, #32): one place for the effective language and the prompt registry."""
from typing import Literal

Language = Literal['uk', 'en']


def story_language(story) -> Language:
    return story.language


def prose_language(story, scene) -> Language:
    """The language prose of a scene is written in: the scene override, otherwise the story language."""
    return (scene.prose_language if scene is not None else None) or story.language
