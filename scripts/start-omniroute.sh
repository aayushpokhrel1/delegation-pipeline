#!/usr/bin/env bash
# Manually start the OmniRoute gateway if it isn't already running (macOS/Linux).
# Idempotent: does nothing if the port is already serving. Backgrounds the process.
set -euo pipefail

PORT=20128
LOG="$HOME/.claude/omniroute.log"
mkdir -p "$HOME/.claude"

if curl -s -m 3 -o /dev/null "http://localhost:$PORT/v1/models" 2>/dev/null; then
  echo "OmniRoute already running on port $PORT"
  exit 0
fi

if command -v omniroute >/dev/null 2>&1; then
  CMD=(omniroute)
else
  CMD=(npx --yes omniroute)
fi

nohup "${CMD[@]}" >"$LOG" 2>&1 &
echo "Launched OmniRoute (${CMD[*]}); log: $LOG"
