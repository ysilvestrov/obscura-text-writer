from importlib.resources import files
from ..prompt_contracts import expected_contract, validate_role_prompt


def role_prompt(stage, settings) -> str:
    if stage=='edit' and settings.edit_mode=='diff':
        return default_prompt('rewrite_editor')
    if stage=='memory' and settings.memory_mode=='evidence_delta':
        return files('storygen.generation').joinpath('resources','memory_delta_uk_v4.txt').read_text(encoding='utf-8')
    name = 'memory_delta' if stage=='memory' and settings.memory_mode=='evidence_delta' else 'copyeditor' if stage=='edit' and settings.edit_mode=='patches' else stage
    return default_prompt(name)


def default_prompt(stage: str) -> str:
    name={'draft':'writer','edit':'editor'}.get(stage,stage)
    if name not in {'prepare','brief','writer','editor','memory','memory_delta','copyeditor','rewrite_editor'}:
        raise ValueError('Невідомий етап')
    version='v2' if name=='brief' else 'v1'
    return files('storygen.generation').joinpath('resources',f'{name}_uk_{version}.txt').read_text(encoding='utf-8')
