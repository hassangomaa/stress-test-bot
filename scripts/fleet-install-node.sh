#!/usr/bin/env bash
# Install stress-test-bot fleet worker on THIS host (run via SSH).
# Usage: fleet-install-node.sh <node-id> [memory_max e.g. 768M]
set -euo pipefail

NODE_ID="${1:?node id required (e.g. fin-core)}"
MEMORY_MAX="${2:-512M}"
REPO_URL="${REPO_URL:-https://github.com/hassangomaa/stress-test-bot.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/stress-test-bot}"
LOG_DIR="/var/log/stress-test-bot/${NODE_ID}"
UNIT_TEMPLATE="stress-test-bot-competitors@.service"
LEGACY_UNIT="stress-test-bot-competitors"

echo "==> Fleet install node=${NODE_ID} memory_max=${MEMORY_MAX}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (or via sudo)" >&2
  exit 1
fi

command -v python3 >/dev/null || { echo "python3 missing" >&2; exit 1; }
command -v git >/dev/null || { echo "git missing" >&2; exit 1; }

mkdir -p "$(dirname "${INSTALL_DIR}")"
if [[ -d "${INSTALL_DIR}/.git" ]]; then
  cd "${INSTALL_DIR}"
  git fetch origin main
  git reset --hard origin/main
else
  git clone "${REPO_URL}" "${INSTALL_DIR}"
  cd "${INSTALL_DIR}"
fi

python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .

mkdir -p "${LOG_DIR}"
chmod 755 "${LOG_DIR}"
touch "${LOG_DIR}/orchestrator.log"
chmod 644 "${LOG_DIR}/orchestrator.log"

cp "deploy/${UNIT_TEMPLATE}" "/etc/systemd/system/${UNIT_TEMPLATE}"

DROPIN_DIR="/etc/systemd/system/${LEGACY_UNIT}@${NODE_ID}.service.d"
mkdir -p "${DROPIN_DIR}"
cat > "${DROPIN_DIR}/memory.conf" <<EOF
[Service]
MemoryMax=${MEMORY_MAX}
EOF

if systemctl is-active --quiet "${LEGACY_UNIT}" 2>/dev/null; then
  echo "==> Stopping legacy unit ${LEGACY_UNIT}"
  systemctl stop "${LEGACY_UNIT}" || true
  systemctl disable "${LEGACY_UNIT}" || true
fi

systemctl daemon-reload
systemctl enable "${LEGACY_UNIT}@${NODE_ID}"
systemctl restart "${LEGACY_UNIT}@${NODE_ID}"

sleep 2
systemctl is-active "${LEGACY_UNIT}@${NODE_ID}"
echo "==> Logs: tail -f ${LOG_DIR}/orchestrator.log"
echo "==> Egress check:"
curl -s --max-time 12 https://ifconfig.me || true
