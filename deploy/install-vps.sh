#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/hassangomaa/stress-test-bot.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
SERVICE_NAME="stress-test-bot"

echo "==> Installing stress-test-bot to ${INSTALL_DIR}"
mkdir -p "$(dirname "${INSTALL_DIR}")"

if [[ -d "${INSTALL_DIR}/.git" ]]; then
  cd "${INSTALL_DIR}"
  git pull origin main
else
  git clone "${REPO_URL}" "${INSTALL_DIR}"
  cd "${INSTALL_DIR}"
fi

python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .

echo "==> Installing systemd unit + 05:00 Asia/Riyadh timer"
cp deploy/stress-test-bot.service /etc/systemd/system/${SERVICE_NAME}.service
cp deploy/stress-test-bot.timer /etc/systemd/system/${SERVICE_NAME}.timer
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.timer"
# Do not enable the service itself for boot — timer owns first start each day.
# After first start, Restart=always keeps the bot running forever.

touch /var/log/stress-test-bot.log
chmod 644 /var/log/stress-test-bot.log

echo "==> Done."
echo "==> Schedule: systemctl start ${SERVICE_NAME}.timer  (fires at 05:00 Asia/Riyadh)"
echo "==> Manual start now: systemctl start ${SERVICE_NAME}"
echo "==> Logs: tail -f /var/log/stress-test-bot.log"
