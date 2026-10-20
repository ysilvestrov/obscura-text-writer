import json
import subprocess
import tempfile
import time
from pathlib import Path

from .gateway import GatewayFailure
from .models import EvaluationRequest, EvaluatorConfig, GatewayResult


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
                raise GatewayFailure("codex_timeout: Час очікування Codex CLI вичерпано") from None
            except OSError:
                raise GatewayFailure("codex_unavailable: Не вдалося запустити Codex CLI") from None
            if process.returncode != 0 or not answer.is_file():
                raise GatewayFailure("codex_failed: Codex CLI не повернув завершений звіт")
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
