"""Prompt identity contracts shared by authoring, storage and generation."""
from .domain import PromptContract


def expected_contract(stage, settings) -> PromptContract:
    mode = {'prepare': 'blueprint', 'brief': 'brief', 'draft': 'prose',
            'edit': settings.edit_mode, 'memory': settings.memory_mode}.get(stage)
    if mode is None:
        raise ValueError('Невідомий етап промпту')
    return PromptContract(stage=stage, mode=mode, schema_version=2 if mode == 'evidence_delta' else 1)


def validate_role_prompt(repo, story_id, stage, settings):
    expected = expected_contract(stage, settings)
    prompt_id = settings.prepare_prompt_version_id if stage == 'prepare' else settings.prompt_version_id
    if not prompt_id:
        return None  # Builtins are selected by the same stage/mode manifest.
    ref = repo.get_version(prompt_id)
    if ref.story_id != story_id or ref.kind != 'prompt' or ref.stale or not ref.complete:
        raise ValueError('Промпт не належить цьому твору або потребує оновлення')
    label = f'{expected.stage}/{expected.mode}/{expected.schema_version}'
    if ref.prompt_contract is None:
        raise ValueError('Промпт не має призначення. У налаштуваннях явно підтвердьте '+label+' або поверніть стандартний промпт.')
    if ref.prompt_contract != expected:
        actual = ref.prompt_contract
        raise ValueError(f'Несумісний промпт: потрібно {label}, збережено {actual.stage}/{actual.mode}/{actual.schema_version}. Адаптуйте й явно призначте промпт або поверніть стандартний.')
    return ref
