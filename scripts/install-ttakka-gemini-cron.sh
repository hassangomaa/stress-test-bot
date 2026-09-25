#!/usr/bin/env bash
# Install 2x-daily Gemini ping on TtaKkaa VPS → TtaKkaa ops Telegram.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
CRON_FILE="/etc/cron.d/ttakka-gemini-ping"
RUNNER="${INSTALL_DIR}/scripts/run-ttakka-node-gemini-ping.sh"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo" >&2
  exit 1
fi

chmod +x "${INSTALL_DIR}/scripts/run-ttakka-node-gemini-ping.sh"
chmod +x "${INSTALL_DIR}/scripts/ttakka-node-gemini-ping.py"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
TZ=Asia/Riyadh

# TtaKkaa node Gemini + fleet visit ping → TtaKkaa ops Telegram
# cron schedules in SYSTEM time (UTC); TZ= above only affects the command env.
# 05:20/17:20 UTC = 08:20/20:20 Riyadh (after the 08:00/20:00 ops brief).
20 5,17 * * * root ${RUNNER}
EOF
chmod 644 "$CRON_FILE"

mkdir -p /var/log/stress-test-bot

if command -v at >/dev/null; then
  echo "${RUNNER}" | at now + 1 minute 2>/dev/null || true
else
  nohup bash -c "sleep 60; ${RUNNER}" >>/var/log/stress-test-bot/ttakka-gemini-bootstrap.log 2>&1 &
fi

echo "Installed ${CRON_FILE}"
cat "$CRON_FILE"
