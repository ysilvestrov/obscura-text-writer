"""Isolated stand for `claude -p` runs of the Obscura skills (CLAUDE-SKILLS).

Starts a fresh Obscura server with its own data folder (never the author's), writes an MCP config that points
`obscura` only at that server, and runs `claude -p` with `--strict-mcp-config` and the plugin from this repository.
Cost and usage come from the `result` line of `--output-format stream-json`; on a claude.ai subscription the dollar
figure is the API-price estimate, not money charged.

    python scripts/skills_stand.py serve --work C:/tmp/stand1
    python scripts/skills_stand.py run --work C:/tmp/stand1 --prompt-file p.txt --model sonnet --budget 1.0
"""
import argparse
import contextlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT/'integrations/claude/obscura'
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]


@dataclass
class Stand:
    port: int
    base: str
    data: Path
    mcp_config: Path


@dataclass
class Result:
    tool_calls: list = field(default_factory=list)
    cost_usd: float | None = None
    usage: dict = field(default_factory=dict)
    text: str = ''
    is_error: bool = False
    errors: list = field(default_factory=list)
    session_id: str | None = None


def write_mcp_config(path, port):
    """Only `obscura`, only the stand's port: the author's server is never reachable from a stand run."""
    path = Path(path)
    config = {'mcpServers': {'obscura': {'command': sys.executable,
                                         'args': ['-m', 'storygen.mcp.bridge', '--url', f'http://127.0.0.1:{port}']}}}
    path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    return path


# The MCP config isolates only MCP; a shell, HTTP or file writes could still reach the author's Obscura or files.
BLOCKED_TOOLS = ('Bash', 'PowerShell', 'WebFetch', 'WebSearch', 'Write', 'Edit', 'NotebookEdit')


def claude_command(prompt, *, mcp_config, plugin_dir, model, budget_usd, resume=None):
    return [shutil.which('claude') or 'claude', '-p', prompt, *(['--resume', resume] if resume else []), '--plugin-dir', str(plugin_dir),
            '--mcp-config', str(mcp_config), '--strict-mcp-config', '--output-format', 'stream-json', '--verbose',
            '--model', model, '--max-budget-usd', str(budget_usd), '--permission-mode', 'bypassPermissions',
            '--disallowedTools', ','.join(BLOCKED_TOOLS)]


def _events(lines):
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(event, dict):
            yield event


def tool_calls(lines):
    """Tool calls in order; Obscura tools without the `mcp__obscura__` prefix."""
    calls = []
    for event in _events(lines):
        if event.get('type') != 'assistant':
            continue
        for item in (event.get('message') or {}).get('content') or []:
            if isinstance(item, dict) and item.get('type') == 'tool_use':
                calls.append((str(item.get('name', '')).removeprefix('mcp__obscura__'), item.get('input') or {}))
    return calls


def tool_errors(lines):
    """Refused tool calls in order: (tool name without the obscura prefix, error text)."""
    names, errors = {}, []
    for event in _events(lines):
        for item in (event.get('message') or {}).get('content') or []:
            if not isinstance(item, dict):
                continue
            if event.get('type') == 'assistant' and item.get('type') == 'tool_use':
                names[item.get('id')] = str(item.get('name', '')).removeprefix('mcp__obscura__')
            elif event.get('type') == 'user' and item.get('type') == 'tool_result' and item.get('is_error'):
                content = item.get('content')
                if isinstance(content, list):
                    content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
                errors.append((names.get(item.get('tool_use_id'), '?'), str(content)))
    return errors


def obscura_call(http, name, arguments):
    """Call one bridge tool in-process against `http` (an httpx client or a base URL); the stand sets up stories this
    way without a model. Raises RuntimeError on a tool error."""
    import anyio
    from mcp import Client
    from storygen.mcp.bridge import build_client, build_server
    client = build_client(http) if isinstance(http, str) else http

    async def run():
        async with Client(build_server(client)) as session:
            return await session.call_tool(name, arguments)
    result = anyio.run(run)
    text = ''.join(getattr(item, 'text', '') for item in result.content)
    if result.is_error:
        raise RuntimeError(f'{name}: {text}')
    data = result.structured_content
    if isinstance(data, dict) and set(data) == {'result'}:
        return data['result']
    return data if data is not None else json.loads(text)


def parse_result(lines):
    lines = list(lines)
    # No `result` event means the session was cut off: an error until the stream proves otherwise.
    result = Result(tool_calls=tool_calls(lines), errors=tool_errors(lines), is_error=True)
    texts = []
    for event in _events(lines):
        if event.get('type') == 'system' and event.get('subtype') == 'init' and result.session_id is None:
            result.session_id = event.get('session_id')
        elif event.get('type') == 'assistant':
            texts += [item['text'] for item in (event.get('message') or {}).get('content') or []
                      if isinstance(item, dict) and item.get('type') == 'text' and item.get('text')]
        elif event.get('type') == 'result':
            result.cost_usd = event.get('total_cost_usd')
            result.usage = event.get('usage') or {}
            result.is_error = bool(event.get('is_error'))
            if event.get('result'):
                texts.append(event['result'])
    result.text = '\n'.join(texts)
    return result


def run_claude(cmd, out, timeout=1800):
    """Run `claude -p`, keep the whole stream in `out`, return the parsed result."""
    out = Path(out)
    proc = subprocess.run(cmd, cwd=out.parent, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          timeout=timeout)
    out.write_text(proc.stdout, encoding='utf-8')
    if proc.stderr:
        out.with_suffix('.stderr.txt').write_text(proc.stderr, encoding='utf-8')
    result = parse_result(proc.stdout.splitlines())
    result.is_error = result.is_error or proc.returncode != 0
    return result


def stand_env(extra=None):
    """The stand server's environment: no provider keys, and no OS credential store, which the author's Obscura shares.
    `extra` adds variables of a scenario, such as a fake key that lets the server read a provider's public model list."""
    from scripts.capture_screenshots import server_env
    return server_env() | dict(extra or {}) | {'PYTHON_KEYRING_BACKEND': 'keyring.backends.fail.Keyring'}


@contextlib.contextmanager
def start_stand(work, extra_env=None):
    """A fresh Obscura on a free port with `work/data`; stopped on exit."""
    from scripts.capture_screenshots import ensure_port_free, free_port, server_command, wait_for
    work = Path(work).resolve()
    data = work/'data'
    if data.exists() and any(data.iterdir()):
        raise SystemExit(f'{data} не порожній: стенд працює лише з новою текою')
    data.mkdir(parents=True, exist_ok=True)
    env_file = work/'empty.env'
    env_file.write_text('', encoding='utf-8')
    port = free_port()
    ensure_port_free(port)
    base = f'http://127.0.0.1:{port}'
    server = subprocess.Popen(server_command(data, port, env_file), cwd=ROOT, env=stand_env(extra_env),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(base+'/', server)
        yield Stand(port=port, base=base, data=data, mcp_config=write_mcp_config(work/'mcp.json', port))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Ізольований стенд для прогонів скілів Obscura.')
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--work', required=True)
    run = sub.add_parser('run')
    run.add_argument('--work', required=True)
    run.add_argument('--prompt-file', required=True)
    run.add_argument('--model', default='sonnet')
    run.add_argument('--budget', type=float, default=1.0)
    args = parser.parse_args(argv)
    with start_stand(args.work) as stand:
        if args.command == 'serve':
            print(f'Стенд: {stand.base}; MCP-конфіг: {stand.mcp_config}. Ctrl+C — зупинити.')
            with contextlib.suppress(KeyboardInterrupt):
                while True:
                    __import__('time').sleep(1)
            return 0
        prompt = Path(args.prompt_file).read_text(encoding='utf-8')
        result = run_claude(claude_command(prompt, mcp_config=stand.mcp_config, plugin_dir=PLUGIN, model=args.model,
                                           budget_usd=args.budget), Path(args.work)/'run.jsonl')
        for name, arguments in result.tool_calls:
            print(name, json.dumps(arguments, ensure_ascii=False)[:200])
        print(json.dumps({'cost_usd': result.cost_usd, 'usage': result.usage, 'is_error': result.is_error}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
