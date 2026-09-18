#!/usr/bin/env bash
# Install 2x-daily competitor Gemini check on fin-core VPS.
# Replaces the old 6-hour competitor-report cron.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
CRON_FILE="/etc/cron.d/fin-core-competitor-gemini"
OLD_CRON="/etc/cron.d/fin-core-competitor-report"
RUNNER="${INSTALL_DIR}/scripts/run-competitor-gemini-check.sh"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

command -v sshpass >/dev/null || apt-get install -y -qq sshpass
command -v at >/dev/null || apt-get install -y -qq at

chmod +x "${INSTALL_DIR}/scripts/run-competitor-gemini-check.sh"
chmod +x "${INSTALL_DIR}/scripts/competitor-gemini-check.py"

rm -f "$OLD_CRON"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
TZ=Asia/Riyadh

# Competitor Gemini discovery + health report → Zaedl Telegram (08:00 + 20:00)
0 8,20 * * * root ${RUNNER}
EOF
chmod 644 "$CRON_FILE"

mkdir -p /var/lib/stress-test-bot
mkdir -p "$(dirname /var/log/stress-test-bot/competitor-gemini.log)"

# Bootstrap: first run in 1 minute
if command -v at >/dev/null; then
  echo "${RUNNER}" | at now + 1 minute 2>/dev/null || true
else
  nohup bash -c "sleep 60; ${RUNNER}" >/var/log/stress-test-bot/competitor-gemini-bootstrap.log 2>&1 &
fi

echo "Cron installed: ${CRON_FILE}"
echo "Removed old cron: ${OLD_CRON} (if existed)"
echo "First report scheduled ~1 minute from now."
cat "$CRON_FILE"
