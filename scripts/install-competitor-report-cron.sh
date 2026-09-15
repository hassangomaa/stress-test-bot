#!/usr/bin/env bash
# Install 6-hour competitor Telegram report on fin-core VPS.
# First run: 10 minutes after install. Then every 6 hours.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
CRON_FILE="/etc/cron.d/fin-core-competitor-report"
RUNNER="${INSTALL_DIR}/scripts/run-competitor-report.sh"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

command -v sshpass >/dev/null || apt-get install -y -qq sshpass

chmod +x "${INSTALL_DIR}/scripts/run-competitor-report.sh"
chmod +x "${INSTALL_DIR}/scripts/competitor-report-telegram.py"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
TZ=Asia/Riyadh

# Competitor health + bot visit report → Zaedl Telegram (every 6 hours)
0 */6 * * * root ${RUNNER}
EOF
chmod 644 "$CRON_FILE"

# One-shot first run in 10 minutes
if command -v at >/dev/null; then
  echo "${RUNNER}" | at now + 10 minutes 2>/dev/null || true
fi

# Fallback one-shot via sleep background if at unavailable
if ! command -v at >/dev/null; then
  nohup bash -c "sleep 600; ${RUNNER}" >/var/log/stress-test-bot/competitor-report-bootstrap.log 2>&1 &
fi

echo "Cron installed: ${CRON_FILE}"
echo "First report scheduled ~10 minutes from now."
crontab -l 2>/dev/null || true
cat "$CRON_FILE"
