"""PACKAGING-001: the pure parts of building the Microsoft Store package; scripts/build_store.py drives them."""
import json
import os
import re
import shutil
import tomllib
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from xml.sax.saxutils import quoteattr, escape

from packaging.requirements import Requirement

from .build_edition import BuildEdition, MARKER

EXTRAS = ('web', 'publication', 'local-tokens', 'desktop')
# Distributions whose wheel carries no licence file: SPDX id and where the text lives. A new one stops the build.
LICENSE_FALLBACKS = {'tokenizers': ('Apache-2.0', 'https://github.com/huggingface/tokenizers/blob/main/LICENSE')}
# Files the standard library of some interpreters reads at run time and the freezer does not collect.
VENDOR_RUNTIME_FILES = ('codex-rejected-cas.pem',)
_LICENSE_FILE = re.compile(r'(^|[\\/])(licen[cs]e|copying|notice)[^\\/]*$', re.IGNORECASE)
HOOKS_DIR = 'store_build/pyinstaller-hooks'
ASSETS = {'StoreLogo.png': 50, 'Square44x44Logo.png': 44, 'Square150x150Logo.png': 150}


def _normal(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def edition_marker(edition: str, report_url: str = '', support_url: str = '', waitlist_url: str = '') -> str:
    """JSON of the build edition marker, validated by the same loader the application uses."""
    from .build_edition import load_build_edition
    data = {'edition': edition, 'report_url': report_url, 'support_url': support_url, 'waitlist_url': waitlist_url}
    text = json.dumps({key: value for key, value in data.items() if value or key == 'edition'}, ensure_ascii=False)
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / MARKER
        path.write_text(text, encoding='utf-8')
        loaded = load_build_edition(path)
    assert isinstance(loaded, BuildEdition)
    return text


def root_requirements(pyproject: Path, extras=EXTRAS) -> list[str]:
    """Requirements of the project itself, read from the checkout (an installed copy may be older)."""
    project = tomllib.loads(Path(pyproject).read_text(encoding='utf-8'))['project']
    optional = project.get('optional-dependencies', {})
    return list(project.get('dependencies', [])) + [item for extra in extras for item in optional[extra]]


def dependency_closure(requirements, *, lookup=None) -> list[str]:
    """Normalised names of every installed distribution the requirements pull in, markers evaluated for this system."""
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


def _license_files(dist) -> list:
    return [item for item in (dist.files or []) if _LICENSE_FILE.search(str(item))]


def missing_licenses(names, *, lookup=distribution) -> list[str]:
    return [name for name in names if not _license_files(lookup(name)) and _normal(name) not in LICENSE_FALLBACKS]


def third_party_notices(names, *, lookup=distribution) -> str:
    missing = missing_licenses(names, lookup=lookup)
    if missing:
        raise ValueError('Немає тексту ліцензії для: ' + ', '.join(missing))
    parts = ['Obscura Text Writer — third-party notices\n',
             'This build includes the following components. Each is distributed under its own licence, reproduced below.\n']
    for name in names:
        dist = lookup(name)
        declared = dist.metadata.get('License-Expression') or (dist.metadata.get('License') or '').strip().splitlines()[0:1]
        declared = declared if isinstance(declared, str) else (declared[0] if declared else '')
        fallback = LICENSE_FALLBACKS.get(_normal(name))
        header = f"\n{'=' * 78}\n{dist.metadata['Name']} {dist.version}\nLicence: {declared or (fallback[0] if fallback else 'see the text below')}\n"
        files = _license_files(dist)
        if not files:
            parts.append(header + f'The distribution carries no licence file. Licence text: {fallback[1]}\n')
            continue
        parts.append(header)
        for item in files:
            parts.append(f"{'-' * 78}\n{Path(str(item)).name}\n\n{Path(dist.locate_file(item)).read_text(encoding='utf-8', errors='replace').strip()}\n")
    return ''.join(parts)


def vendor_runtime_files(python_lib: Path) -> list[Path]:
    """Files next to ssl.py that this interpreter's standard library needs when frozen; empty for stock CPython."""
    return [Path(python_lib) / name for name in VENDOR_RUNTIME_FILES if (Path(python_lib) / name).is_file()]


def pyinstaller_args(entry: Path, name: str, dist: Path, work: Path, hooks: Path) -> list[str]:
    return ['--noconfirm', '--onedir', '--noconsole', '--name', name, '--distpath', str(dist), '--workpath', str(work),
            '--specpath', str(work), '--collect-data', 'storygen', '--collect-submodules', 'storygen', '--copy-metadata', 'storygen',
            '--hidden-import', 'keyring.backends.Windows', '--hidden-import', 'pystray._win32',
            '--additional-hooks-dir', str(hooks), str(entry)]


def check_report(report: dict, edition: str) -> list[str]:
    """Reasons why the built application is not fit to package; empty when it is."""
    if not isinstance(report, dict) or not isinstance(report.get('checks'), list):
        return ['звіт самоперевірки відсутній або пошкоджений']
    reasons = [f"перевірка {check.get('name')}: {check.get('detail')}" for check in report['checks'] if not check.get('ok')]
    if not report.get('frozen'):
        reasons.append('самоперевірку виконано не в замороженій збірці')
    if report.get('edition') != edition:
        reasons.append(f"позначка видання не потрапила в збірку: очікувано {edition}, застосунок повідомляє {report.get('edition')}")
    if not report.get('ok') and not reasons:
        reasons.append('самоперевірка не пройшла')
    return reasons


def package_version(project_version: str) -> str:
    """MSIX wants four numeric parts: 0.1.0 -> 0.1.0.0."""
    parts = project_version.split('.') if project_version else []
    if not 1 <= len(parts) <= 4 or not all(part.isascii() and part.isdigit() for part in parts):
        raise ValueError(f'Версія пакета MSIX має складатися з чисел: {project_version!r}')
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
    for candidate in (explicit, os.environ.get('MAKEAPPX'), shutil.which('makeappx')):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise ValueError('Не знайдено makeappx.exe. Він є в пакеті Microsoft.Windows.SDK.BuildTools (nuget.org) і в Windows SDK; '
                     'вкажіть шлях аргументом --makeappx або змінною MAKEAPPX.')
