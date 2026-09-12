#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODES_JSON="${ROOT}/configs/egress-nodes.json"
: "${HOSTINGER_API_TOKEN:?export HOSTINGER_API_TOKEN}"
BASE="${HOSTINGER_API_BASE:-https://developers.hostinger.com}"
hdr=(-H "Authorization: Bearer ${HOSTINGER_API_TOKEN}" -H "Accept: application/json")

echo "=== Hostinger inventory ==="
websites=$(curl -sf "${hdr[@]}" "$BASE/api/hosting/v1/websites" || echo '[]')
vms=$(curl -sf "${hdr[@]}" "$BASE/api/vps/v1/virtual-machines" || echo '[]')
echo "$vms" | jq '[.[] | {id, hostname, ip}]' 2>/dev/null | head -40
echo "--- egress-nodes enabled ---"
jq -r '.nodes[] | select(.enabled==true) | "\(.id)\t\(.public_ip)"' "$NODES_JSON"
