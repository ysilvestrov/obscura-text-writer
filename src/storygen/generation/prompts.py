from ..language import load_prompt
from ..prompt_contracts import expected_contract, validate_role_prompt


def role_prompt(stage, settings, language='uk') -> str:
    if stage=='edit' and settings.edit_mode=='diff':
        return default_prompt('rewrite_editor',language)
    if stage=='memory' and settings.memory_mode=='evidence_delta':
        return load_prompt('memory_delta_v4',language)
    name = 'copyeditor' if stage=='edit' and settings.edit_mode=='patches' else stage
    return default_prompt(name,language)


def default_prompt(stage: str, language='uk') -> str:
    name={'draft':'writer','edit':'editor'}.get(stage,stage)
    if name not in {'prepare','brief','writer','editor','memory','memory_delta','copyeditor','rewrite_editor'}:
        raise ValueError('Невідомий етап')
    version={'brief':'v2','memory_delta':'v4'}.get(name,'v1')
    return load_prompt(f'{name}_{version}',language)
