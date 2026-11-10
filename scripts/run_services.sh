#!/usr/bin/env bash
# Start the three Python services in the foreground (local development).
# Each service gets its own log prefix; Ctrl-C stops all of them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "error: .env not found. Run: cp .env.example .env" >&2
  exit 1
fi

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo "error: python not found at $PYTHON (create .venv or set PYTHON=...)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

pids=()
cleanup() {
  echo
  echo "stopping services..."
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for svc in mqtt-bridge data-logger telegram-bot; do
  if [[ -f "services/$svc/main.py" ]]; then
    entry="main.py"
  elif [[ -f "services/$svc/telegrambot.py" ]]; then
    entry="telegrambot.py"
  else
    echo "skip $svc (no main.py)" >&2
    continue
  fi
  echo "starting $svc ($entry)"
  "$PYTHON" "services/$svc/$entry" 2>&1 | sed -u "s/^/[$svc] /" &
  pids+=("$!")
done

wait