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
from storygen.packaging import (appx_manifest, bundled_distributions, check_report, copyleft_distributions, dependency_closure, edition_marker,
    bridge_pyinstaller_args, find_makeappx, missing_licenses, package_data_manifest, package_version, pyinstaller_args, root_requirements,
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
    # STORE-MCP: the package carries the MCP bridge, so its extra is part of the notices.
    assert {'pydantic', 'fastapi', 'keyring', 'pillow', 'tokenizers', 'mcp'} <= names and 'pytest' not in names and 'pystray' not in names


def test_dependency_closure_follows_markers_and_extras():
    table = {'app': ['lib[fast]', 'win-only; sys_platform == "win32"', 'never; python_version < "3"'],
             'lib': ['core', 'speedups; extra == "fast"', 'docs-tool; extra == "docs"'], 'core': [], 'speedups': [], 'win-only': []}

    def lookup(name):
        if name not in table:
            raise PackageNotFoundError(name)
        return table[name]
    expected = ['app', 'core', 'lib', 'speedups'] + (['win-only'] if sys.platform == 'win32' else [])
    assert dependency_closure(['app'], lookup=lookup) == sorted(expected)
    with pytest.raises(ValueError, match='Dependency is not installed: ghost'):
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
        'tray': FakeDistribution('Tray', tmp_path, [write(tmp_path, 'tray-1.0.dist-info/LICENSE.BSD', 'BSD 3-CLAUSE LICENSE')], 'BSD-3-Clause'),
        'tokenizers': FakeDistribution('tokenizers', tmp_path, ['tokenizers/__init__.py'], ''),
    }
    licences = tmp_path / 'licences'
    write(licences, 'tokenizers-1.0.txt', 'Apache License Version 2.0\n\nahash 0.8.12\nMIT text')
    text = third_party_notices(['alpha', 'tray', 'tokenizers'], lookup=table.__getitem__, runtime_license='PYTHON SOFTWARE FOUNDATION LICENSE',
                               licenses_dir=licences)
    assert 'Alpha 1.0\nLicence: MIT' in text and 'Permission is hereby granted' in text and 'vendored notice' in text
    assert 'Tray 1.0\nLicence: BSD-3-Clause' in text and 'BSD 3-CLAUSE LICENSE' in text
    assert 'tokenizers 1.0\n' in text and 'Apache License Version 2.0' in text and 'ahash 0.8.12\nMIT text' in text
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
    with pytest.raises(ValueError, match='No licence text for: mystery'):
        third_party_notices(['mystery'], lookup=table.__getitem__)


def test_bundled_licence_of_another_version_stops_the_build(tmp_path):
    table = {'tokenizers': FakeDistribution('tokenizers', tmp_path, ['tokenizers/__init__.py'], '')}
    write(tmp_path / 'licences', 'tokenizers-0.9.txt', 'old text')
    assert missing_licenses(['tokenizers'], lookup=table.__getitem__, licenses_dir=tmp_path / 'licences') == ['tokenizers']
    with pytest.raises(ValueError, match='No licence text for: tokenizers 1.0'):
        third_party_notices(['tokenizers'], lookup=table.__getitem__, licenses_dir=tmp_path / 'licences')


def test_declared_dependencies_all_have_licence_texts():
    for module in ('keyring', 'reportlab', 'tokenizers'):
        pytest.importorskip(module)
    names = dependency_closure(root_requirements(ROOT / 'pyproject.toml'))
    licences = ROOT / packaging.BUNDLED_LICENSES
    assert missing_licenses(names, licenses_dir=licences) == []
    assert len(third_party_notices(names, licenses_dir=licences)) > 20000


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
    with pytest.raises(ValueError, match='No PyInstaller records'):
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
    with pytest.raises(ValueError, match='No package data files found'):
        package_data_manifest(tmp_path, '0.1.0', ['src/storygen/web/app.py'])
    assert package.is_dir()


def test_pyinstaller_arguments(tmp_path):
    arguments = pyinstaller_args(tmp_path / 'entry.py', 'Obscura', tmp_path / 'dist', tmp_path / 'work', tmp_path / 'src')
    for flag in ('--noconsole', '--onedir', '--noconfirm', '--noupx'):
        assert flag in arguments
    assert '--onefile' not in arguments and '--copy-metadata' not in arguments and arguments[-1] == str(tmp_path / 'entry.py')
    pairs = list(zip(arguments, arguments[1:]))
    for pair in [('--collect-data', 'storygen'), ('--collect-submodules', 'storygen'), ('--paths', str(tmp_path / 'src')),
                 ('--hidden-import', 'keyring.backends.Windows'),
                 ('--name', 'Obscura'),
                 ('--exclude-module', 'storygen.mcp'), ('--exclude-module', 'mcp'), ('--exclude-module', 'pytest'), ('--exclude-module', '_pytest')]:
        assert pair in pairs, pair


@pytest.mark.req('STORE-MCP-001')
def test_bridge_is_frozen_as_a_console_exe_with_its_own_contents(tmp_path):
    arguments = bridge_pyinstaller_args(tmp_path / 'bridge.py', tmp_path / 'dist', tmp_path / 'work', tmp_path / 'src')
    pairs = list(zip(arguments, arguments[1:]))
    for pair in [('--name', packaging.BRIDGE_NAME), ('--contents-directory', packaging.BRIDGE_CONTENTS),
                 ('--hidden-import', 'storygen.mcp.bridge'), ('--paths', str(tmp_path / 'src'))]:
        assert pair in pairs, pair
    assert packaging.BRIDGE_NAME == 'obscura-mcp' and packaging.BRIDGE_CONTENTS != '_internal'
    assert '--onedir' in arguments and '--noconsole' not in arguments and '--windowed' not in arguments
    excluded = {value for flag, value in pairs if flag == '--exclude-module'}
    assert 'storygen.mcp' not in excluded and 'mcp' not in excluded and 'pytest' in excluded
    assert arguments[-1] == str(tmp_path / 'bridge.py')


@pytest.mark.req('STORE-MCP-001')
def test_main_exe_still_excludes_the_bridge(tmp_path):
    arguments = pyinstaller_args(tmp_path / 'entry.py', 'Obscura', tmp_path / 'dist', tmp_path / 'work', tmp_path / 'src')
    pairs = list(zip(arguments, arguments[1:]))
    assert ('--exclude-module', 'storygen.mcp') in pairs and ('--exclude-module', 'mcp') in pairs


def test_no_tray_library_in_the_build(tmp_path):
    arguments = pyinstaller_args(tmp_path / 'entry.py', 'Obscura', tmp_path / 'dist', tmp_path / 'work', tmp_path / 'src')
    assert not [value for value in arguments if 'pystray' in value or 'hooks' in value]
    assert not (ROOT / 'store_build' / 'pyinstaller-hooks').exists()


class MetadataDistribution:
    """Real metadata shape: an email.Message with repeated Classifier headers."""
    def __init__(self, name, **headers):
        from email.message import Message
        self.metadata = Message()
        self.metadata['Name'] = name
        for key, values in headers.items():
            for value in values if isinstance(values, list) else [values]:
                self.metadata[key.replace('_', '-')] = value


def test_copyleft_is_found_by_expression_licence_or_classifier():
    table = {
        'gpl': MetadataDistribution('gpl', License_Expression='GPL-3.0-or-later'),
        'lgpl-text': MetadataDistribution('lgpl-text', License='GNU LGPL v3'),
        'lgpl-classifier': MetadataDistribution('lgpl-classifier', Classifier=['Programming Language :: Python',
                                                'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)']),
        'mit': MetadataDistribution('mit', License_Expression='MIT', Classifier=['License :: OSI Approved :: MIT License']),
        'bare': MetadataDistribution('bare'),
    }
    assert copyleft_distributions(list(table), lookup=table.__getitem__) == ['gpl', 'lgpl-text', 'lgpl-classifier']


def _exception_distribution(name, texts):
    licence = [text for text in texts if not text.startswith('License ::')]
    return MetadataDistribution(name, License=licence[0] if licence else None,
                                Classifier=[text for text in texts if text.startswith('License ::')])


PYINSTALLER_LICENCES = {'GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute '
                        'non-free programs (including commercial ones)',
                        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)'}
HOOKS_LICENCES = {'License :: OSI Approved :: Apache Software License',
                  'License :: OSI Approved :: GNU General Public License v2 (GPLv2)'}


def test_copyleft_exceptions_pass_only_with_the_exact_declared_licence():
    # Literal metadata as reviewed (probe П7), not read back from the table under test.
    assert packaging.COPYLEFT_EXCEPTIONS['pyinstaller'][0] == PYINSTALLER_LICENCES
    assert packaging.COPYLEFT_EXCEPTIONS['pyinstaller-hooks-contrib'][0] == HOOKS_LICENCES
    pyi, hooks = PYINSTALLER_LICENCES, HOOKS_LICENCES
    table = {
        'pyinstaller': _exception_distribution('pyinstaller', pyi),
        'pyinstaller-hooks-contrib': _exception_distribution('pyinstaller-hooks-contrib', hooks),
        'PyInstaller_Hooks.Contrib': _exception_distribution('PyInstaller_Hooks.Contrib', hooks),
    }
    assert copyleft_distributions(list(table), lookup=table.__getitem__) == []


def test_copyleft_exception_with_changed_licence_is_refused():
    hooks = set(packaging.COPYLEFT_EXCEPTIONS['pyinstaller-hooks-contrib'][0]) | {'License :: OSI Approved :: GNU General Public License v3 (GPLv3)'}
    table = {'pyinstaller': MetadataDistribution('pyinstaller', License='GPL-3.0-only'),
             'pyinstaller-hooks-contrib': _exception_distribution('pyinstaller-hooks-contrib', hooks)}
    assert copyleft_distributions(list(table), lookup=table.__getitem__) == ['pyinstaller', 'pyinstaller-hooks-contrib']


def test_copyleft_exception_with_a_non_gpl_or_missing_licence_is_refused():
    table = {'pyinstaller': MetadataDistribution('pyinstaller', License='MIT'),
             'pyinstaller-hooks-contrib': MetadataDistribution('pyinstaller-hooks-contrib')}
    assert copyleft_distributions(list(table), lookup=table.__getitem__) == ['pyinstaller', 'pyinstaller-hooks-contrib']


def test_copyleft_exception_table_names_a_reason_for_each_entry():
    assert set(packaging.COPYLEFT_EXCEPTIONS) == {'pyinstaller', 'pyinstaller-hooks-contrib'}
    assert all(reason.strip() for _, reason in packaging.COPYLEFT_EXCEPTIONS.values())


def test_installed_freezer_matches_the_exception_table():
    pytest.importorskip('PyInstaller')
    assert copyleft_distributions(['pyinstaller', 'pyinstaller-hooks-contrib']) == []


def test_copyleft_distribution_stops_the_notices(tmp_path):
    table = {'tray': FakeDistribution('Tray', tmp_path, [write(tmp_path, 'tray-1.0.dist-info/COPYING', 'text')], 'LGPL-3.0-only')}
    with pytest.raises(ValueError, match='GPL-family.*tray'):
        third_party_notices(['tray'], lookup=table.__getitem__)


def test_build_dependencies_have_no_copyleft():
    for module in ('keyring', 'reportlab', 'tokenizers'):
        pytest.importorskip(module)
    assert copyleft_distributions(dependency_closure(root_requirements(ROOT / 'pyproject.toml'))) == []


def test_check_report_accepts_only_a_complete_matching_report():
    assert check_report(GOOD, 'store', '0.1.0') == []
    failed = json.loads(json.dumps(GOOD))
    failed['ok'], failed['checks'][0]['ok'], failed['checks'][0]['detail'] = False, False, 'FileNotFoundError'
    assert check_report(failed, 'store', '0.1.0') == ['check tls_context: FileNotFoundError']
    assert check_report({**GOOD, 'frozen': False}, 'store', '0.1.0') == ['the self-check did not run in a frozen build']
    assert check_report({**GOOD, 'edition': 'full'}, 'store', '0.1.0') == ['the edition mark did not reach the build: expected store, the app reports full']
    assert check_report(GOOD, 'store', '0.2.0') == ['the app version does not match the project version: expected 0.2.0, the app reports 0.1.0']
    assert check_report({**GOOD, 'ok': False}, 'store', '0.1.0') == ['the self-check failed']
    for broken in (None, {}, {'checks': 'x'}, [], {**GOOD, 'checks': ['tls_context']}, {**GOOD, 'checks': [{'ok': True}]}):
        assert check_report(broken, 'store', '0.1.0') == ['the self-check report is missing or damaged']


@pytest.mark.parametrize('checks', [[], GOOD['checks'][:-1], GOOD['checks'] + [GOOD['checks'][0]], list(reversed(GOOD['checks'])),
                                    GOOD['checks'][:-1] + [{'name': 'something_else', 'ok': True, 'detail': ''}]])
def test_check_report_requires_exactly_the_seven_checks(checks):
    reasons = check_report({**GOOD, 'checks': checks}, 'store', '0.1.0')
    assert len(reasons) == 1 and reasons[0].startswith('the report has the wrong set of checks')


def test_check_report_treats_a_non_boolean_ok_as_failure():
    odd = json.loads(json.dumps(GOOD))
    odd['checks'][2]['ok'] = 'yes'
    assert check_report(odd, 'store', '0.1.0') == ['check package_data: ']


@pytest.mark.parametrize('given,expected', [('0.1.0', '0.1.0.0'), ('1.2', '1.2.0.0'), ('2.0.1.0', '2.0.1.0'), ('7', '7.0.0.0'), ('65535.0.10', '65535.0.10.0')])
def test_package_version(given, expected):
    assert package_version(given) == expected


@pytest.mark.parametrize('given', ['0.2.0rc1', '1.2.3.4.5', '', '1..2', '1.-2', '١.٢', '2.0.1.5', '65536.0.0', '01.2', '1.02'])
def test_package_version_refuses_what_the_store_cannot_hold(given):
    with pytest.raises(ValueError, match='The MSIX package version'):
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


UAP3 = 'http://schemas.microsoft.com/appx/manifest/uap/windows10/3'
DESKTOP = 'http://schemas.microsoft.com/appx/manifest/desktop/windows10'


@pytest.mark.req('STORE-MCP-001')
def test_manifest_declares_the_bridge_alias():
    root = manifest()
    extension = root.find('m:Applications/m:Application/m:Extensions/uap3:Extension', {**NS, 'uap3': UAP3})
    assert extension.attrib == {'Category': 'windows.appExecutionAlias', 'Executable': 'obscura-mcp.exe',
                                'EntryPoint': 'Windows.FullTrustApplication'}
    aliases = extension.findall('uap3:AppExecutionAlias/desktop:ExecutionAlias', {'uap3': UAP3, 'desktop': DESKTOP})
    assert [alias.attrib['Alias'] for alias in aliases] == ['obscura-mcp.exe']


@pytest.mark.req('STORE-MCP-001')
def test_manifest_without_bridge_has_no_alias():
    root = manifest(bridge_executable=None)
    assert root.find('m:Applications/m:Application/m:Extensions', NS) is None


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
            colours = image.convert('RGBA').getcolors(maxcolors=size * size)
            assert len(colours) > 8, f'{name}: placeholder, not the emblem'


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
    with pytest.raises(ValueError, match='not found at the given path'):
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
    assert 'paid' in result.stdout


def test_build_script_refuses_a_non_empty_output_folder(tmp_path):
    (tmp_path / 'keep.txt').write_text('mine', encoding='utf-8')
    result = run_script('--out', str(tmp_path), '--report-url', 'https://example.test/r', '--skip-msix')
    assert result.returncode != 0 and sorted(p.name for p in tmp_path.iterdir()) == ['keep.txt']
    assert (tmp_path / 'keep.txt').read_text(encoding='utf-8') == 'mine'


@pytest.mark.parametrize('arguments,needle', [
    (['--skip-msix'], 'report_url'),
    (['--report-url', 'https://example.test/r'], '--identity-name'),
    (['--report-url', 'https://example.test/r', '--identity-name', 'A', '--publisher', 'CN=A', '--publisher-display-name', 'A',
      '--makeappx', 'C:/no/such/makeappx.exe'], 'not found at the given path'),
])
def test_build_script_refuses_bad_arguments_before_freezing(tmp_path, arguments, needle):
    out = tmp_path / 'out'
    result = run_script('--out', str(out), *arguments)
    assert result.returncode == 1 and needle in result.stderr
    assert not out.exists() or sorted(p.name for p in out.iterdir()) == ['BUILD-FAILED.txt']


def _load_build_store():
    import importlib.util
    spec = importlib.util.spec_from_file_location('build_store_under_test', ROOT / 'scripts' / 'build_store.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin_tree(tmp_path):
    root = tmp_path / 'integrations' / 'claude'
    files = {
        '.claude-plugin/marketplace.json': '{}',
        'obscura/.claude-plugin/plugin.json': '{"name": "obscura"}',
        'obscura/shared/rules.md': 'rules',
        'obscura/skills/start-story/SKILL.md': '---\nname: start-story\n---\nSee ${CLAUDE_PLUGIN_ROOT}/shared/rules.md\n',
        'obscura/evals/x.json': '{}',
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding='utf-8')
    return root, sorted(files)


def test_plugin_files_are_tracked_user_files_only(plugin_tree):
    root, tracked = plugin_tree
    (root / 'obscura/skills/start-story/draft.tmp').write_text('stray', encoding='utf-8')
    assert packaging.plugin_files(root, tracked) == ['.claude-plugin/marketplace.json', 'obscura/.claude-plugin/plugin.json',
                                                     'obscura/shared/rules.md', 'obscura/skills/start-story/SKILL.md']


def test_plugin_files_refuse_a_plugin_without_manifest(plugin_tree):
    root, tracked = plugin_tree
    (root / 'obscura/.claude-plugin/plugin.json').unlink()
    with pytest.raises(ValueError, match='plugin.json'):
        packaging.plugin_files(root, [rel for rel in tracked if not rel.endswith('plugin.json')])


def test_plugin_files_refuse_a_cross_skill_reference(plugin_tree):
    root, tracked = plugin_tree
    skill = root / 'obscura/skills/draft-scene/SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('Use ${CLAUDE_PLUGIN_ROOT}/skills/start-story/SKILL.md\n', encoding='utf-8')
    with pytest.raises(ValueError, match='draft-scene'):
        packaging.plugin_files(root, tracked + ['obscura/skills/draft-scene/SKILL.md'])


def test_repository_plugin_files_hold_every_skill():
    listed = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', 'integrations/claude'], capture_output=True, check=True)
    prefix = 'integrations/claude/'
    tracked = [item[len(prefix):] for item in listed.stdout.decode('utf-8').split('\0') if item]
    files = packaging.plugin_files(ROOT / 'integrations' / 'claude', tracked)
    for skill in ('start-story', 'draft-scene', 'publish', 'revise', 'series-bible', 'setup-models'):
        assert f'obscura/skills/{skill}/SKILL.md' in files
    assert not [rel for rel in files if rel.startswith('obscura/evals/')]


def test_bridge_check_requires_the_guide(monkeypatch, tmp_path):
    build_store = _load_build_store()
    answers = {'--help': b'storygen-mcp\n', '--self-check': b'storygen-mcp: ok\nguide: absent\n'}

    def fake(arguments, **kwargs):
        return subprocess.CompletedProcess(arguments, 0, stdout=answers[arguments[1]], stderr=b'')

    monkeypatch.setattr(build_store.subprocess, 'run', fake)
    with pytest.raises(build_store.Refused, match='guide'):
        build_store.check_bridge(tmp_path)
    answers['--self-check'] = b'storygen-mcp: ok\nguide: ok\n'
    build_store.check_bridge(tmp_path)


def test_package_version_of_the_project_is_1_0_1_0():
    import tomllib
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    plugin = json.loads((ROOT / 'integrations/claude/obscura/.claude-plugin/plugin.json').read_text(encoding='utf-8'))
    assert package_version(project['version']) == '1.0.1.0'
    assert plugin['version'] == project['version']


def test_plugin_files_check_skills_as_they_will_ship(plugin_tree):
    root, tracked = plugin_tree
    skill = root / 'obscura/skills/start-story'
    (skill / 'references').mkdir()
    (skill / 'references/new.md').write_text('never added to git', encoding='utf-8')
    (skill / 'SKILL.md').write_text('See ${CLAUDE_PLUGIN_ROOT}/skills/start-story/references/new.md\n', encoding='utf-8')
    with pytest.raises(ValueError, match='start-story'):
        packaging.plugin_files(root, tracked)
    # An untracked draft skill is not shipped, so it cannot refuse the build.
    (skill / 'references/new.md').unlink()
    (skill / 'SKILL.md').write_text('See ${CLAUDE_PLUGIN_ROOT}/shared/rules.md\n', encoding='utf-8')
    draft = root / 'obscura/skills/draft-idea/SKILL.md'
    draft.parent.mkdir(parents=True)
    draft.write_text('Use ${CLAUDE_PLUGIN_ROOT}/skills/start-story/SKILL.md\n', encoding='utf-8')
    assert 'obscura/skills/draft-idea/SKILL.md' not in packaging.plugin_files(root, tracked)
