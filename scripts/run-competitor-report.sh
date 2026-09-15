#!/usr/bin/env bash
# Run competitor health + fleet visit report → Telegram.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
ENV_FILE="${INSTALL_DIR}/configs/competitor-report.env"
LOG_FILE="/var/log/stress-test-bot/competitor-report.log"

mkdir -p "$(dirname "$LOG_FILE")"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

{
  echo "===== $(date -Iseconds) competitor report start ====="
  cd "$INSTALL_DIR"
  if .venv/bin/python scripts/competitor-report-telegram.py --hours 6; then
    echo "telegram: sent OK"
  else
    echo "telegram: SEND FAILED" >&2
    exit 1
  fi
  echo "===== $(date -Iseconds) competitor report end ====="
} >> "$LOG_FILE" 2>&1
