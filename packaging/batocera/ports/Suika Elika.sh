#!/bin/sh
set -eu

PORTS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
GAME_DIR="$PORTS_DIR/.data/SuikaElika"
PYTHON="${SUIKA_ELIKA_PYTHON:-python3}"

exec "$PYTHON" "$GAME_DIR/SuikaElika.pygame" "$@"
