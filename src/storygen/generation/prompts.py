from importlib.resources import files


def role_prompt(stage, settings) -> str:
    name = 'memory_delta' if stage=='memory' and settings.memory_mode=='evidence_delta' else 'copyeditor' if stage=='edit' and settings.edit_mode=='patches' else stage
    return default_prompt(name)


def default_prompt(stage: str) -> str:
    name={'draft':'writer','edit':'editor'}.get(stage,stage)
    if name not in {'prepare','brief','writer','editor','memory','memory_delta','copyeditor'}:
        raise ValueError('Невідомий етап')
    return files('storygen.generation').joinpath('resources',name+'_uk_v1.txt').read_text(encoding='utf-8')
