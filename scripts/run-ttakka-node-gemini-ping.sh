#!/usr/bin/env bash
# TtaKkaa worker node Gemini ping → TtaKkaa ops Telegram.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
ENV_FILE="${INSTALL_DIR}/configs/ttakka-gemini.env"
LOG_FILE="/var/log/stress-test-bot/ttakka-gemini-ping.log"

mkdir -p "$(dirname "$LOG_FILE")"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

export STRESSBOT_NODE_ID="${STRESSBOT_NODE_ID:-ttakka}"

{
  echo "===== $(date -Iseconds) ttakka gemini ping start ====="
  cd "$INSTALL_DIR"
  PYTHON="$(command -v python3)"
  if [[ -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
    PYTHON="${INSTALL_DIR}/.venv/bin/python"
  fi
  if "$PYTHON" scripts/ttakka-node-gemini-ping.py --hours 12; then
    echo "telegram: sent OK"
  else
    echo "telegram: SEND FAILED" >&2
    exit 1
  fi
  echo "===== $(date -Iseconds) ttakka gemini ping end ====="
} >> "$LOG_FILE" 2>&1
