"""CODEX-SKILLS: generated skills preserve the workflow without Claude client instructions."""
import hashlib
import re
import shutil
from pathlib import Path, PurePosixPath

import pytest

from storygen.codex_skills import GenerationError, generate_skills

SOURCE = Path(__file__).resolve().parents[1]/'integrations/claude/obscura'
NAMES = {'obscura-start-story','obscura-draft-scene','obscura-publish','obscura-series-bible','obscura-setup-models'}


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def copy_source(tmp_path):
    return Path(shutil.copytree(SOURCE, tmp_path/'source'))


@pytest.mark.req('CODEX-SKILLS')
def test_real_sources_generate_five_self_contained_skills():
    bundle = generate_skills(SOURCE)
    assert {key.split('/')[0] for key in bundle.files} == NAMES
    for name in NAMES:
        text = bundle.files[name+'/SKILL.md'].decode()
        assert 'name: '+name+'\n' in text and 'description:' in text
        assert text.count('# Shared rules for every Obscura skill') == 1
    assert bundle.files == generate_skills(SOURCE).files
    assert bundle.sources and all(len(value) == 64 for value in bundle.sources.values())
    assert not any(key.startswith(('evals/', 'shared/')) for key in bundle.files)


@pytest.mark.req('CODEX-SKILLS')
def test_generation_does_not_change_sources():
    before = snapshot(SOURCE)
    generate_skills(SOURCE)
    assert snapshot(SOURCE) == before


@pytest.mark.req('CODEX-SKILLS')
def test_rules_and_references_are_portable():
    bundle = generate_skills(SOURCE)
    for key, raw in bundle.files.items():
        text = raw.decode()
        assert 'CLAUDE_PLUGIN_ROOT' not in text and 'AskUserQuestion' not in text
        assert 'Claude Code' not in text and 'Connect Claude' not in text
        pattern = chr(96)+'([^'+chr(96)+r']*\.md)'+chr(96)
        for reference in re.findall(pattern, text):
            import posixpath
            resolved = posixpath.normpath(str(PurePosixPath(key).parent/reference))
            assert resolved in bundle.files, (key, reference)
    start = bundle.files['obscura-start-story/SKILL.md'].decode()
    assert 'obscura-draft-scene' in start and 'numbered options' in start


@pytest.mark.req('CODEX-SKILLS')
def test_planning_and_scene_routing_use_current_session():
    bundle = generate_skills(SOURCE)
    start = bundle.files['obscura-start-story/SKILL.md'].decode()
    pipeline = bundle.files['obscura-draft-scene/references/chat-pipeline.md'].decode()
    assert '/model' not in start and 'Advisor' not in start
    assert 'current session' in start and 'current session' in pipeline
    assert 'sonnet' not in pipeline and 'opus' not in pipeline and 'Haiku' not in pipeline
    assert 'get_stage_task' in pipeline and 'save_stage_result' in pipeline
    assert 'task_fingerprint' in pipeline and 'needs_review' in pipeline


@pytest.mark.req('CODEX-SKILLS')
def test_provider_recipes_are_preserved():
    bundle = generate_skills(SOURCE)
    original = (SOURCE/'skills/setup-models/references/recipes.md').read_text()
    emitted = bundle.files['obscura-setup-models/references/recipes.md'].decode()
    assert [line for line in original.splitlines() if line.startswith('|')] == [
        line for line in emitted.splitlines() if line.startswith('|')]


@pytest.mark.req('CODEX-SKILLS')
@pytest.mark.parametrize('old,new', [('## Model\n','## Routing changed\n'),
                                   ('## Gates\n','## Next gates\n')])
def test_source_drift_refuses_the_whole_bundle(tmp_path, old, new):
    source = copy_source(tmp_path)
    skill = source/'skills/start-story/SKILL.md'
    skill.write_text(skill.read_text().replace(old,new),encoding='utf-8')
    with pytest.raises(GenerationError):
        generate_skills(source)


@pytest.mark.req('CODEX-SKILLS')
def test_external_reference_is_rejected(tmp_path):
    source = copy_source(tmp_path)
    skill = source/'skills/start-story/SKILL.md'
    token = chr(36)+'{CLAUDE_PLUGIN_ROOT}'
    skill.write_text(skill.read_text().replace(token+'/skills/start-story/references/interview.md',
                                               token+'/../../outside.md'),encoding='utf-8')
    with pytest.raises(GenerationError):
        generate_skills(source)


@pytest.mark.req('CODEX-SKILLS')
def test_symlink_source_is_rejected(tmp_path):
    source = copy_source(tmp_path)
    target = source/'skills/start-story/references/interview.md'
    outside = tmp_path/'outside.md'
    outside.write_text(target.read_text(),encoding='utf-8')
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip('OS denies test symlink creation')
    with pytest.raises(GenerationError):
        generate_skills(source)


@pytest.mark.req('CODEX-SKILLS')
def test_unknown_mcp_tool_is_reported(tmp_path):
    from storygen.mcp.bridge import TOOLS
    from test_claude_plugin import tool_mentions
    source=copy_source(tmp_path)
    skill=source/'skills/start-story/SKILL.md'
    tick=chr(96)
    skill.write_text(skill.read_text()+'\nCall '+tick+'get_unknown_test_tool(story_id)'+tick+'.\n',encoding='utf-8')
    bundle=generate_skills(source)
    mentions=set().union(*(tool_mentions(raw.decode()) for raw in bundle.files.values()))
    assert {'get_story','get_stage_task','save_draft'} <= mentions
    assert mentions - set(TOOLS)=={'get_unknown_test_tool'}
    clean=generate_skills(SOURCE)
    real=set().union(*(tool_mentions(raw.decode()) for raw in clean.files.values()))
    assert {'get_story','get_stage_task','save_draft'} <= real
    assert real <= set(TOOLS)


@pytest.mark.req('CODEX-SKILLS')
@pytest.mark.parametrize('skill,position', [
    ('draft-scene/references/chat-pipeline.md','end'),
    ('start-story/SKILL.md','before_gates'),
])
def test_model_adaptation_preserves_other_sections(tmp_path,skill,position):
    source=copy_source(tmp_path)
    path=source/'skills'/skill
    extra='## Additional requirement\n\nKeep the neutral editorial checklist.\n\n'
    text=path.read_text()
    text=text+extra if position=='end' else text.replace('## Gates\n',extra+'## Gates\n')
    path.write_text(text,encoding='utf-8')
    result=generate_skills(source)
    emitted=result.files['obscura-'+skill].decode()
    assert 'Keep the neutral editorial checklist.' in emitted


@pytest.mark.req('CODEX-SKILLS')
def test_lowercase_advisor_instruction_is_not_emitted(tmp_path):
    source=copy_source(tmp_path)
    path=source/'skills/start-story/SKILL.md'
    path.write_text(path.read_text()+'\nConsult the advisor before continuing.\n',encoding='utf-8')
    with pytest.raises(GenerationError):
        generate_skills(source)


@pytest.mark.req('CODEX-SKILLS')
@pytest.mark.parametrize('mutation', ['invalid_scalar','unknown_key'])
def test_entire_frontmatter_is_validated(tmp_path,mutation):
    source=copy_source(tmp_path)
    path=source/'skills/start-story/SKILL.md'
    text=path.read_text()
    if mutation=='invalid_scalar':
        text=text.replace('description: ','description: invalid: ',1)
    else:
        text=text.replace('\n---\n','\nclient_only: yes\n---\n',1)
    path.write_text(text,encoding='utf-8')
    with pytest.raises(GenerationError):
        generate_skills(source)


@pytest.mark.req('CODEX-SKILLS')
def test_markdown_fragment_does_not_hide_missing_reference(tmp_path):
    source=copy_source(tmp_path)
    path=source/'skills/start-story/SKILL.md'
    path.write_text(path.read_text()+'\n[chapter](references/missing.md#introduction)\n',encoding='utf-8')
    with pytest.raises(GenerationError):
        generate_skills(source)
