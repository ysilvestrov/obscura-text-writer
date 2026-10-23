"""Read-only structural traceability check; does not execute or grade tests."""
import ast
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT=Path(__file__).resolve().parents[1]
ID=r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+'
HEADER=re.compile(r'^#{3,4} (Requirement|Scenario): (.+)$')
DEFAULT_DOCS=['SPEC.MD','README.md','CONTRIBUTING.md','docs/STATUS.md',
              'docs/verification/README.md','docs/verification/manual.md','docs/adr/README.md']


def markdown_lines(text):
    """Exclude fenced code examples from normative headers and link checks."""
    fence=None
    for line in text.splitlines():
        marker=re.match(r'^\s*(`{3,}|~{3,})',line)
        if marker:
            token=marker[1]
            if fence is None:fence=token
            elif token[0]==fence[0] and len(token)>=len(fence):fence=None
            continue
        if fence is None:yield line


def spec_index(text):
    requirements={};scenarios={};errors=[];current=None;all_ids=set()
    for line in markdown_lines(text):
        match=HEADER.match(line)
        if not match:continue
        kind,title=match.groups()
        id=title.split(' — ',1)[0]
        if not re.fullmatch(ID,id):
            errors.append(f'SPEC: {kind} без сталого ID: {title}')
            current=None if kind=='Requirement' else current
            continue
        if id in all_ids:errors.append(f'SPEC: повторний ID {id}')
        all_ids.add(id)
        if kind=='Requirement':requirements[id]=[];current=id
        elif current is None:errors.append(f'SPEC: сценарій {id} без Requirement')
        else:scenarios[id]=current;requirements[current].append(id)
    for id,items in requirements.items():
        if not items:errors.append(f'SPEC: вимога {id} без Scenario')
    if not requirements:errors.append('SPEC: немає Requirements')
    return requirements,scenarios,errors


def inside(root,path):
    resolved=(root/path).resolve()
    if not resolved.is_relative_to(root.resolve()):raise ValueError('шлях поза репозиторієм')
    return resolved


def anchors(path):
    text=path.read_text(encoding='utf-8-sig');seen={};result=set()
    for line in markdown_lines(text):
        result.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)["\']',line))
        match=re.match(r'^#{1,6}\s+(.+?)\s*#*$',line)
        if not match:continue
        title=re.sub(r'<[^>]*>','',match[1]).lower()
        slug=re.sub(r'[^\w\-\s]','',title).replace(' ','-')
        count=seen.get(slug,0);seen[slug]=count+1
        result.add(slug+(f'-{count}' if count else ''))
    return result


def check_link(root,document,target):
    if target.startswith('<') and target.endswith('>'):target=target[1:-1]
    parsed=urlsplit(target)
    if parsed.scheme or parsed.netloc:return
    path=inside(root,str(Path(document).parent/unquote(parsed.path))) if parsed.path else inside(root,document)
    if not path.is_file():raise ValueError(f'файл не існує: {target}')
    if parsed.fragment and path.suffix.lower() in {'.md','.markdown'} and unquote(parsed.fragment) not in anchors(path):
        raise ValueError(f'anchor не існує: {target}')


def req_marker(node):
    return isinstance(node,ast.Call) and ast.unparse(node.func)=='pytest.mark.req'


def test_index(root,requirements):
    tests=set();markers={};errors=[]
    for path in sorted((root/'tests').rglob('test_*.py')):
        relative=path.relative_to(root).as_posix()
        try:tree=ast.parse(path.read_text(encoding='utf-8-sig'),filename=relative)
        except (SyntaxError,UnicodeError) as exc:
            errors.append(f'{relative}: не вдалося прочитати AST: {type(exc).__name__}');continue
        allowed=set()
        def visit(body,prefix=''):
            disabled=set()
            for node in body:
                if isinstance(node,(ast.Assign,ast.AnnAssign)) and isinstance(node.value,ast.Constant) and node.value.value is False:
                    for target in node.targets if isinstance(node,ast.Assign) else [node.target]:disabled.add(ast.unparse(target))
            if '__test__' in disabled:return
            for node in body:
                if isinstance(node,ast.ClassDef):
                    if node.name.startswith('Test') and node.name+'.__test__' not in disabled:visit(node.body,prefix+node.name+'::')
                elif isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                    if node.name+'.__test__' in disabled or any(ast.unparse(d.func if isinstance(d,ast.Call) else d)=='pytest.fixture' for d in node.decorator_list):continue
                    name=relative+'::'+prefix+node.name;tests.add(name)
                    for decorator in node.decorator_list:
                        if not req_marker(decorator):continue
                        allowed.add(id(decorator))
                        values=[value.value for value in decorator.args if isinstance(value,ast.Constant) and isinstance(value.value,str)]
                        if not values or len(values)!=len(decorator.args) or decorator.keywords:
                            errors.append(f'{name}: req marker вимагає буквальні ID')
                        for value in values:
                            if value not in requirements:errors.append(f'{name}: невідомий req {value}')
                            markers.setdefault(name,set()).add(value)
        visit(tree.body)
        for node in ast.walk(tree):
            if req_marker(node) and id(node) not in allowed:
                errors.append(f'{relative}: req дозволено лише на конкретній test-функції')
    return tests,markers,errors


def check(root=ROOT,*,documents=None):
    root=Path(root).resolve();errors=[]
    try:
        requirements,scenarios,errors=spec_index((root/'SPEC.MD').read_text(encoding='utf-8-sig'))
        matrix=json.loads((root/'docs/verification/traceability.json').read_text(encoding='utf-8-sig'))
    except (OSError,UnicodeError,ValueError) as exc:return [f'Не вдалося прочитати SPEC/матрицю: {exc}']
    if not isinstance(matrix,dict) or type(matrix.get('version')) is not int or matrix.get('version')!=1 or not isinstance(matrix.get('scenarios'),list):return errors+['Некоректна схема матриці']
    tests,markers,test_errors=test_index(root,requirements);errors.extend(test_errors)
    seen=set();bindings={}
    for row in matrix['scenarios']:
        if not isinstance(row,dict):errors.append('Матриця: запис не є об’єктом');continue
        id=row.get('id')
        if not isinstance(id,str):errors.append('Матриця: ID має бути текстом');continue
        if id in seen:errors.append(f'Матриця: повторний сценарій {id}')
        seen.add(id)
        if id not in scenarios:errors.append(f'Матриця: зайвий сценарій {id}')
        if row.get('requirement')!=scenarios.get(id):errors.append(f'{id}: неправильна вимога')
        if not isinstance(row.get('scope'),str) or not row['scope'].strip():errors.append(f'{id}: немає опису меж перевірки')
        refs=row.get('tests',[])
        if not isinstance(refs,list):errors.append(f'{id}: tests має бути списком');refs=[]
        for ref in refs:
            if not isinstance(ref,str) or ref not in tests:errors.append(f'{id}: конкретний тест не існує: {ref}');continue
            if isinstance(row.get('requirement'),str):bindings.setdefault(ref,set()).add(row['requirement'])
        manual=row.get('manual')
        if manual is not None:
            if not isinstance(manual,dict) or not all(isinstance(manual.get(key),str) and manual[key].strip() for key in ['procedure','reason']):
                errors.append(f'{id}: ручна перевірка потребує procedure/reason')
            else:
                try:
                    parsed=urlsplit(manual['procedure'])
                    if parsed.scheme or parsed.netloc or not parsed.path or not parsed.fragment:raise ValueError('процедура має посилатися на локальний документ і anchor')
                    if Path(parsed.path).suffix.lower() not in {'.md','.markdown'}:raise ValueError('процедура має бути Markdown-документом')
                    check_link(root,'SPEC.MD',manual['procedure'])
                except (ValueError,OSError) as exc:errors.append(f'{id}: {exc}')
        if not refs and not manual:errors.append(f'{id}: немає способу перевірки')
    for id in sorted(set(scenarios)-seen):errors.append(f'Матриця: немає сценарію {id}')
    for name,ids in markers.items():
        for id in ids-bindings.get(name,set()):errors.append(f'{name}: req {id} не має зв’язку зі сценарієм у матриці')
    docs=documents if documents is not None else DEFAULT_DOCS+[p.relative_to(root).as_posix() for p in sorted((root/'docs/adr').glob('*.md')) if p.name!='README.md']
    for document in docs:
        try:
            path=inside(root,document)
            for line in markdown_lines(path.read_text(encoding='utf-8-sig')):
                # Inline links/images; external URLs do not trigger network access.
                for target in re.findall(r'\]\((<[^>]+>|[^\s)]+)\)',line):check_link(root,document,target)
        except (OSError,UnicodeError,ValueError) as exc:errors.append(f'{document}: {exc}')
    return errors


def main():
    errors=check()
    if errors:
        print('\n'.join(errors));return 1
    print('Структура SPEC, матриця, тести, markers і локальні посилання узгоджені. Тести й ручні процедури ця команда не виконувала.')
    return 0


if __name__=='__main__':sys.exit(main())
