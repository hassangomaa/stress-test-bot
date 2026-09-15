#!/usr/bin/env bash
# Fully remove competitor stress-bot from a fleet node.
set -euo pipefail

NODE_ID="${1:?node id required}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

UNIT="stress-test-bot-competitors@${NODE_ID}"
LEGACY="stress-test-bot-competitors"

systemctl stop "$UNIT" 2>/dev/null || true
systemctl disable "$UNIT" 2>/dev/null || true
systemctl mask "$UNIT" 2>/dev/null || true

systemctl stop "$LEGACY" 2>/dev/null || true
systemctl disable "$LEGACY" 2>/dev/null || true
systemctl mask "$LEGACY" 2>/dev/null || true

pkill -f 'stressbot run-multi' 2>/dev/null || true
pkill -f 'stressbot run' 2>/dev/null || true

rm -rf "/etc/systemd/system/${UNIT}.service.d" 2>/dev/null || true
rm -f "/etc/systemd/system/stress-test-bot-competitors@.service" 2>/dev/null || true
rm -f "/etc/systemd/system/${LEGACY}.service" 2>/dev/null || true

rm -rf "/var/log/stress-test-bot/${NODE_ID}"
rm -rf /opt/stress-test-bot

systemctl daemon-reload
echo "Purged competitor fleet on node=${NODE_ID}"
