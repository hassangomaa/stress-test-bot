#!/usr/bin/env bash
# 2x-daily Gemini competitor discovery + fallback → DB + Telegram.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
ENV_FILE="${INSTALL_DIR}/configs/competitor-gemini.env"
LOG_FILE="/var/log/stress-test-bot/competitor-gemini.log"

mkdir -p "$(dirname "$LOG_FILE")" /var/lib/stress-test-bot

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

{
  echo "===== $(date -Iseconds) competitor gemini check start ====="
  cd "$INSTALL_DIR"
  PYTHON="${INSTALL_DIR}/.venv/bin/python"
  if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
  fi
  if "$PYTHON" scripts/competitor-gemini-check.py --hours 12; then
    echo "telegram: sent OK"
  else
    echo "telegram: SEND FAILED" >&2
    exit 1
  fi
  echo "===== $(date -Iseconds) competitor gemini check end ====="
} >> "$LOG_FILE" 2>&1
