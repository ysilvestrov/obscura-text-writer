"""Build the Microsoft Store edition: freeze, complete the folder, let the built application check itself, pack MSIX.

Downloads and installs nothing. PyInstaller must be installed; makeappx is needed unless --skip-msix is given.
The output folder must be empty or absent; nothing outside it is written or removed.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from storygen import packaging  # noqa: E402
from storygen.build_edition import MARKER  # noqa: E402
from storygen.self_check import NOTICES  # noqa: E402

NAME = 'Obscura'
ENTRY = 'from storygen.desktop import main\n\nraise SystemExit(main())\n'
SELF_CHECK_TIMEOUT = 120


def fail(message: str) -> int:
    print('Помилка: ' + message, file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, required=True, help='empty or absent output folder')
    parser.add_argument('--edition', default='store', choices=['store', 'full'])
    parser.add_argument('--report-url', default='')
    parser.add_argument('--support-url', default='')
    parser.add_argument('--waitlist-url', default='')
    parser.add_argument('--skip-msix', action='store_true')
    parser.add_argument('--makeappx')
    parser.add_argument('--identity-name')
    parser.add_argument('--publisher')
    parser.add_argument('--publisher-display-name')
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        return fail(f'тека результату має бути порожньою або відсутньою: {out}')
    try:
        marker = packaging.edition_marker(args.edition, args.report_url, args.support_url, args.waitlist_url)
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
        version = packaging.package_version(project['version'])
        names = packaging.dependency_closure(packaging.root_requirements(ROOT / 'pyproject.toml'))
        notices = packaging.third_party_notices(names)
        if not args.skip_msix:
            missing = [flag for flag in ('identity_name', 'publisher', 'publisher_display_name') if not getattr(args, flag)]
            if missing:
                return fail('для пакета MSIX потрібні --' + ', --'.join(flag.replace('_', '-') for flag in missing))
            makeappx = packaging.find_makeappx(args.makeappx)
    except ValueError as error:
        return fail(str(error))
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        return fail('PyInstaller не встановлено: pip install "pyinstaller>=6,<7"')

    work = out / 'work'
    work.mkdir(parents=True)
    entry = work / 'obscura_entry.py'
    entry.write_text(ENTRY, encoding='utf-8')
    arguments = packaging.pyinstaller_args(entry, NAME, out, work / 'pyinstaller', ROOT / packaging.HOOKS_DIR)
    log = out / 'pyinstaller.log'
    with log.open('w', encoding='utf-8') as stream:
        # The checkout's sources are frozen, not whatever copy of the package happens to be installed.
        frozen = subprocess.run([sys.executable, '-m', 'PyInstaller', '--paths', str(ROOT / 'src'), *arguments],
                                stdout=stream, stderr=subprocess.STDOUT, cwd=work)
    if frozen.returncode:
        return fail(f'PyInstaller завершився з кодом {frozen.returncode}; див. {log}')

    build = out / NAME
    internal = build / '_internal'
    package = internal / 'storygen'
    if not package.is_dir():
        return fail(f'у збірці немає теки пакета: {package}')
    (package / MARKER).write_text(marker, encoding='utf-8')
    for extra in packaging.vendor_runtime_files(Path(shutil.__file__).parent):
        shutil.copyfile(extra, internal / extra.name)
    (build / NOTICES).write_text(notices, encoding='utf-8')
    shutil.copyfile(ROOT / 'LICENSE', build / 'LICENSE.txt')

    report_path = out / 'self-check.json'
    try:
        subprocess.run([str(build / f'{NAME}.exe'), '--self-check', str(report_path)], timeout=SELF_CHECK_TIMEOUT)
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        report = None
    reasons = packaging.check_report(report, args.edition)
    if reasons:
        return fail('збірка не пройшла самоперевірку: ' + '; '.join(reasons))
    files = [path for path in build.rglob('*') if path.is_file()]
    print(f'Збірка: {build} ({len(files)} файлів, {sum(path.stat().st_size for path in files) / 1e6:.1f} МБ), видання {args.edition}')
    if args.skip_msix:
        return 0

    layout = out / 'msix-layout'
    shutil.copytree(build, layout)
    shutil.copytree(ROOT / 'store_build' / 'msix' / 'Assets', layout / 'Assets')
    (layout / 'AppxManifest.xml').write_text(packaging.appx_manifest(
        identity_name=args.identity_name, publisher=args.publisher, publisher_display_name=args.publisher_display_name,
        version=version, description=project['description']), encoding='utf-8')
    msix = out / f'{NAME}-{version}.msix'
    with (out / 'makeappx.log').open('w', encoding='utf-8', errors='replace') as stream:
        packed = subprocess.run([str(makeappx), 'pack', '/d', str(layout), '/p', str(msix), '/o'], stdout=stream, stderr=subprocess.STDOUT)
    if packed.returncode or not msix.is_file():
        return fail(f"makeappx завершився з кодом {packed.returncode}; див. {out / 'makeappx.log'}")
    print(f'Пакет: {msix} ({msix.stat().st_size / 1e6:.1f} МБ)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
