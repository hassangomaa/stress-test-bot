#!/usr/bin/env bash
# Permanently stop stress-test-bot on the fin-core VPS (never auto-restart).
set -euo pipefail

SERVICE=stress-test-bot

systemctl stop "${SERVICE}.service" 2>/dev/null || true
systemctl stop "${SERVICE}.timer" 2>/dev/null || true
systemctl disable "${SERVICE}.service" 2>/dev/null || true
systemctl disable "${SERVICE}.timer" 2>/dev/null || true
systemctl mask "${SERVICE}.service" 2>/dev/null || true
systemctl mask "${SERVICE}.timer" 2>/dev/null || true

pkill -f 'stressbot run' 2>/dev/null || true

echo "stress-test-bot stopped, disabled, and masked."
