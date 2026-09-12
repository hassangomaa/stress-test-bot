#!/usr/bin/env bash
# POC Phase 0: fetch Hostinger websites + VPS VMs; diff public IPs vs egress-nodes.json
# Usage: source env.fleet.poc && bash tasks/PRPs/poc/hostinger-inventory.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
NODES_JSON="${STRESSBOT_EGRESS_NODES:-$SCRIPT_DIR/egress-nodes.json}"

if [[ -f "$REPO_ROOT/tasks/PRPs/poc/env.fleet.poc" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/tasks/PRPs/poc/env.fleet.poc"
fi

: "${HOSTINGER_API_TOKEN:?Set HOSTINGER_API_TOKEN (see env.fleet.poc)}"
BASE="${HOSTINGER_API_BASE:-https://developers.hostinger.com}"

hdr=(-H "Authorization: Bearer ${HOSTINGER_API_TOKEN}" -H "Accept: application/json")

echo "=== Hostinger API inventory ==="
echo "API: $BASE"
echo

websites=$(curl -sf "${hdr[@]}" "$BASE/api/hosting/v1/websites" || echo '{"error":"websites_fetch_failed"}')
vms=$(curl -sf "${hdr[@]}" "$BASE/api/vps/v1/virtual-machines" || echo '{"error":"vms_fetch_failed"}')

echo "--- Websites (truncated) ---"
echo "$websites" | jq '.[0:5]' 2>/dev/null || echo "$websites" | head -c 2000
echo

echo "--- VPS VMs (truncated) ---"
echo "$vms" | jq '.[0:5]' 2>/dev/null || echo "$vms" | head -c 2000
echo

echo "--- egress-nodes.json enabled IPs ---"
jq -r '.nodes[] | select(.enabled==true) | "\(.id)\t\(.public_ip)"' "$NODES_JSON"
echo

echo "Manual cross-check: VM 1652428 should be 69.62.114.63 (slt-ocr)"
echo "fin-core A records in zaedl-store/credentials/vault.json → 31.97.180.152"
