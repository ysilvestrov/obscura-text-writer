#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT=8760
DATA_DIR=""
OPEN_BROWSER=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Port|--port|-p)
      PORT="$2"
      shift 2
      ;;
    -DataDir|--data-dir|-d)
      DATA_DIR="$2"
      shift 2
      ;;
    --no-browser)
      OPEN_BROWSER=0
      shift
      ;;
    *)
      echo "Невідомий аргумент: $1" >&2
      exit 1
      ;;
  esac
done

if [ -z "$DATA_DIR" ]; then
  DATA_DIR="$PROJECT_ROOT/data"
fi

PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
  else
    echo "Помилка: Python не знайдено. Активуйте nix devShell або створіть .venv." >&2
    exit 1
  fi
fi

ARGS=(
  --data-dir "$DATA_DIR"
  --env-file "$PROJECT_ROOT/.env"
  --port "$PORT"
)

if [ "$OPEN_BROWSER" -eq 1 ]; then
  ARGS+=(--open-browser)
fi

exec "$PYTHON" -m storygen.server "${ARGS[@]}"
