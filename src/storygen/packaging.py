"""PACKAGING-001: the pure parts of building the Microsoft Store package; scripts/build_store.py drives them."""
import ast
import hashlib
import json
import os
import re
import shutil
import tomllib
from importlib.metadata import PackageNotFoundError, distribution, distributions
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .build_edition import parse_build_edition
from .self_check import CHECK_NAMES

EXTRAS = ('web', 'publication', 'local-tokens', 'desktop')
# Distributions whose wheel carries no licence file: SPDX id and where the text lives. A new one stops the build.
LICENSE_FALLBACKS = {'tokenizers': ('Apache-2.0', 'https://github.com/huggingface/tokenizers/blob/main/LICENSE')}
# Always named in the notices: the freezer's bootloader is part of the executable.
ALWAYS_NOTICED = ('pyinstaller',)
# Files the standard library of some interpreters reads at run time and the freezer does not collect.
VENDOR_RUNTIME_FILES = ('codex-rejected-cas.pem',)
# Not part of the Store build: the MCP bridge and anything that only tests or benchmarks use.
EXCLUDED_MODULES = ('storygen.mcp', 'mcp', 'pytest', '_pytest')
_LICENSE_NAME = re.compile(r'^(licen[cs]e|copying|notice|copyright|unlicense|authors)([-_.][^\\/]*)?$', re.IGNORECASE)
HOOKS_DIR = 'store_build/pyinstaller-hooks'
ASSETS = {'StoreLogo.png': 50, 'Square44x44Logo.png': 44, 'Square150x150Logo.png': 150}
PACKAGE_DIR = 'src/storygen'
MAX_VERSION_PART = 65535


def _normal(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def edition_marker(edition: str, report_url: str = '', support_url: str = '', waitlist_url: str = '') -> str:
    """JSON of the build edition marker, validated in memory by the same rules the application applies."""
    data = {'edition': edition, 'report_url': report_url, 'support_url': support_url, 'waitlist_url': waitlist_url}
    text = json.dumps({key: value for key, value in data.items() if value or key == 'edition'}, ensure_ascii=False)
    parse_build_edition(text)
    return text


def root_requirements(pyproject: Path, extras=EXTRAS) -> list[str]:
    """Requirements of the project itself, read from the checkout (an installed copy may be older)."""
    project = tomllib.loads(Path(pyproject).read_text(encoding='utf-8'))['project']
    optional = project.get('optional-dependencies', {})
    return list(project.get('dependencies', [])) + [item for extra in extras for item in optional[extra]]


def dependency_closure(requirements, *, lookup=None) -> list[str]:
    """Normalised names of every installed distribution the requirements pull in, markers evaluated for this system."""
    from packaging.requirements import Requirement
    lookup = lookup or (lambda name: distribution(name).requires or [])
    seen, todo = {}, [(Requirement(text), frozenset()) for text in requirements]
    while todo:
        requirement, parent_extras = todo.pop()
        environments = [{'extra': extra} for extra in parent_extras] or [{'extra': ''}]
        if requirement.marker and not any(requirement.marker.evaluate(environment) for environment in environments):
            continue
        name, extras = _normal(requirement.name), frozenset(requirement.extras)
        if name in seen and extras <= seen[name]:
            continue
        seen[name] = seen.get(name, frozenset()) | extras
        try:
            children = lookup(requirement.name)
        except PackageNotFoundError:
            raise ValueError(f'Залежність не встановлена: {requirement.name}') from None
        todo += [(Requirement(text), seen[name]) for text in children]
    return sorted(seen)


def toc_sources(work: Path) -> list[Path]:
    """Source paths of everything the freezer put into the build, read from its own records (*.toc)."""
    found = set()

    def walk(node):
        if isinstance(node, tuple) and len(node) == 3 and all(isinstance(part, str) for part in node):
            found.add(node[1])
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
    records = sorted(Path(work).rglob('*.toc'))
    if not records:
        raise ValueError(f'Немає записів PyInstaller (*.toc) у {work}')
    for record in records:
        walk(ast.literal_eval(record.read_text(encoding='utf-8')))
    return [Path(item) for item in sorted(found) if item]


def bundled_distributions(sources, *, installed=None) -> list[str]:
    """Names of the installed distributions that own the bundled files; files of no distribution are skipped
    (the interpreter itself, the checkout)."""
    owners = {}
    for dist in (installed if installed is not None else distributions()):
        for item in dist.files or []:
            owners[os.path.normcase(os.path.abspath(dist.locate_file(item)))] = _normal(dist.metadata['Name'])
    names = {owners[key] for key in (os.path.normcase(os.path.abspath(path)) for path in sources) if key in owners}
    return sorted(names - {'storygen'})


def _license_files(dist) -> list:
    """Licence files of a distribution: what lies under *.dist-info/licenses/, or carries a licence name there."""
    found = []
    for item in dist.files or []:
        parts = Path(str(item)).parts
        if not parts or not parts[0].endswith('.dist-info'):
            continue
        if (len(parts) > 2 and parts[1] == 'licenses') or (len(parts) == 2 and _LICENSE_NAME.match(parts[1]) and not parts[1].endswith('.py')):
            found.append(item)
    return found


def missing_licenses(names, *, lookup=distribution) -> list[str]:
    return [name for name in names if not _license_files(lookup(name)) and _normal(name) not in LICENSE_FALLBACKS]


def third_party_notices(names, *, lookup=distribution, runtime_license: str = '') -> str:
    missing = missing_licenses(names, lookup=lookup)
    if missing:
        raise ValueError('Немає тексту ліцензії для: ' + ', '.join(missing))
    parts = ['Obscura Text Writer — third-party notices\n',
             'This build includes the following components. Each is distributed under its own licence, reproduced below.\n']
    if runtime_license:
        parts.append(f"\n{'=' * 78}\nPython runtime and the libraries distributed with it\n{'-' * 78}\n{runtime_license.strip()}\n")
    for name in names:
        dist = lookup(name)
        declared = dist.metadata.get('License-Expression') or ((dist.metadata.get('License') or '').strip().splitlines() or [''])[0]
        fallback = LICENSE_FALLBACKS.get(_normal(name))
        header = f"\n{'=' * 78}\n{dist.metadata['Name']} {dist.version}\nLicence: {declared or (fallback[0] if fallback else 'see the text below')}\n"
        files = _license_files(dist)
        if not files:
            parts.append(header + f'The distribution carries no licence file. Licence text: {fallback[1]}\n')
            continue
        parts.append(header)
        for item in files:
            text = Path(dist.locate_file(item)).read_text(encoding='utf-8', errors='replace').strip()
            parts.append(f"{'-' * 78}\n{Path(str(item)).name}\n\n{text}\n")
    return ''.join(parts)


def vendor_runtime_files(python_lib: Path) -> list[Path]:
    """Files next to ssl.py that this interpreter's standard library needs when frozen; empty for stock CPython."""
    return [Path(python_lib) / name for name in VENDOR_RUNTIME_FILES if (Path(python_lib) / name).is_file()]


def package_data_manifest(root: Path, version: str, tracked) -> dict:
    """Version and SHA-256 of every tracked data file of the package, keyed by its path inside the package."""
    package = Path(root) / PACKAGE_DIR
    files = {}
    for item in sorted(tracked):
        path = Path(root) / item
        if path.suffix == '.py' or not path.is_file():
            continue
        files[path.relative_to(package).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not files:
        raise ValueError('У робочій копії не знайдено файлів даних пакета')
    return {'version': version, 'files': files}


def stray_data_files(frozen_package: Path, manifest: dict, allowed=()) -> list[str]:
    """Files in the frozen package folder that are not tracked data of the checkout: they must not be published."""
    known = set(manifest['files']) | set(allowed)
    return sorted(path.relative_to(frozen_package).as_posix() for path in Path(frozen_package).rglob('*')
                  if path.is_file() and path.relative_to(frozen_package).as_posix() not in known)


def pyinstaller_args(entry: Path, name: str, dist: Path, work: Path, hooks: Path, source: Path) -> list[str]:
    arguments = ['--noconfirm', '--onedir', '--noconsole', '--noupx', '--name', name, '--distpath', str(dist),
                 '--workpath', str(work), '--specpath', str(work), '--paths', str(source),
                 '--collect-data', 'storygen', '--collect-submodules', 'storygen',
                 '--hidden-import', 'keyring.backends.Windows', '--hidden-import', 'pystray._win32',
                 '--additional-hooks-dir', str(hooks)]
    for module in EXCLUDED_MODULES:
        arguments += ['--exclude-module', module]
    return arguments + [str(entry)]


def check_report(report, edition: str, version: str) -> list[str]:
    """Reasons why the built application is not fit to package; empty when it is."""
    if not isinstance(report, dict) or not isinstance(report.get('checks'), list) or \
            not all(isinstance(check, dict) and isinstance(check.get('name'), str) for check in report['checks']):
        return ['звіт самоперевірки відсутній або пошкоджений']
    reasons = [f"перевірка {check['name']}: {check.get('detail')}" for check in report['checks'] if check.get('ok') is not True]
    ran = [check['name'] for check in report['checks']]
    if ran != CHECK_NAMES:
        reasons.append('у звіті не той набір перевірок: бракує ' + (', '.join(name for name in CHECK_NAMES if name not in ran) or 'нічого')
                       + '; зайві чи повторені: ' + (', '.join(name for name in ran if name not in CHECK_NAMES or ran.count(name) > 1) or 'немає'))
    if report.get('frozen') is not True:
        reasons.append('самоперевірку виконано не в замороженій збірці')
    if report.get('edition') != edition:
        reasons.append(f"позначка видання не потрапила в збірку: очікувано {edition}, застосунок повідомляє {report.get('edition')}")
    if report.get('version') != version:
        reasons.append(f"версія застосунку не збігається з версією проєкту: очікувано {version}, застосунок повідомляє {report.get('version')}")
    if report.get('ok') is not True and not reasons:
        reasons.append('самоперевірка не пройшла')
    return reasons


def package_version(project_version: str) -> str:
    """Version of the MSIX package: three numeric parts of the project plus the fourth, which the Store reserves as 0."""
    parts = project_version.split('.') if project_version else []
    valid = 1 <= len(parts) <= 4 and all(part.isascii() and part.isdigit() and (part == '0' or not part.startswith('0'))
                                         and int(part) <= MAX_VERSION_PART for part in parts)
    if not valid or (len(parts) == 4 and parts[3] != '0'):
        raise ValueError(f'Версія пакета MSIX має складатися з чисел 0–65535, а четверта частина — бути 0: {project_version!r}')
    return '.'.join((parts + ['0', '0', '0'])[:4])


def appx_manifest(*, identity_name: str, publisher: str, publisher_display_name: str, version: str,
                  description: str, display_name: str = 'Obscura Text Writer', executable: str = 'Obscura.exe') -> str:
    q = quoteattr
    return f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name={q(identity_name)} Publisher={q(publisher)} Version={q(version)} ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>{escape(display_name)}</DisplayName>
    <PublisherDisplayName>{escape(publisher_display_name)}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="uk-UA" />
    <Resource Language="en-US" />
  </Resources>
  <Applications>
    <Application Id="Obscura" Executable={q(executable)} EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName={q(display_name)} Description={q(description)} BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png" />
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
'''


def find_makeappx(explicit: str | None = None) -> Path:
    if explicit:
        # A path given on purpose is never silently replaced by another tool found elsewhere.
        if not Path(explicit).is_file():
            raise ValueError(f'makeappx.exe не знайдено за вказаним шляхом: {explicit}')
        return Path(explicit)
    for candidate in (os.environ.get('MAKEAPPX'), shutil.which('makeappx')):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise ValueError('Не знайдено makeappx.exe. Він є в пакеті Microsoft.Windows.SDK.BuildTools (nuget.org) і в Windows SDK; '
                     'вкажіть шлях аргументом --makeappx або змінною MAKEAPPX.')
