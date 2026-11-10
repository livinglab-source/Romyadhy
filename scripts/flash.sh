#!/usr/bin/env bash
# Build and flash one firmware folder.
# Usage: scripts/flash.sh esp32-sensor-node
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-}"

if [[ -z "$TARGET" ]]; then
  echo "usage: $0 <firmware-folder>" >&2
  echo "available:" >&2
  find "$ROOT/firmware" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n' >&2
  exit 1
fi

DIR="$ROOT/firmware/$TARGET"
if [[ ! -d "$DIR" ]]; then
  echo "error: no such firmware folder: $DIR" >&2
  exit 1
fi

command -v pio >/dev/null 2>&1 || {
  echo "error: PlatformIO (pio) not installed. pip install platformio" >&2
  exit 1
}

cd "$DIR"
echo "==> building $TARGET"
pio run
echo "==> flashing $TARGET"
pio run -t upload
echo "==> opening serial monitor (Ctrl-C to exit)"
pio device monitor -b 115200