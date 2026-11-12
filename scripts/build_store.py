"""Build the Microsoft Store edition: freeze the checkout, complete the folder, let the built application check
itself, pack MSIX.

Downloads and installs nothing. PyInstaller must be installed; makeappx is needed unless --skip-msix is given.
The output folder must be empty or absent; the script writes only there (the interpreter and the freezer may still
use the system temporary folder and the byte-code cache). A finished build has BUILD-OK.json, a refused one
BUILD-FAILED.txt.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src'
sys.path.insert(0, str(SOURCE))

from storygen import packaging  # noqa: E402
from storygen.build_edition import MARKER  # noqa: E402
from storygen.build_manifest import NAME as MANIFEST  # noqa: E402
from storygen.self_check import NOTICES  # noqa: E402

NAME = 'Obscura'
ENTRY = 'from storygen.desktop import main\n\nraise SystemExit(main())\n'
FREEZE_TIMEOUT = 900
SELF_CHECK_TIMEOUT = 120


class Refused(Exception):
    pass


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, required=True, help='empty or absent output folder')
    parser.add_argument('--edition', default='store', choices=['store', 'full', 'paid'])
    parser.add_argument('--report-url', default='')
    parser.add_argument('--support-url', default='')
    parser.add_argument('--waitlist-url', default='')
    parser.add_argument('--skip-msix', action='store_true')
    parser.add_argument('--makeappx')
    parser.add_argument('--identity-name')
    parser.add_argument('--publisher')
    parser.add_argument('--publisher-display-name')
    parser.add_argument('--display-name', default='Obscura Text Writer', help='must equal the name reserved in Partner Center')
    parser.add_argument('--allow-vendor-runtime', action='store_true',
                        help='pack an MSIX although the interpreter is not a stock CPython (its extra runtime files are bundled)')
    return parser.parse_args(argv)


def tracked_package_files() -> list[str]:
    listed = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', packaging.PACKAGE_DIR], capture_output=True, timeout=60)
    if listed.returncode:
        raise Refused('не вдалося отримати перелік відстежуваних файлів (git ls-files)')
    return [item for item in listed.stdout.decode('utf-8').split('\0') if item]


def build(args, out: Path) -> dict:
    try:
        marker = packaging.edition_marker(args.edition, args.report_url, args.support_url, args.waitlist_url)
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
        version = packaging.package_version(project['version'])
        makeappx = None
        if not args.skip_msix:
            missing = [flag for flag in ('identity_name', 'publisher', 'publisher_display_name') if not getattr(args, flag)]
            if missing:
                raise Refused('для пакета MSIX потрібні --' + ', --'.join(flag.replace('_', '-') for flag in missing))
            makeappx = packaging.find_makeappx(args.makeappx)
        manifest = packaging.package_data_manifest(ROOT, project['version'], tracked_package_files())
    except ValueError as error:
        raise Refused(str(error)) from None
    vendor_files = packaging.vendor_runtime_files(Path(shutil.__file__).parent)
    if vendor_files:
        names = ', '.join(path.name for path in vendor_files)
        print(f'Увага: інтерпретатор не є звичайним CPython; у збірку буде додано його файли: {names}', file=sys.stderr)
        if not args.skip_msix and not args.allow_vendor_runtime:
            raise Refused('пакет MSIX слід збирати на офіційному CPython; щоб усе ж зібрати на цьому інтерпретаторі, '
                          'додайте --allow-vendor-runtime')
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise Refused('PyInstaller не встановлено: pip install "pyinstaller>=6,<7"') from None

    # The freezer must see the checkout as the package: its collect-data and collect-submodules resolve `storygen`
    # through the import system, and an installed copy may be another branch.
    environment = {**os.environ, 'PYTHONPATH': str(SOURCE), 'PYTHONDONTWRITEBYTECODE': '1'}
    located = subprocess.run([sys.executable, '-c', 'import storygen, sys; sys.stdout.write(storygen.__file__)'],
                             capture_output=True, encoding='utf-8', env=environment, timeout=60)
    expected = SOURCE / 'storygen' / '__init__.py'
    if located.returncode or Path(located.stdout.strip()).resolve() != expected.resolve():
        raise Refused(f'пакет storygen у середовищі збирання береться не з робочої копії: {located.stdout.strip() or located.stderr.strip()[:200]}')

    work = out / 'work'
    work.mkdir(parents=True)
    entry = work / 'obscura_entry.py'
    entry.write_text(ENTRY, encoding='utf-8')
    pyinstaller_work = work / 'pyinstaller'
    arguments = packaging.pyinstaller_args(entry, NAME, out, pyinstaller_work, ROOT / packaging.HOOKS_DIR, SOURCE)
    log = out / 'pyinstaller.log'
    try:
        with log.open('w', encoding='utf-8') as stream:
            frozen = subprocess.run([sys.executable, '-m', 'PyInstaller', *arguments], stdout=stream, stderr=subprocess.STDOUT,
                                    cwd=work, env=environment, timeout=FREEZE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Refused(f'PyInstaller не завершився за {FREEZE_TIMEOUT} с; див. {log}') from None
    if frozen.returncode:
        raise Refused(f'PyInstaller завершився з кодом {frozen.returncode}; див. {log}')

    target = out / NAME
    internal = target / '_internal'
    package = internal / 'storygen'
    if not package.is_dir():
        raise Refused(f'у збірці немає теки пакета: {package}')
    stale = sorted(path.name for path in internal.glob('storygen-*.dist-info'))
    if stale:
        raise Refused('у збірку потрапили метадані встановленої копії: ' + ', '.join(stale))
    stray = packaging.stray_data_files(package, manifest)
    if stray:
        raise Refused('у збірку потрапили файли, яких немає серед відстежуваних у робочій копії: ' + ', '.join(stray[:10]))
    (package / MARKER).write_text(marker, encoding='utf-8')
    (package / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    for extra in vendor_files:
        shutil.copyfile(extra, internal / extra.name)
    try:
        bundled = packaging.bundled_distributions(packaging.toc_sources(pyinstaller_work))
        names = sorted(set(bundled) | set(packaging.ALWAYS_NOTICED))
        runtime = Path(sys.base_prefix) / 'LICENSE.txt'
        if not runtime.is_file():
            raise Refused(f'немає ліцензії інтерпретатора: {runtime}')
        notices = packaging.third_party_notices(names, runtime_license=runtime.read_text(encoding='utf-8', errors='replace'))
    except ValueError as error:
        raise Refused(str(error)) from None
    (target / NOTICES).write_text(notices, encoding='utf-8')
    shutil.copyfile(ROOT / 'LICENSE', target / 'LICENSE.txt')

    report_path = out / 'self-check.json'
    try:
        checked = subprocess.run([str(target / f'{NAME}.exe'), '--self-check', str(report_path)], timeout=SELF_CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Refused(f'самоперевірка не завершилася за {SELF_CHECK_TIMEOUT} с (зібраний застосунок завис або показав вікно помилки)') from None
    except OSError as error:
        raise Refused(f'зібраний застосунок не запустився: {type(error).__name__}') from None
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        report = None
    reasons = packaging.check_report(report, args.edition, project['version'])
    if reasons:
        raise Refused(f'збірка не пройшла самоперевірку (код виходу {checked.returncode}): ' + '; '.join(reasons))
    files = [path for path in target.rglob('*') if path.is_file()]
    summary = {'edition': args.edition, 'version': project['version'], 'package_version': version, 'files': len(files),
               'megabytes': round(sum(path.stat().st_size for path in files) / 1e6, 1), 'data_files': len(manifest['files']),
               'components_with_notices': names, 'vendor_runtime_files': [path.name for path in vendor_files], 'msix': None}
    print(f"Збірка: {target} ({summary['files']} файлів, {summary['megabytes']} МБ), видання {args.edition}, версія {project['version']}")
    if args.skip_msix:
        return summary

    layout = out / 'msix-layout'
    shutil.copytree(target, layout)
    shutil.copytree(ROOT / 'store_build' / 'msix' / 'Assets', layout / 'Assets')
    (layout / 'AppxManifest.xml').write_text(packaging.appx_manifest(
        identity_name=args.identity_name, publisher=args.publisher, publisher_display_name=args.publisher_display_name,
        version=version, description=project['description'], display_name=args.display_name), encoding='utf-8')
    msix = out / f'{NAME}-{version}.msix'
    with (out / 'makeappx.log').open('w', encoding='utf-8', errors='replace') as stream:
        packed = subprocess.run([str(makeappx), 'pack', '/d', str(layout), '/p', str(msix), '/o'], stdout=stream,
                                stderr=subprocess.STDOUT, timeout=FREEZE_TIMEOUT)
    if packed.returncode or not msix.is_file():
        raise Refused(f"makeappx завершився з кодом {packed.returncode}; див. {out / 'makeappx.log'}")
    summary['msix'] = {'file': msix.name, 'megabytes': round(msix.stat().st_size / 1e6, 1), 'makeappx': str(makeappx)}
    print(f"Пакет: {msix} ({summary['msix']['megabytes']} МБ)")
    return summary


def main(argv=None) -> int:
    # Redirected output takes the system code page, which cannot hold these messages; a console needs no help.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and not stream.isatty() and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parse(argv)
    out = args.out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        print(f'Помилка: тека результату має бути порожньою або відсутньою: {out}', file=sys.stderr)
        return 1
    try:
        summary = build(args, out)
    except Refused as refusal:
        # The folder may hold a complete-looking build: mark it so that nobody ships it.
        if out.is_dir():
            (out / 'BUILD-FAILED.txt').write_text(str(refusal) + '\n', encoding='utf-8')
        print('Помилка: ' + str(refusal), file=sys.stderr)
        return 1
    (out / 'BUILD-OK.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
