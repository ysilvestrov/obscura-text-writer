"""Prompt identity contracts shared by authoring, storage and generation."""
from .domain import PromptContract

MARKDOWN_PRESERVATION = '''ФОРМАТ АВТОРСЬКОГО ТЕКСТУ — MARKDOWN
Відповідь прози зберігається як Markdown. Використовуй лише абзаци, переноси,
**жирний** і _курсив_, коли вони доречні. Не додавай заголовків, HTML, зображень,
посилань або зовнішньої code fence. Зберігай чинне форматування та буквальні
escape/entity фрагменти поза потрібними правками; форматні маркери не є подіями
чи фактами твору. Для JSON-правок збережи задану JSON-схему: дослівні якорі
посилаються на raw Markdown, без видалення його маркерів перед цитуванням.'''


BRIEF_INTRODUCED_CONTRACT = '''ФОРМА ВІДПОВІДІ ЗАВДАННЯ — ОБОВ’ЯЗКОВІ ПОЛЯ
Поверни JSON з усіма полями в такому порядку:
{"objective":"...","beats":["..."],"constraints":["..."],"proposed_changes":[],"introduced":[]}
Поле introduced — ID персонажів зі складу сцени, яких головний герой уперше зустрічає й яких
представлено в цій сцені; якщо нікого — []. Не пропускай поле й закрий об’єкт після нього.'''

MARKDOWN_PRESERVATION_EN = '''AUTHOR TEXT FORMAT: MARKDOWN
The prose answer is stored as Markdown. Use only paragraphs, line breaks,
**bold** and _italics_ where they fit. Do not add headings, HTML, images,
links or an outer code fence. Keep the existing formatting and literal
escape/entity fragments outside the required edits; format markers are not events
or facts of the story. For JSON edits keep the given JSON schema: verbatim anchors
refer to the raw Markdown, without removing its markers before quoting.'''

BRIEF_INTRODUCED_CONTRACT_EN = '''BRIEF ANSWER FORMAT: REQUIRED FIELDS
Return JSON with all fields in this order:
{"objective":"...","beats":["..."],"constraints":["..."],"proposed_changes":[],"introduced":[]}
The introduced field lists IDs of characters from the scene's cast whom the protagonist meets for the first time and
who are introduced in this scene; if there are none, []. Do not skip the field, and close the object after it.'''


def markdown_preservation(language='uk') -> str:
    return MARKDOWN_PRESERVATION_EN if language=='en' else MARKDOWN_PRESERVATION


def brief_introduced_contract(language='uk') -> str:
    return BRIEF_INTRODUCED_CONTRACT_EN if language=='en' else BRIEF_INTRODUCED_CONTRACT


def expected_contract(stage, settings) -> PromptContract:
    mode = {'prepare': 'blueprint', 'brief': 'brief', 'draft': 'prose',
            'edit': settings.edit_mode, 'memory': settings.memory_mode}.get(stage)
    if mode is None:
        raise ValueError('Невідомий етап промпту')
    return PromptContract(stage=stage, mode=mode, schema_version=4 if mode == 'evidence_delta' else 1)


def compatible_contract(expected: PromptContract, actual: PromptContract | None) -> bool:
    # Memory /2 and /3 prompts cannot fill the mandatory core and thread decisions of wire v4: no older contract is compatible.
    return actual == expected


def memory_wire_version(ref) -> int:
    """Wire of the memory answer: the built-in prompt is v4, a custom prompt follows its stored (validated) contract."""
    return 4 if ref is None else ref.prompt_contract.schema_version


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
