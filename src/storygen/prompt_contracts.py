"""Prompt identity contracts shared by authoring, storage and generation."""
from .domain import PromptContract

MARKDOWN_PRESERVATION = '''ФОРМАТ АВТОРСЬКОГО ТЕКСТУ — MARKDOWN
Відповідь прози зберігається як Markdown. Використовуй лише абзаци, переноси,
**жирний** і _курсив_, коли вони доречні. Не додавай заголовків, HTML, зображень,
посилань або зовнішньої code fence. Зберігай чинне форматування та буквальні
escape/entity фрагменти поза потрібними правками; форматні маркери не є подіями
чи фактами твору. Для JSON-правок збережи задану JSON-схему: дослівні якорі
посилаються на raw Markdown, без видалення його маркерів перед цитуванням.'''


def expected_contract(stage, settings) -> PromptContract:
    mode = {'prepare': 'blueprint', 'brief': 'brief', 'draft': 'prose',
            'edit': settings.edit_mode, 'memory': settings.memory_mode}.get(stage)
    if mode is None:
        raise ValueError('Невідомий етап промпту')
    return PromptContract(stage=stage, mode=mode, schema_version=3 if mode == 'evidence_delta' else 1)


def compatible_contract(expected: PromptContract, actual: PromptContract | None) -> bool:
    # Custom memory prompts written for wire v2 keep v2 wire; nothing else has a compatible older contract.
    if expected.stage == 'memory' and expected.mode == 'evidence_delta' and actual is not None:
        return (actual.stage, actual.mode) == ('memory', 'evidence_delta') and actual.schema_version in {2, 3}
    return actual == expected


def memory_wire_version(ref) -> int:
    """Wire of the memory answer: the built-in prompt is v3, a custom prompt follows its stored contract."""
    return 3 if ref is None else ref.prompt_contract.schema_version


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
    if not compatible_contract(expected, ref.prompt_contract):
        actual = ref.prompt_contract
        raise ValueError(f'Несумісний промпт: потрібно {label}, збережено {actual.stage}/{actual.mode}/{actual.schema_version}. Адаптуйте й явно призначте промпт або поверніть стандартний.')
    return ref
