"""CODEX-SKILLS: deterministic, read-only adaptation of the Claude skill sources."""
from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

NAMES = ('start-story', 'draft-scene', 'publish', 'series-bible', 'setup-models')
GENERATOR_VERSION = '1'
TICK = chr(96)
PLUGIN_ROOT = chr(36) + '{CLAUDE_PLUGIN_ROOT}'
PORTABLE = {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'}


class GenerationError(ValueError):
    """A source no longer has the known portable structure."""


@dataclass(frozen=True)
class SkillBundle:
    files: dict[str, bytes]
    sources: dict[str, str]
    generator_version: str


def _reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def _once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise GenerationError('source_structure_changed')
    return text.replace(old, new)


def _section(text: str, start: str, end: str | None, replacement: str) -> str:
    if text.count(start) != 1 or end is not None and text.count(end) != 1:
        raise GenerationError('source_model_section_changed')
    left = text.index(start)
    right = text.index(end, left + len(start)) if end else len(text)
    return text[:left] + replacement + '\n\n' + text[right:]


def generate_skills(source: Path) -> SkillBundle:
    source = Path(source).absolute()
    hashes: dict[str, str] = {}

    def read(relative: str) -> str:
        parts = PurePosixPath(relative)
        if parts.is_absolute() or '..' in parts.parts or '\\' in relative:
            raise GenerationError('unsafe_source_path')
        path = source
        for part in ('', *parts.parts):
            path = path/part
            if _reparse(path):
                raise GenerationError('linked_source')
        if not path.is_file():
            raise GenerationError('missing_source')
        raw = path.read_bytes()
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        try:
            return raw.decode('utf-8').replace('\r\n', '\n')
        except UnicodeError:
            raise GenerationError('source_encoding') from None

    # Do not traverse a directory link while collecting the input inventory.
    read('shared/rules.md')
    skills = source/'skills'
    if _reparse(skills) or {p.name for p in skills.iterdir()} != set(NAMES):
        raise GenerationError('source_skill_inventory_changed')
    originals: dict[str, str] = {}
    for name in NAMES:
        pending = [skills/name]
        while pending:
            path = pending.pop()
            if _reparse(path):
                raise GenerationError('linked_source')
            if path.is_dir():
                pending.extend(sorted(path.iterdir()))
            elif path.suffix == '.md' and (path.name == 'SKILL.md' or path.is_relative_to(skills/name/'references')):
                originals[path.relative_to(source).as_posix()] = read(path.relative_to(source).as_posix())
            else:
                raise GenerationError('unsupported_source_file')
        if f'skills/{name}/SKILL.md' not in originals:
            raise GenerationError('missing_skill')

    rules = read('shared/rules.md')
    rules = _once(rules, 'Claude is not connected', 'Codex is not connected')
    rules = _once(rules, '"Connect Claude"', '"Connect to Codex"')
    rules = _once(rules, 'AskUserQuestion', "the client's available question tool")
    emitted_paths = {key: 'obscura-' + key.removeprefix('skills/') for key in originals}
    available = set(emitted_paths.values())
    files: dict[str, bytes] = {}

    for key, original in sorted(originals.items()):
        name = PurePosixPath(key).parts[1]
        target = emitted_paths[key]
        text = original
        if key.endswith('/SKILL.md'):
            if not text.startswith('---\n') or '\n---\n' not in text[4:]:
                raise GenerationError('invalid_frontmatter')
            front = text[4:text.index('\n---\n', 4)]
            fields = dict(re.findall(r'^([a-z][a-z-]*):[ \t]*(.*)$', front, re.M))
            if fields.get('name') != name or not fields.get('description') or set(fields) - PORTABLE:
                raise GenerationError('unsupported_frontmatter')
            text = _once(text, 'name: '+name+'\n', 'name: obscura-'+name+'\n')
            lines = text.splitlines(keepends=True)
            rule_lines = [i for i, line in enumerate(lines) if PLUGIN_ROOT+'/shared/rules.md' in line]
            if len(rule_lines) != 1 or not lines[rule_lines[0]].startswith('Read '):
                raise GenerationError('shared_rules_link_changed')
            lines[rule_lines[0]] = rules.rstrip()+'\n'
            text = ''.join(lines)
        if key == 'skills/start-story/SKILL.md':
            text = _section(text, '## Model\n', '## Gates\n',
                            '## Model\n\nUse the current session for planning. Do not automatically switch models, '
                            'call an advisor, or create subagents. No Codex quality comparison has been measured.')
        if key == 'skills/draft-scene/references/chat-pipeline.md':
            text = _section(text, '## Model routing\n', None,
                            '## Model routing\n\nUse the current session for brief, draft, edit, and memory. '
                            'Do not automatically switch models or create subagents. '
                            'No Codex quality or cost comparison has been measured.')
        if 'AskUserQuestion' in text:
            if key != 'skills/start-story/references/interview.md':
                raise GenerationError('unknown_question_instruction')
            text = _once(text, 'AskUserQuestion', "the client's available question tool")
        for skill in NAMES:
            text = text.replace(TICK+skill+TICK, TICK+'obscura-'+skill+TICK)

        def plugin_reference(match):
            reference = match[1]
            if reference not in emitted_paths:
                raise GenerationError('unresolved_plugin_reference')
            return posixpath.relpath(emitted_paths[reference], posixpath.dirname(target))
        text = re.sub(re.escape(PLUGIN_ROOT) + '/([^'+TICK+r'\s]+)', plugin_reference, text)

        def relative_reference(reference: str) -> str:
            if '\\' in reference or ':' in reference or reference.startswith('/'):
                raise GenerationError('external_reference')
            parent = posixpath.dirname(target)
            resolved = posixpath.normpath(posixpath.join(parent, reference))
            if resolved not in available:
                resolved = posixpath.normpath(posixpath.join('obscura-'+name, 'references', reference))
            if resolved not in available:
                raise GenerationError('unresolved_relative_reference')
            return posixpath.relpath(resolved, parent)

        text = re.sub(TICK+'([^'+TICK+r'\n]*\.md)'+TICK,
                      lambda match: TICK+relative_reference(match[1])+TICK, text)
        text = re.sub(r'(\[[^\]]+\]\()([^)]+\.md)(\))',
                      lambda match: match[1]+relative_reference(match[2])+match[3], text)
        if any(token in text for token in ('CLAUDE_PLUGIN_ROOT', 'Claude', 'AskUserQuestion', '/model', 'Advisor')):
            raise GenerationError('unadapted_client_instruction')
        if target.endswith('/SKILL.md'):
            text += '\nResolve local file references relative to the directory of the file that contains them.\n'
        files[target] = text.rstrip().encode('utf-8') + b'\n'
    return SkillBundle(files, hashes, GENERATOR_VERSION)
