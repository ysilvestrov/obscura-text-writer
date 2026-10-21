import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / 'src/storygen'


def test_storage_does_not_import_generation():
    violations = []
    for path in (ROOT / 'storage').rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and 'generation' in node.module.split('.'):
                violations.append(f'{path.name}:{node.lineno}')
            elif isinstance(node, ast.Import) and any('generation' in n.name.split('.') for n in node.names):
                violations.append(f'{path.name}:{node.lineno}')
    assert not violations, violations


def test_run_models_reexports_remain_compatible():
    from storygen import run_models
    from storygen.generation import events, worker
    assert worker.Run is run_models.Run
    assert worker.RunRequest is run_models.RunRequest
    assert events.RunEvent is run_models.RunEvent


def boundary_violations(paths):
    violations = []
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if not isinstance(node, ast.Attribute):
                continue
            repository = isinstance(node.value, ast.Name) and node.value.id == 'repo'
            repository |= isinstance(node.value, ast.Attribute) and node.value.attr == 'repo'
            if node.attr in {'execute', 'executemany', 'executescript'} or repository and (node.attr == 'db' or node.attr.startswith('_')):
                violations.append(f'{path.relative_to(ROOT)}:{node.lineno}:{node.attr}')
    return violations


def test_authoring_uses_public_repository_only():
    assert not (found := boundary_violations((ROOT / 'authoring').rglob('*.py'))), found


def test_production_uses_public_repository_only():
    paths = [p for p in ROOT.rglob('*.py') if 'storage' not in p.relative_to(ROOT).parts]
    assert not (found := boundary_violations(paths)), found
