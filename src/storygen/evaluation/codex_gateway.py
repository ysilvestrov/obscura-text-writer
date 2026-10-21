import json
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from .gateway import GatewayFailure
from .models import EvaluationRequest, EvaluatorConfig, GatewayResult, FailureDetail
from .failures import api_failure, is_text_refusal, refusal_detail


class CodexGateway:
    """Тестування промпту через встановлений Codex CLI; без shell-інтерполяції."""

    def __init__(self, config: EvaluatorConfig, *, run=None, temp_root: Path | None = None):
        self.config = config
        self.run = run or subprocess.run
        self.temp_root = temp_root or Path("artifacts/tmp").resolve()

    def close(self):
        pass

    def complete(self, request: EvaluationRequest) -> GatewayResult:
        self.temp_root.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="judge-", dir=self.temp_root) as folder:
            root = Path(folder)
            schema = root / "schema.json"
            answer = root / "answer.json"
            schema.write_text(json.dumps(request.response_schema, ensure_ascii=False), encoding="utf-8")
            args = [self.config.codex_command, "exec", "--ignore-user-config", "--ephemeral", "--sandbox", "read-only",
                "--skip-git-repo-check", "--cd", str(root), "--output-schema", str(schema), "--output-last-message", str(answer), "--json"]
            if self.config.model:
                args += ["--model", self.config.model]
            args += ["-"]
            prompt = "\n\n".join(message["content"] for message in request.messages)
            try:
                process = self.run(args, input=prompt, text=True, encoding="utf-8", errors="replace",
                    capture_output=True, shell=False, timeout=self.config.timeout_seconds or 300, cwd=root)
            except subprocess.TimeoutExpired:
                raise GatewayFailure("codex_timeout: Час очікування Codex CLI вичерпано",
                    detail=FailureDetail(category='timeout', message='Час очікування Codex CLI вичерпано.')) from None
            except OSError as exc:
                raise GatewayFailure("codex_unavailable: Не вдалося запустити Codex CLI",
                    detail=FailureDetail(category='connection', message='Не вдалося запустити Codex CLI; errno=' + str(exc.errno))) from None
            if process.returncode != 0 or not answer.is_file():
                detail = FailureDetail(category='provider_error', message=f'Codex CLI не повернув завершений звіт; exit code={process.returncode}.')
                for line in process.stdout.splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(event, dict) or event.get('type') not in {'error', 'turn.failed'}:
                        continue
                    error = event.get('error', event)
                    if not isinstance(error, dict):
                        continue
                    detail = api_failure(SimpleNamespace(body=error), documents=[m['content'] for m in request.messages])
                    if is_text_refusal(error.get('message', '')):
                        detail = refusal_detail(error['message'])
                raise GatewayFailure('codex_failed: ' + detail.message, detail=detail)
            usage = {}
            for line in process.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "turn.completed":
                    usage = event.get("usage") or {}
            return GatewayResult(text=answer.read_text(encoding="utf-8-sig"), finish_reason="stop",
                usage=usage, duration_seconds=time.monotonic() - started)
