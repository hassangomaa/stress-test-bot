#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/hassangomaa/stress-test-bot.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
SERVICE_NAME="stress-test-bot-competitors"
LEGACY_SERVICE="stress-test-bot"
LOG_DIR="/var/log/stress-test-bot"

echo "==> Installing competitor stress-test-bot to ${INSTALL_DIR}"
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

echo "==> Pausing legacy Zaedl stress-test-bot"
if systemctl is-active --quiet "${LEGACY_SERVICE}" 2>/dev/null; then
  systemctl stop "${LEGACY_SERVICE}" || true
fi
if systemctl is-enabled --quiet "${LEGACY_SERVICE}" 2>/dev/null; then
  systemctl disable "${LEGACY_SERVICE}" || true
fi
if systemctl is-active --quiet "${LEGACY_SERVICE}.timer" 2>/dev/null; then
  systemctl stop "${LEGACY_SERVICE}.timer" || true
fi
if systemctl is-enabled --quiet "${LEGACY_SERVICE}.timer" 2>/dev/null; then
  systemctl disable "${LEGACY_SERVICE}.timer" || true
fi

echo "==> Installing competitor systemd unit"
mkdir -p "${LOG_DIR}"
cp deploy/stress-test-bot-competitors.service "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

touch "${LOG_DIR}/orchestrator.log"
chmod 644 "${LOG_DIR}/orchestrator.log"

echo "==> Done."
echo "==> Status: systemctl status ${SERVICE_NAME}"
echo "==> Logs: tail -f ${LOG_DIR}/orchestrator.log"
echo "==> Per-site: ls -la ${LOG_DIR}/comp-*.log"
