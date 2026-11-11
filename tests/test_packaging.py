"""PACKAGING-001: pure parts of the Store package build."""
import json
import xml.etree.ElementTree as ET
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from storygen import packaging
from storygen.build_edition import load_build_edition
from storygen.packaging import (appx_manifest, check_report, dependency_closure, edition_marker, find_makeappx, missing_licenses,
    package_version, pyinstaller_args, root_requirements, third_party_notices, vendor_runtime_files)

ROOT = Path(__file__).resolve().parents[1]
NS = {'m': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10',
      'uap': 'http://schemas.microsoft.com/appx/manifest/uap/windows10',
      'rescap': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities'}
GOOD = {'ok': True, 'frozen': True, 'edition': 'store', 'checks': [{'name': 'tls_context', 'ok': True, 'detail': ''}]}


def test_edition_marker_is_what_the_application_reads(tmp_path):
    path = tmp_path / 'build_edition.json'
    path.write_text(edition_marker('store', 'https://example.test/r', support_url='https://example.test/s'), encoding='utf-8')
    loaded = load_build_edition(path)
    assert (loaded.edition, loaded.report_url, loaded.support_url, loaded.waitlist_url) == ('store', 'https://example.test/r', 'https://example.test/s', '')


@pytest.mark.parametrize('arguments', [('store', ''), ('store', 'http://example.test/r'), ('pro', 'https://example.test/r')])
def test_edition_marker_refuses_what_the_application_would_refuse(arguments):
    with pytest.raises(ValueError):
        edition_marker(*arguments)


def test_root_requirements_come_from_the_checkout():
    found = root_requirements(ROOT / 'pyproject.toml')
    names = {packaging._normal(packaging.Requirement(text).name) for text in found}
    assert {'pydantic', 'fastapi', 'keyring', 'pystray', 'pillow', 'tokenizers'} <= names and 'pytest' not in names and 'mcp' not in names


def test_dependency_closure_follows_markers_and_extras():
    table = {'app': ['lib[fast]', 'win-only; sys_platform == "win32"', 'never; python_version < "3"'],
             'lib': ['core', 'speedups; extra == "fast"', 'docs-tool; extra == "docs"'], 'core': [], 'speedups': [], 'win-only': []}

    def lookup(name):
        if name not in table:
            raise PackageNotFoundError(name)
        return table[name]
    import sys
    expected = ['app', 'core', 'lib', 'speedups'] + (['win-only'] if sys.platform == 'win32' else [])
    assert dependency_closure(['app'], lookup=lookup) == sorted(expected)
    with pytest.raises(ValueError, match='Залежність не встановлена: ghost'):
        dependency_closure(['ghost'], lookup=lookup)


class FakeDistribution:
    def __init__(self, name, tmp_path, files=(), license_expression='MIT'):
        self.version, self.files, self._root = '1.0', list(files), tmp_path
        self.metadata = {'Name': name, 'License-Expression': license_expression}

    def locate_file(self, item):
        return self._root / str(item)


def test_notices_carry_name_version_licence_and_text(tmp_path):
    (tmp_path / 'LICENSE').write_text('Permission is hereby granted', encoding='utf-8')
    (tmp_path / 'COPYING.LGPL').write_text('GNU LESSER GENERAL PUBLIC LICENSE', encoding='utf-8')
    table = {'alpha': FakeDistribution('Alpha', tmp_path, ['alpha-1.0.dist-info/licenses/LICENSE', 'alpha/__init__.py']),
             'tray': FakeDistribution('Tray', tmp_path, ['COPYING.LGPL'], 'LGPL-3.0-only'),
             'tokenizers': FakeDistribution('tokenizers', tmp_path, ['tokenizers/__init__.py'], '')}
    (tmp_path / 'alpha-1.0.dist-info' / 'licenses').mkdir(parents=True)
    (tmp_path / 'alpha-1.0.dist-info' / 'licenses' / 'LICENSE').write_text('Permission is hereby granted', encoding='utf-8')
    text = third_party_notices(['alpha', 'tray', 'tokenizers'], lookup=table.__getitem__)
    assert 'Alpha 1.0\nLicence: MIT' in text and 'Permission is hereby granted' in text
    assert 'Tray 1.0\nLicence: LGPL-3.0-only' in text and 'GNU LESSER GENERAL PUBLIC LICENSE' in text
    assert 'tokenizers 1.0\nLicence: Apache-2.0' in text and 'github.com/huggingface/tokenizers' in text


def test_distribution_without_a_licence_text_stops_the_build(tmp_path):
    table = {'mystery': FakeDistribution('Mystery', tmp_path, ['mystery/__init__.py'], '')}
    assert missing_licenses(['mystery'], lookup=table.__getitem__) == ['mystery']
    with pytest.raises(ValueError, match='Немає тексту ліцензії для: mystery'):
        third_party_notices(['mystery'], lookup=table.__getitem__)


def test_real_dependencies_all_have_licence_texts():
    names = dependency_closure(root_requirements(ROOT / 'pyproject.toml'))
    assert missing_licenses(names) == []
    text = third_party_notices(names)
    assert 'pystray' in text and 'keyring' in text and len(text) > 20000


def test_vendor_runtime_files(tmp_path):
    (tmp_path / 'ssl.py').write_text('', encoding='utf-8')
    assert vendor_runtime_files(tmp_path) == []                     # stock CPython
    (tmp_path / 'codex-rejected-cas.pem').write_text('pem', encoding='utf-8')
    assert vendor_runtime_files(tmp_path) == [tmp_path / 'codex-rejected-cas.pem']


def test_pyinstaller_arguments(tmp_path):
    arguments = pyinstaller_args(tmp_path / 'entry.py', 'Obscura', tmp_path / 'dist', tmp_path / 'work', tmp_path / 'hooks')
    for flag in ('--noconsole', '--onedir', '--noconfirm'):
        assert flag in arguments
    assert '--onefile' not in arguments and arguments[-1] == str(tmp_path / 'entry.py')
    pairs = list(zip(arguments, arguments[1:]))
    for pair in [('--collect-data', 'storygen'), ('--collect-submodules', 'storygen'), ('--copy-metadata', 'storygen'),
                 ('--hidden-import', 'keyring.backends.Windows'), ('--hidden-import', 'pystray._win32'),
                 ('--additional-hooks-dir', str(tmp_path / 'hooks')), ('--name', 'Obscura')]:
        assert pair in pairs


def test_pystray_hook_keeps_the_lgpl_library_replaceable():
    hook = (ROOT / packaging.HOOKS_DIR / 'hook-pystray.py').read_text(encoding='utf-8')
    assert "module_collection_mode = 'py'" in hook


def test_check_report():
    assert check_report(GOOD, 'store') == []
    failed = {**GOOD, 'ok': False, 'checks': [{'name': 'tls_context', 'ok': False, 'detail': 'FileNotFoundError'}]}
    assert check_report(failed, 'store') == ['перевірка tls_context: FileNotFoundError']
    assert check_report({**GOOD, 'frozen': False}, 'store') == ['самоперевірку виконано не в замороженій збірці']
    assert check_report({**GOOD, 'edition': 'full'}, 'store') == ['позначка видання не потрапила в збірку: очікувано store, застосунок повідомляє full']
    assert check_report({**GOOD, 'ok': False}, 'store') == ['самоперевірка не пройшла']
    for broken in (None, {}, {'checks': 'x'}, []):
        assert check_report(broken, 'store') == ['звіт самоперевірки відсутній або пошкоджений']


@pytest.mark.parametrize('given,expected', [('0.1.0', '0.1.0.0'), ('1.2', '1.2.0.0'), ('2.0.1.5', '2.0.1.5'), ('7', '7.0.0.0')])
def test_package_version(given, expected):
    assert package_version(given) == expected


@pytest.mark.parametrize('given', ['0.2.0rc1', '1.2.3.4.5', '', '1..2', '1.-2', '١.٢'])
def test_package_version_refuses_what_msix_cannot_hold(given):
    with pytest.raises(ValueError, match='Версія пакета MSIX має складатися з чисел'):
        package_version(given)


def manifest(**overrides):
    values = dict(identity_name='Obscura.TextWriter', publisher='CN=Publisher', publisher_display_name='Publisher',
                  version='0.1.0.0', description='Local workshop for writing stories')
    return ET.fromstring(appx_manifest(**{**values, **overrides}))


def test_manifest_structure():
    root = manifest()
    identity = root.find('m:Identity', NS).attrib
    assert identity == {'Name': 'Obscura.TextWriter', 'Publisher': 'CN=Publisher', 'Version': '0.1.0.0', 'ProcessorArchitecture': 'x64'}
    application = root.find('m:Applications/m:Application', NS)
    assert application.attrib['Executable'] == 'Obscura.exe' and application.attrib['EntryPoint'] == 'Windows.FullTrustApplication'
    assert [c.attrib['Name'] for c in root.findall('m:Capabilities/rescap:Capability', NS)] == ['runFullTrust']
    assert [r.attrib['Language'] for r in root.findall('m:Resources/m:Resource', NS)] == ['uk-UA', 'en-US']
    family = root.find('m:Dependencies/m:TargetDeviceFamily', NS).attrib
    assert family['Name'] == 'Windows.Desktop' and family['MinVersion'] == '10.0.19041.0'
    visual = application.find('uap:VisualElements', NS).attrib
    logos = {root.find('m:Properties/m:Logo', NS).text, visual['Square150x150Logo'], visual['Square44x44Logo']}
    assert logos == {'Assets\\' + name for name in packaging.ASSETS}


def test_manifest_escapes_every_value():
    awkward = 'CN=A&B "C" <D> \'E\''
    root = manifest(publisher=awkward, publisher_display_name=awkward, description=awkward, identity_name='A&B')
    assert root.find('m:Identity', NS).attrib['Publisher'] == awkward and root.find('m:Identity', NS).attrib['Name'] == 'A&B'
    assert root.find('m:Properties/m:PublisherDisplayName', NS).text == awkward
    assert root.find('m:Applications/m:Application/uap:VisualElements', NS).attrib['Description'] == awkward


def test_package_assets_exist_with_the_declared_sizes():
    from PIL import Image
    for name, size in packaging.ASSETS.items():
        with Image.open(ROOT / 'store_build' / 'msix' / 'Assets' / name) as image:
            assert image.size == (size, size) and image.format == 'PNG'


def test_find_makeappx(tmp_path, monkeypatch):
    tool = tmp_path / 'makeappx.exe'
    tool.write_bytes(b'')
    monkeypatch.delenv('MAKEAPPX', raising=False)
    monkeypatch.setattr(packaging.shutil, 'which', lambda name: None)
    assert find_makeappx(str(tool)) == tool
    monkeypatch.setenv('MAKEAPPX', str(tool))
    assert find_makeappx(None) == tool and find_makeappx(str(tmp_path / 'absent.exe')) == tool
    monkeypatch.delenv('MAKEAPPX')
    with pytest.raises(ValueError, match='Microsoft.Windows.SDK.BuildTools'):
        find_makeappx(None)


def test_build_script_help_runs_without_side_effects(tmp_path):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_store.py'), '--help'], cwd=tmp_path,
                            capture_output=True, encoding='utf-8', errors='replace', timeout=60)
    assert result.returncode == 0 and '--report-url' in result.stdout and list(tmp_path.iterdir()) == []


def test_build_script_refuses_a_non_empty_output_folder(tmp_path):
    import subprocess
    import sys
    (tmp_path / 'keep.txt').write_text('mine', encoding='utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_store.py'), '--out', str(tmp_path),
                             '--report-url', 'https://example.test/r', '--skip-msix'],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=60)
    assert result.returncode != 0 and (tmp_path / 'keep.txt').read_text(encoding='utf-8') == 'mine'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['keep.txt']
