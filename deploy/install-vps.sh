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

echo "==> Installing systemd unit"
cp deploy/stress-test-bot.service /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

touch /var/log/stress-test-bot.log
chmod 644 /var/log/stress-test-bot.log

echo "==> Done. Start with: systemctl start ${SERVICE_NAME}"
echo "==> Logs: tail -f /var/log/stress-test-bot.log"
