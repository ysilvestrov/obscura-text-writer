"""Execute pytest once and record fresh results, never collection counts."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT=Path(__file__).resolve().parents[1]


def validate_args(args):
    for arg in args:
        if (arg in {'--co','--collect-only','-o','--override-ini','-c'} or
                arg.startswith(('--collect-only=','--junitxml','--junit-xml','--override-ini=')) or
                arg.startswith('-o') and arg!='-o'):
            raise ValueError('Collection/config override/сторонній JUnit не є підтримуваним запуском verify.py')


def summarize(exit_code,xml):
    unknown=dict(state='unconfirmed',passed=None,failed=None,errors=None,skipped=None,reported=None)
    if xml is None:return unknown
    try:
        root=ET.fromstring(xml)
        if root.tag not in {'testsuite','testsuites'}:return unknown
        cases=list(root.iter('testcase'))
        if not cases:return unknown
        for suite in root.iter('testsuite'):
            items=list(suite.iter('testcase'))
            if 'tests' in suite.attrib and int(suite.attrib['tests'])!=len(items):return unknown
            for counter,tag in [('failures','failure'),('errors','error'),('skipped','skipped')]:
                if counter in suite.attrib and int(suite.attrib[counter])!=sum(case.find(tag) is not None for case in items):return unknown
        counts=dict(passed=0,failed=0,errors=0,skipped=0)
        for case in cases:
            outcomes=[key for tag,key in [('failure','failed'),('error','errors'),('skipped','skipped')] if case.find(tag) is not None]
            if len(outcomes)>1:return unknown
            counts[outcomes[0] if outcomes else 'passed']+=1
        executed=counts['passed']+counts['failed']+counts['errors']
        state='passed' if exit_code==0 and not counts['failed'] and not counts['errors'] and executed else 'failed' if exit_code!=0 or counts['failed'] or counts['errors'] else 'unconfirmed'
        return dict(state=state,**counts,reported=len(cases))
    except (ET.ParseError,ValueError,TypeError):return unknown


def source_identity(root):
    def git(*args):
        return subprocess.run(['git',*args],cwd=root,capture_output=True,check=True).stdout
    commit=git('rev-parse','HEAD').decode().strip()
    dirty=bool(git('status','--porcelain'))
    paths=set(git('ls-files','-z','--cached','--others','--exclude-standard').decode('utf-8').split('\0'))
    digest=hashlib.sha256()
    for name in sorted(paths):
        if not name or name=='docs/STATUS.md' or name.startswith(('artifacts/','.pytest-tmp/')):continue
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('Знімок містить шлях поза checkout')
        digest.update(name.encode('utf-8')+b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b'<deleted>')
    return dict(commit=commit,dirty=dirty,snapshot_sha256=digest.hexdigest())


def render_status(data):
    result=data['result'];labels={'passed':'ПЕРЕВІРКА ПРОЙШЛА','failed':'ПЕРЕВІРКА НЕ ПРОЙШЛА','unconfirmed':'РЕЗУЛЬТАТ НЕ ПІДТВЕРДЖЕНО'}
    counts=' · '.join(f'{key}: {result[key] if result[key] is not None else "невідомо"}' for key in ['passed','failed','errors','skipped'])
    command=json.dumps(data['command'],ensure_ascii=False)
    return f'''# Стан перевірки проєкту

**{labels[result['state']]}** — свідчення конкретного запуску, не поточного довільного стану.

- Початок (UTC): {data['started_at']}
- Завершення (UTC): {data['finished_at']}
- Базовий commit: `{data['commit']}`
- Незакомічені зміни під час перевірки: `{str(data['dirty']).lower()}`
- SHA-256 вихідного знімка: `{data['snapshot_sha256']}`
- Зміна знімка під час прогону: `{str(data.get('source_changed_during_run',False)).lower()}`
- Exit code: `{data['exit_code']}`
- Фактичні testcase результати JUnit: {counts}
- Тривалість: {data['duration_seconds']:.2f} с

Точний argv (JSON, не shell-команда):

```json
{command}
```

Результат стосується лише наведеної команди й вихідного знімка. Якщо в argv зазначено окремі файли або фільтри, це часткова перевірка. Збір (collection) не є виконанням; skipped не зараховано до passed. Відсутній або непридатний XML позначається непідтвердженим. Після зміни вихідних файлів звіт історичний. Власний STATUS і artifacts виключено зі знімка; початкова ревізія може мати dirty=true, оскільки звіт створюється до коміту.

Цей прогін не є доказом літературної якості, реальної поведінки моделей або виконання ручних процедур. Коди виходу та лічильники не замінюють аналізу тестів.

Архітектура: [SPEC.MD](../SPEC.MD). Способи перевірки: [інструкція та матриця](verification/README.md). Мотиви рішень: [ADR](adr/README.md).
'''


def run_verification(root,args,*,runner=subprocess.run,identity=None):
    validate_args(args);root=Path(root).resolve()
    inspect_after=identity is None
    identity=identity or source_identity(root)
    artifacts=root/'artifacts';artifacts.mkdir(exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='verification-',dir=artifacts))
    xml=output/'junit.xml'
    command=[sys.executable,'-m','pytest',*(args or ['-q']),f'--junitxml={xml}',f'--basetemp={output / "test-tmp"}']
    started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    env=os.environ.copy();env['PYTHONUTF8']='1';env.pop('PYTEST_ADDOPTS',None)
    with (output/'pytest.log').open('w',encoding='utf-8') as log:
        try:code=runner(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,env=env).returncode
        except KeyboardInterrupt:code=130
        except OSError as exc:code=127;log.write(type(exc).__name__+': '+str(exc))
    try:raw=xml.read_text(encoding='utf-8')
    except (OSError,UnicodeError):raw=None
    after=source_identity(root) if inspect_after else identity
    changed=after['snapshot_sha256']!=identity['snapshot_sha256'] or after['commit']!=identity['commit']
    data=dict(**identity,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),duration_seconds=time.monotonic()-clock,
              command=command,exit_code=code,result=summarize(code,raw),snapshot_after_sha256=after['snapshot_sha256'],source_changed_during_run=changed)
    if changed:data['result']['state']='unconfirmed'
    (output/'result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (root/'docs').mkdir(exist_ok=True)
    (root/'docs/STATUS.md').write_text(render_status(data),encoding='utf-8')
    print(f'Звіт: {output.relative_to(root).as_posix()}/result.json')
    print(json.dumps(data['result'],ensure_ascii=False))
    return data


def main(args=None):
    args=list(sys.argv[1:] if args is None else args)
    if args[:1]==['--']:args=args[1:]
    try:data=run_verification(ROOT,args)
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        print(f'Не вдалося виконати перевірку: {exc}',file=sys.stderr);return 2
    return 0 if data['result']['state']=='passed' else data['exit_code'] or 1


if __name__=='__main__':sys.exit(main())
