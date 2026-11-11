"""PACKAGING-001: pure parts of the Store package build."""
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from storygen import packaging
from storygen.build_edition import parse_build_edition
from storygen.packaging import (appx_manifest, bundled_distributions, check_report, dependency_closure, edition_marker,
    find_makeappx, missing_licenses, package_data_manifest, package_version, pyinstaller_args, root_requirements,
    stray_data_files, third_party_notices, toc_sources, vendor_runtime_files)
from storygen.self_check import CHECK_NAMES

ROOT = Path(__file__).resolve().parents[1]
NS = {'m': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10',
      'uap': 'http://schemas.microsoft.com/appx/manifest/uap/windows10',
      'rescap': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities'}
GOOD = {'ok': True, 'frozen': True, 'edition': 'store', 'version': '0.1.0',
        'checks': [{'name': name, 'ok': True, 'detail': ''} for name in CHECK_NAMES]}


def test_edition_marker_is_what_the_application_reads():
    loaded = parse_build_edition(edition_marker('store', 'https://example.test/r', support_url='https://example.test/s'))
    assert (loaded.edition, loaded.report_url, loaded.support_url, loaded.waitlist_url) == ('store', 'https://example.test/r', 'https://example.test/s', '')


@pytest.mark.parametrize('arguments', [('store', ''), ('store', 'http://example.test/r'), ('pro', 'https://example.test/r')])
def test_edition_marker_refuses_what_the_application_would_refuse(arguments):
    with pytest.raises(ValueError):
        edition_marker(*arguments)


def test_edition_marker_is_validated_without_touching_the_disk(monkeypatch):
    import tempfile

    def no_files(*args, **kwargs):
        raise AssertionError('marker validation must not create temporary files')
    for name in ('TemporaryDirectory', 'mkdtemp', 'NamedTemporaryFile', 'mkstemp'):
        monkeypatch.setattr(tempfile, name, no_files)
    assert json.loads(edition_marker('store', 'https://example.test/r'))['edition'] == 'store'


def test_root_requirements_come_from_the_checkout():
    from packaging.requirements import Requirement
    names = {packaging._normal(Requirement(text).name) for text in root_requirements(ROOT / 'pyproject.toml')}
    assert {'pydantic', 'fastapi', 'keyring', 'pystray', 'pillow', 'tokenizers'} <= names and 'pytest' not in names and 'mcp' not in names


def test_dependency_closure_follows_markers_and_extras():
    table = {'app': ['lib[fast]', 'win-only; sys_platform == "win32"', 'never; python_version < "3"'],
             'lib': ['core', 'speedups; extra == "fast"', 'docs-tool; extra == "docs"'], 'core': [], 'speedups': [], 'win-only': []}

    def lookup(name):
        if name not in table:
            raise PackageNotFoundError(name)
        return table[name]
    expected = ['app', 'core', 'lib', 'speedups'] + (['win-only'] if sys.platform == 'win32' else [])
    assert dependency_closure(['app'], lookup=lookup) == sorted(expected)
    with pytest.raises(ValueError, match='Залежність не встановлена: ghost'):
        dependency_closure(['ghost'], lookup=lookup)


class FakeDistribution:
    def __init__(self, name, root, files=(), license_expression='MIT'):
        self.version, self.files, self._root = '1.0', list(files), root
        self.metadata = {'Name': name, 'License-Expression': license_expression}

    def locate_file(self, item):
        return self._root / str(item)


def write(root, relative, text='text'):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return relative


def test_notices_carry_name_version_licence_and_text(tmp_path):
    table = {
        'alpha': FakeDistribution('Alpha', tmp_path, [write(tmp_path, 'alpha-1.0.dist-info/licenses/LICENSE', 'Permission is hereby granted'),
                                                      write(tmp_path, 'alpha-1.0.dist-info/licenses/vendored/THIRD_PARTY', 'vendored notice'),
                                                      'alpha/__init__.py']),
        'tray': FakeDistribution('Tray', tmp_path, [write(tmp_path, 'tray-1.0.dist-info/COPYING.LGPL', 'GNU LESSER GENERAL PUBLIC LICENSE')], 'LGPL-3.0-only'),
        'tokenizers': FakeDistribution('tokenizers', tmp_path, ['tokenizers/__init__.py'], ''),
    }
    text = third_party_notices(['alpha', 'tray', 'tokenizers'], lookup=table.__getitem__, runtime_license='PYTHON SOFTWARE FOUNDATION LICENSE')
    assert 'Alpha 1.0\nLicence: MIT' in text and 'Permission is hereby granted' in text and 'vendored notice' in text
    assert 'Tray 1.0\nLicence: LGPL-3.0-only' in text and 'GNU LESSER GENERAL PUBLIC LICENSE' in text
    assert 'tokenizers 1.0\nLicence: Apache-2.0' in text and 'github.com/huggingface/tokenizers' in text
    assert 'Python runtime and the libraries distributed with it' in text and 'PYTHON SOFTWARE FOUNDATION LICENSE' in text


def test_only_real_licence_files_are_taken(tmp_path):
    files = [write(tmp_path, 'pkg/license.py', 'SOURCE CODE'), write(tmp_path, 'pkg/notice_board.py', 'SOURCE CODE'),
             write(tmp_path, 'pkg-1.0.dist-info/METADATA', 'meta'), write(tmp_path, 'pkg-1.0.dist-info/LICENSE-MIT', 'MIT TEXT'),
             write(tmp_path, 'pkg-1.0.dist-info/COPYRIGHT', 'COPYRIGHT TEXT'), write(tmp_path, 'pkg-1.0.dist-info/license.py', 'MORE SOURCE')]
    table = {'pkg': FakeDistribution('Pkg', tmp_path, files)}
    text = third_party_notices(['pkg'], lookup=table.__getitem__)
    assert 'MIT TEXT' in text and 'COPYRIGHT TEXT' in text and 'SOURCE' not in text and 'meta' not in text


def test_distribution_without_a_licence_text_stops_the_build(tmp_path):
    table = {'mystery': FakeDistribution('Mystery', tmp_path, ['mystery/__init__.py', write(tmp_path, 'mystery/license.py')], '')}
    assert missing_licenses(['mystery'], lookup=table.__getitem__) == ['mystery']
    with pytest.raises(ValueError, match='Немає тексту ліцензії для: mystery'):
        third_party_notices(['mystery'], lookup=table.__getitem__)


def test_declared_dependencies_all_have_licence_texts():
    for module in ('pystray', 'keyring', 'reportlab', 'tokenizers'):
        pytest.importorskip(module)
    names = dependency_closure(root_requirements(ROOT / 'pyproject.toml'))
    assert missing_licenses(names) == []
    assert len(third_party_notices(names)) > 20000


def test_bundled_distributions_come_from_the_freezer_records(tmp_path):
    work = tmp_path / 'work'
    site = tmp_path / 'site-packages'
    owned = {'alpha': ['alpha/__init__.py', 'alpha/_speed.pyd'], 'beta-lib': ['beta_lib/core.py'], 'unused': ['unused/__init__.py'],
             'storygen': ['storygen/__init__.py']}
    for files in owned.values():
        for relative in files:
            write(site, relative)
    stdlib = write(tmp_path, 'python/Lib/json/__init__.py')
    (work / 'Obscura').mkdir(parents=True)
    pyz = ('x.pyz', [('alpha', str(site / 'alpha/__init__.py'), 'PYMODULE'), ('json', str(tmp_path / stdlib), 'PYMODULE'),
                     ('storygen', str(site / 'storygen/__init__.py'), 'PYMODULE')])
    collect = ([('Obscura.exe', str(work / 'Obscura.exe'), 'EXECUTABLE'), ('alpha\\_speed.pyd', str(site / 'alpha/_speed.pyd'), 'EXTENSION'),
                ('beta_lib\\core.py', str(site / 'beta_lib/core.py').upper(), 'DATA')],)
    (work / 'Obscura' / 'PYZ-00.toc').write_text(repr(pyz), encoding='utf-8')
    (work / 'Obscura' / 'COLLECT-00.toc').write_text(repr(collect), encoding='utf-8')
    installed = [FakeDistribution(name, site, files) for name, files in owned.items()]
    # Bundled files decide: 'unused' is installed but not bundled; the standard library and the app itself own no notice.
    assert bundled_distributions(toc_sources(work), installed=installed) == ['alpha', 'beta-lib']
    with pytest.raises(ValueError, match='Немає записів PyInstaller'):
        toc_sources(tmp_path / 'empty')


def test_vendor_runtime_files(tmp_path):
    (tmp_path / 'ssl.py').write_text('', encoding='utf-8')
    assert vendor_runtime_files(tmp_path) == []                     # stock CPython
    (tmp_path / 'codex-rejected-cas.pem').write_text('pem', encoding='utf-8')
    assert vendor_runtime_files(tmp_path) == [tmp_path / 'codex-rejected-cas.pem']


def test_package_data_manifest_lists_tracked_data_with_digests(tmp_path):
    package = tmp_path / 'src' / 'storygen'
    write(tmp_path, 'src/storygen/web/static/i18n.json', '{"a": 1}')
    write(tmp_path, 'src/storygen/storage/migrations/001_initial.sql', 'CREATE TABLE t(x);')
    write(tmp_path, 'src/storygen/web/app.py', 'code')
    write(tmp_path, 'src/storygen/web/static/untracked-notes.txt', 'private')
    tracked = ['src/storygen/web/static/i18n.json', 'src/storygen/storage/migrations/001_initial.sql', 'src/storygen/web/app.py',
               'src/storygen/deleted-in-worktree.txt']
    manifest = package_data_manifest(tmp_path, '0.1.0', tracked)
    assert manifest == {'version': '0.1.0', 'files': {
        'storage/migrations/001_initial.sql': hashlib.sha256(b'CREATE TABLE t(x);').hexdigest(),
        'web/static/i18n.json': hashlib.sha256(b'{"a": 1}').hexdigest()}}
    frozen = tmp_path / 'frozen'
    for relative in ('web/static/i18n.json', 'storage/migrations/001_initial.sql', 'web/static/untracked-notes.txt', 'build_edition.json'):
        write(frozen, relative)
    assert stray_data_files(frozen, manifest, allowed=('build_edition.json',)) == ['web/static/untracked-notes.txt']
    with pytest.raises(ValueError, match='не знайдено файлів даних'):
        package_data_manifest(tmp_path, '0.1.0', ['src/storygen/web/app.py'])
    assert package.is_dir()


def test_pyinstaller_arguments(tmp_path):
    arguments = pyinstaller_args(tmp_path / 'entry.py', 'Obscura', tmp_path / 'dist', tmp_path / 'work', tmp_path / 'hooks', tmp_path / 'src')
    for flag in ('--noconsole', '--onedir', '--noconfirm', '--noupx'):
        assert flag in arguments
    assert '--onefile' not in arguments and '--copy-metadata' not in arguments and arguments[-1] == str(tmp_path / 'entry.py')
    pairs = list(zip(arguments, arguments[1:]))
    for pair in [('--collect-data', 'storygen'), ('--collect-submodules', 'storygen'), ('--paths', str(tmp_path / 'src')),
                 ('--hidden-import', 'keyring.backends.Windows'), ('--hidden-import', 'pystray._win32'),
                 ('--additional-hooks-dir', str(tmp_path / 'hooks')), ('--name', 'Obscura'),
                 ('--exclude-module', 'storygen.mcp'), ('--exclude-module', 'mcp'), ('--exclude-module', 'pytest'), ('--exclude-module', '_pytest')]:
        assert pair in pairs, pair


def test_pystray_hook_ships_the_lgpl_library_as_source_files():
    hook = (ROOT / packaging.HOOKS_DIR / 'hook-pystray.py').read_text(encoding='utf-8')
    assert "module_collection_mode = 'py'" in hook


def test_check_report_accepts_only_a_complete_matching_report():
    assert check_report(GOOD, 'store', '0.1.0') == []
    failed = json.loads(json.dumps(GOOD))
    failed['ok'], failed['checks'][0]['ok'], failed['checks'][0]['detail'] = False, False, 'FileNotFoundError'
    assert check_report(failed, 'store', '0.1.0') == ['перевірка tls_context: FileNotFoundError']
    assert check_report({**GOOD, 'frozen': False}, 'store', '0.1.0') == ['самоперевірку виконано не в замороженій збірці']
    assert check_report({**GOOD, 'edition': 'full'}, 'store', '0.1.0') == ['позначка видання не потрапила в збірку: очікувано store, застосунок повідомляє full']
    assert check_report(GOOD, 'store', '0.2.0') == ['версія застосунку не збігається з версією проєкту: очікувано 0.2.0, застосунок повідомляє 0.1.0']
    assert check_report({**GOOD, 'ok': False}, 'store', '0.1.0') == ['самоперевірка не пройшла']
    for broken in (None, {}, {'checks': 'x'}, [], {**GOOD, 'checks': ['tls_context']}, {**GOOD, 'checks': [{'ok': True}]}):
        assert check_report(broken, 'store', '0.1.0') == ['звіт самоперевірки відсутній або пошкоджений']


@pytest.mark.parametrize('checks', [[], GOOD['checks'][:-1], GOOD['checks'] + [GOOD['checks'][0]], list(reversed(GOOD['checks'])),
                                    GOOD['checks'][:-1] + [{'name': 'something_else', 'ok': True, 'detail': ''}]])
def test_check_report_requires_exactly_the_seven_checks(checks):
    reasons = check_report({**GOOD, 'checks': checks}, 'store', '0.1.0')
    assert len(reasons) == 1 and reasons[0].startswith('у звіті не той набір перевірок')


def test_check_report_treats_a_non_boolean_ok_as_failure():
    odd = json.loads(json.dumps(GOOD))
    odd['checks'][2]['ok'] = 'yes'
    assert check_report(odd, 'store', '0.1.0') == ['перевірка package_data: ']


@pytest.mark.parametrize('given,expected', [('0.1.0', '0.1.0.0'), ('1.2', '1.2.0.0'), ('2.0.1.0', '2.0.1.0'), ('7', '7.0.0.0'), ('65535.0.10', '65535.0.10.0')])
def test_package_version(given, expected):
    assert package_version(given) == expected


@pytest.mark.parametrize('given', ['0.2.0rc1', '1.2.3.4.5', '', '1..2', '1.-2', '١.٢', '2.0.1.5', '65536.0.0', '01.2', '1.02'])
def test_package_version_refuses_what_the_store_cannot_hold(given):
    with pytest.raises(ValueError, match='Версія пакета MSIX'):
        package_version(given)


def manifest(**overrides):
    values = dict(identity_name='Obscura.TextWriter', publisher='CN=Publisher', publisher_display_name='Publisher',
                  version='0.1.0.0', description='Local workshop for writing stories')
    return ET.fromstring(appx_manifest(**{**values, **overrides}))


def test_manifest_structure():
    root = manifest(display_name='Reserved Name')
    identity = root.find('m:Identity', NS).attrib
    assert identity == {'Name': 'Obscura.TextWriter', 'Publisher': 'CN=Publisher', 'Version': '0.1.0.0', 'ProcessorArchitecture': 'x64'}
    application = root.find('m:Applications/m:Application', NS)
    assert application.attrib['Executable'] == 'Obscura.exe' and application.attrib['EntryPoint'] == 'Windows.FullTrustApplication'
    assert [c.attrib['Name'] for c in root.findall('m:Capabilities/rescap:Capability', NS)] == ['runFullTrust']
    assert [r.attrib['Language'] for r in root.findall('m:Resources/m:Resource', NS)] == ['uk-UA', 'en-US']
    family = root.find('m:Dependencies/m:TargetDeviceFamily', NS).attrib
    assert family['Name'] == 'Windows.Desktop' and family['MinVersion'] == '10.0.19041.0'
    visual = application.find('uap:VisualElements', NS).attrib
    assert root.find('m:Properties/m:DisplayName', NS).text == visual['DisplayName'] == 'Reserved Name'
    logos = {root.find('m:Properties/m:Logo', NS).text, visual['Square150x150Logo'], visual['Square44x44Logo']}
    assert logos == {'Assets\\' + name for name in packaging.ASSETS}


def test_manifest_escapes_every_value():
    awkward = 'CN=A&B "C" <D> \'E\''
    root = manifest(publisher=awkward, publisher_display_name=awkward, description=awkward, identity_name='A&B', display_name=awkward)
    assert root.find('m:Identity', NS).attrib['Publisher'] == awkward and root.find('m:Identity', NS).attrib['Name'] == 'A&B'
    assert root.find('m:Properties/m:PublisherDisplayName', NS).text == awkward
    assert root.find('m:Applications/m:Application/uap:VisualElements', NS).attrib['Description'] == awkward


def test_package_assets_exist_with_the_declared_sizes():
    from PIL import Image
    for name, size in packaging.ASSETS.items():
        with Image.open(ROOT / 'store_build' / 'msix' / 'Assets' / name) as image:
            assert image.size == (size, size) and image.format == 'PNG'


def test_find_makeappx(tmp_path, monkeypatch):
    tool, other = tmp_path / 'makeappx.exe', tmp_path / 'other' / 'makeappx.exe'
    tool.write_bytes(b'')
    other.parent.mkdir()
    other.write_bytes(b'')
    monkeypatch.delenv('MAKEAPPX', raising=False)
    monkeypatch.setattr(packaging.shutil, 'which', lambda name: None)
    assert find_makeappx(str(tool)) == tool
    monkeypatch.setenv('MAKEAPPX', str(other))
    assert find_makeappx(None) == other and find_makeappx(str(tool)) == tool
    # A path given on purpose is never replaced by another tool found elsewhere.
    with pytest.raises(ValueError, match='не знайдено за вказаним шляхом'):
        find_makeappx(str(tmp_path / 'typo' / 'makeappx.exe'))
    monkeypatch.delenv('MAKEAPPX')
    with pytest.raises(ValueError, match='Microsoft.Windows.SDK.BuildTools'):
        find_makeappx(None)


def run_script(*arguments, cwd=None):
    return subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_store.py'), *arguments], cwd=cwd,
                          capture_output=True, encoding='utf-8', errors='replace', timeout=120)


def test_build_script_help_runs_without_side_effects(tmp_path):
    result = run_script('--help', cwd=tmp_path)
    assert result.returncode == 0 and '--report-url' in result.stdout and list(tmp_path.iterdir()) == []


def test_build_script_refuses_a_non_empty_output_folder(tmp_path):
    (tmp_path / 'keep.txt').write_text('mine', encoding='utf-8')
    result = run_script('--out', str(tmp_path), '--report-url', 'https://example.test/r', '--skip-msix')
    assert result.returncode != 0 and sorted(p.name for p in tmp_path.iterdir()) == ['keep.txt']
    assert (tmp_path / 'keep.txt').read_text(encoding='utf-8') == 'mine'


@pytest.mark.parametrize('arguments,needle', [
    (['--skip-msix'], 'report_url'),
    (['--report-url', 'https://example.test/r'], '--identity-name'),
    (['--report-url', 'https://example.test/r', '--identity-name', 'A', '--publisher', 'CN=A', '--publisher-display-name', 'A',
      '--makeappx', 'C:/no/such/makeappx.exe'], 'не знайдено за вказаним шляхом'),
])
def test_build_script_refuses_bad_arguments_before_freezing(tmp_path, arguments, needle):
    out = tmp_path / 'out'
    result = run_script('--out', str(out), *arguments)
    assert result.returncode == 1 and needle in result.stderr
    assert not out.exists() or sorted(p.name for p in out.iterdir()) == ['BUILD-FAILED.txt']
