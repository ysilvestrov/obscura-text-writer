"""CLAUDE-SKILLS: the obscura plugin for Claude Code stays installable, portable and in step with the MCP bridge."""
import json
import re
import shutil
from pathlib import Path

import pytest

pytest.importorskip('mcp')
from storygen.mcp.bridge import TOOLS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT/'integrations/claude'
PLUGIN = MARKET/'obscura'
# Outside Claude Code (claude.ai upload, Skills API) a skill with any other frontmatter key is refused.
PORTABLE = {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'}
RULES = '${CLAUDE_PLUGIN_ROOT}/shared/rules.md'
TOOL_PREFIXES = ('get_', 'save_', 'create_', 'update_', 'import_', 'add_', 'list_', 'start_', 'apply_',
                 'generate_', 'upload_', 'export_', 'open_', 'next_step')  # not next_: next_offset is a response field


def skill_files(plugin):
    return sorted((plugin/'skills').glob('*/SKILL.md'))


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return {}
    block = text[4:text.index('\n---', 4)]
    fields = {}
    for line in block.splitlines():
        if line and not line[0].isspace() and ':' in line:
            key, value = line.split(':', 1)
            fields[key.strip()] = value.strip()
    return fields


def strict_yaml_problems(path):
    """Claude Code reads frontmatter leniently; the Desktop ZIP and claude.ai upload need valid YAML (an unquoted ': '
    inside the description breaks it)."""
    import yaml
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return []
    try:
        data = yaml.safe_load(text[4:text.index('\n---', 4)])
    except yaml.YAMLError as error:
        return [f'{path.parent.name}: frontmatter is not valid YAML: {str(error).splitlines()[0]}']
    return [] if isinstance(data, dict) else [f'{path.parent.name}: frontmatter is not a YAML mapping']


def tool_mentions(text):
    """Every MCP tool a skill names: `mcp__obscura__x` or a backticked snake_case name with a tool verb prefix,
    bare or in call syntax such as `get_run(run_id)`."""
    found = set(re.findall(r'mcp__obscura__(\w+)', text))
    found |= {name for name in re.findall(r'`([a-z]+(?:_[a-z]+)+)(?:`|\()', text) if name.startswith(TOOL_PREFIXES)}
    return found


def problems(plugin):
    result = []
    files = skill_files(plugin)
    if not files:
        result.append('no skills')
    for path in files:
        skill = path.parent.name
        fields = frontmatter(path)
        result += strict_yaml_problems(path)
        if fields.get('name') != skill:
            result.append(f'{skill}: name must equal the folder name')
        if not fields.get('description'):
            result.append(f'{skill}: no description')
        result += [f'{skill}: frontmatter field {key} works only in Claude Code' for key in sorted(set(fields) - PORTABLE)]
        text = path.read_text(encoding='utf-8')
        if RULES not in text:
            result.append(f'{skill}: does not point to {RULES}')
    for path in sorted(plugin.rglob('*.md')):
        unknown = tool_mentions(path.read_text(encoding='utf-8')) - set(TOOLS)
        result += [f'{path.relative_to(plugin).as_posix()}: unknown MCP tool {name}' for name in sorted(unknown)]
    return result


def copy_plugin(tmp_path):
    return Path(shutil.copytree(PLUGIN, tmp_path/'obscura'))


@pytest.mark.req('CLAUDE-SKILLS')
def test_marketplace_and_plugin_are_valid():
    market = json.loads((MARKET/'.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
    assert market['name'] == 'obscura'
    assert [p['name'] for p in market['plugins']] == ['obscura'] and market['plugins'][0]['source'] == './obscura'
    plugin = json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text(encoding='utf-8'))
    assert plugin['name'] == 'obscura' and plugin['version'] and plugin['description']
    # The server is registered by "Connect Claude" or the site command; a second entry would duplicate it.
    assert not (PLUGIN/'.mcp.json').exists() and 'mcpServers' not in plugin


@pytest.mark.req('CLAUDE-SKILLS')
def test_real_plugin_has_no_problems():
    assert {p.parent.name for p in skill_files(PLUGIN)} >= {'start-story', 'draft-scene'}
    assert (PLUGIN/'shared/rules.md').is_file()
    assert problems(PLUGIN) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_claude_code_only_field_is_reported(tmp_path):
    copy = copy_plugin(tmp_path)
    path = copy/'skills/start-story/SKILL.md'
    path.write_text(path.read_text(encoding='utf-8').replace('---\n', '---\nmodel: opus\n', 1), encoding='utf-8')
    assert any('start-story' in p and 'model' in p for p in problems(copy))


@pytest.mark.req('CLAUDE-SKILLS')
def test_invalid_yaml_frontmatter_is_reported(tmp_path):
    copy = copy_plugin(tmp_path)
    path = copy/'skills/revise/SKILL.md'
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace('Obscura story, for example move', 'Obscura story: move', 1), encoding='utf-8')
    assert any(p.startswith('revise: frontmatter is not valid YAML') for p in problems(copy))


@pytest.mark.req('CLAUDE-SKILLS')
def test_unknown_tool_name_is_reported(tmp_path):
    copy = copy_plugin(tmp_path)
    path = copy/'skills/draft-scene/SKILL.md'
    path.write_text(path.read_text(encoding='utf-8') + '\nCall `get_storyy` and `mcp__obscura__save_drafts`; read on with `next_offset`.\n', encoding='utf-8')
    found = problems(copy)
    assert any('get_storyy' in p for p in found) and any('save_drafts' in p for p in found)
    assert not any('next_offset' in p for p in found)


@pytest.mark.req('CLAUDE-SKILLS')
def test_unknown_tool_in_call_syntax_is_reported(tmp_path):
    copy = copy_plugin(tmp_path)
    path = copy/'skills/draft-scene/SKILL.md'
    path.write_text(path.read_text(encoding='utf-8') + '\nWatch with `get_runs(run_id)`.\n', encoding='utf-8')
    assert any('get_runs' in p for p in problems(copy))


@pytest.mark.req('CLAUDE-SKILLS')
def test_plugin_version_is_project_version():
    import tomllib
    project = tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    plugin = json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text(encoding='utf-8'))['version']
    assert plugin == project


@pytest.mark.req('CLAUDE-SKILLS')
def test_skills_never_mention_get_guide():
    """get_guide is for clients without the skills; a skill that names it would send Claude in circles."""
    offenders = [str(p.relative_to(PLUGIN)) for p in PLUGIN.rglob('*.md')
                 if 'evals' not in p.parts and 'get_guide' in p.read_text(encoding='utf-8')]
    assert offenders == []
