"""CLAUDE-SKILLS: Desktop ZIPs and the MCP guide are generated from the one plugin source."""
import io
import zipfile
from pathlib import Path

import pytest

from storygen import skill_bundles as sb

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT/'integrations/claude'
PLUGIN = MARKET/'obscura'
RULES = '${CLAUDE_PLUGIN_ROOT}/shared/rules.md'


def make_plugin(root, skills):
    """A synthetic plugin: `skills` maps a skill name to its SKILL.md body; references are files under `refs`."""
    plugin = root/'obscura'
    (plugin/'.claude-plugin').mkdir(parents=True)
    (plugin/'.claude-plugin/plugin.json').write_text('{"name": "obscura", "version": "0.1.0"}', encoding='utf-8')
    (plugin/'shared').mkdir()
    (plugin/'shared/rules.md').write_text('RULES TEXT\n', encoding='utf-8')
    for name, (body, refs) in skills.items():
        folder = plugin/'skills'/name
        (folder/'references').mkdir(parents=True)
        (folder/'SKILL.md').write_text(f'---\nname: {name}\ndescription: d\n---\n{body}\n', encoding='utf-8')
        for ref, text in refs.items():
            (folder/'references'/f'{ref}.md').write_text(text, encoding='utf-8')
    return plugin


@pytest.mark.req('CLAUDE-SKILLS')
def test_bundle_rewrites_plugin_root(tmp_path):
    plugin = make_plugin(tmp_path, {'a': (f'Read `{RULES}`, then `${{CLAUDE_PLUGIN_ROOT}}/skills/a/references/x.md`.',
                                          {'x': 'X TEXT\n'})})
    files = sb.bundle_files(plugin, 'a')
    assert set(files) == {'a/SKILL.md', 'a/references/x.md', 'a/references/rules.md'}
    assert '`references/rules.md`' in files['a/SKILL.md']
    assert '`references/x.md`' in files['a/SKILL.md']
    assert files['a/references/rules.md'] == 'RULES TEXT\n'
    assert all('${CLAUDE_PLUGIN_ROOT}' not in text for text in files.values())


@pytest.mark.req('CLAUDE-SKILLS')
def test_reference_to_another_skill_is_an_error(tmp_path):
    plugin = make_plugin(tmp_path, {'a': ('See `${CLAUDE_PLUGIN_ROOT}/skills/b/references/y.md`.', {}),
                                    'b': ('b', {'y': 'Y'})})
    with pytest.raises(sb.BundleError, match='a/SKILL.md'):
        sb.bundle_files(plugin, 'a')


@pytest.mark.req('CLAUDE-SKILLS')
def test_unknown_skill_is_an_error(tmp_path):
    plugin = make_plugin(tmp_path, {'a': ('a', {})})
    for name in ('../shared', 'nope'):
        with pytest.raises(sb.BundleError):
            sb.bundle_files(plugin, name)


@pytest.mark.req('CLAUDE-SKILLS')
def test_desktop_zip_is_one_folder_named_after_skill(tmp_path):
    plugin = make_plugin(tmp_path, {'a': (f'Read `{RULES}`.', {'x': 'X'})})
    data = sb.desktop_zip(plugin, 'a')
    archive = zipfile.ZipFile(io.BytesIO(data))
    assert sorted(archive.namelist()) == ['a/SKILL.md', 'a/references/rules.md', 'a/references/x.md']
    files = sb.bundle_files(plugin, 'a')
    assert {name: archive.read(name).decode('utf-8') for name in archive.namelist()} == files
    assert sb.desktop_zip(plugin, 'a') == data


@pytest.mark.req('CLAUDE-SKILLS')
def test_every_real_skill_bundles():
    assert sb.skill_names(PLUGIN) == ['draft-scene', 'publish', 'revise', 'series-bible', 'setup-models', 'start-story']
    for skill in sb.skill_names(PLUGIN):
        files = sb.bundle_files(PLUGIN, skill)
        assert f'{skill}/SKILL.md' in files
        assert f'{skill}/references/rules.md' in files


@pytest.mark.req('CLAUDE-SKILLS')
def test_guide_points_to_get_guide():
    text = sb.guide_text(PLUGIN, 'draft-scene')
    assert 'get_guide(task="draft-scene", reference="chat-pipeline")' in text
    assert 'get_guide(task="draft-scene", reference="rules")' in text
    assert '${CLAUDE_PLUGIN_ROOT}' not in text
    assert sb.guide_references(PLUGIN, 'draft-scene') == ['chat-pipeline', 'continuity', 'obscura-runs', 'rules']
    rules = (PLUGIN/'shared/rules.md').read_text(encoding='utf-8')
    assert sb.guide_reference(PLUGIN, 'draft-scene', 'rules') == rules
    for name in ('../SKILL', '..\\rules', 'nope'):
        with pytest.raises(sb.BundleError):
            sb.guide_reference(PLUGIN, 'draft-scene', name)


@pytest.mark.req('CLAUDE-SKILLS')
def test_user_files_skip_tools_and_evals():
    files = sb.user_files(MARKET)
    assert '.claude-plugin/marketplace.json' in files
    assert 'obscura/.claude-plugin/plugin.json' in files
    assert 'obscura/skills/publish/SKILL.md' in files
    assert 'obscura/shared/rules.md' in files
    assert not [f for f in files if f.startswith('tools/') or '/evals/' in f or f.startswith('obscura/evals')]
    assert files == sorted(files)


@pytest.mark.req('CLAUDE-SKILLS')
def test_sources(tmp_path):
    exe = tmp_path/'app'/'Obscura.exe'
    checkout = tmp_path/'repo'
    assert sb.marketplace_source(frozen=True, executable=exe, checkout=checkout) is None
    (exe.parent/'claude/.claude-plugin').mkdir(parents=True)
    (exe.parent/'claude/.claude-plugin/marketplace.json').write_text('{}', encoding='utf-8')
    assert sb.marketplace_source(frozen=True, executable=exe, checkout=checkout) == exe.parent/'claude'
    assert sb.marketplace_source(frozen=False, executable=exe, checkout=checkout) is None
    assert sb.marketplace_source(frozen=False, executable=exe, checkout=ROOT) == MARKET
    assert sb.plugin_root(MARKET) == PLUGIN
    assert sb.plugin_root(None) is None
    assert sb.plugin_root(exe.parent/'claude') is None
