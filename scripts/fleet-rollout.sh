#!/usr/bin/env bash
# Roll out stress fleet to all enabled nodes in configs/egress-nodes.json
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODES_JSON="${ROOT}/configs/egress-nodes.json"
INSTALL_SCRIPT="${ROOT}/scripts/fleet-install-node.sh"

# Lab credentials (fin-core + fleet nodes)
FIN_CORE_PASS='6.CiFB1BQGAQTX81eMFz'
ECO7_PASS='Ax7a7pM0IPhbk49fs2kyaI8M'
SLT_OCR_KEY="${HOME}/.ssh/egyguests_vps"
TTAKKA_KEY="${HOME}/.ssh/cursor_ttakka"

ssh_pw() {
  local pass="$1" host="$2" port="$3" user="$4"
  SSHPASS="$pass" sshpass -e ssh -o StrictHostKeyChecking=accept-new \
    -o PreferredAuthentications=password -o PubkeyAuthentication=no \
    -p "$port" "${user}@${host}" "$5"
}

ssh_key() {
  local key="$1" host="$2" port="$3" user="$4"
  ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -p "$port" "${user}@${host}" "$5"
}

remote_install() {
  local node_id="$1" host="$2" port="$3" user="$4" auth="$5" mem="$6"
  echo ""
  echo "========== ROLLOUT ${node_id} @ ${host} =========="
  local remote_shell="bash -s -- ${node_id} ${mem}"
  if [[ "$node_id" == "ttakka" ]]; then
    remote_shell="sudo bash -s -- ${node_id} ${mem}"
  fi
  if [[ "$auth" == "password" ]]; then
    local pass="$FIN_CORE_PASS"
    if [[ "$node_id" == eco7-* ]]; then pass="$ECO7_PASS"; fi
    ssh_pw "$pass" "$host" "$port" "$user" "$remote_shell" < "$INSTALL_SCRIPT"
  else
    local key="$SLT_OCR_KEY"
    if [[ "$node_id" == "ttakka" ]]; then key="$TTAKKA_KEY"; fi
    ssh_key "$key" "$host" "$port" "$user" "$remote_shell" < "$INSTALL_SCRIPT"
  fi
}

echo "Fleet rollout from ${NODES_JSON}"
command -v jq >/dev/null || { echo "jq required" >&2; exit 1; }
command -v sshpass >/dev/null || { echo "sshpass required for password nodes" >&2; exit 1; }

while IFS= read -r node; do
  id=$(echo "$node" | jq -r '.id')
  enabled=$(echo "$node" | jq -r '.enabled')
  host=$(echo "$node" | jq -r '.public_ip')
  port=$(echo "$node" | jq -r '.ssh.port // 22')
  user=$(echo "$node" | jq -r '.ssh.user')
  auth=$(echo "$node" | jq -r '.ssh.auth')
  mem=$(echo "$node" | jq -r '.systemd.memory_max // "512M"')

  if [[ "$enabled" != "true" ]]; then
    echo "[SKIP] ${id} — $(echo "$node" | jq -r '.blocked_reason // "disabled"')"
    continue
  fi

  if ! remote_install "$id" "$host" "$port" "$user" "$auth" "$mem"; then
    echo "[FAIL] ${id} install failed" >&2
  else
    echo "[OK] ${id}"
  fi
done < <(jq -c '.nodes | sort_by(.rollout_order) | .[]' "$NODES_JSON")

echo ""
echo "==> Run: bash scripts/verify-egress-ip.sh"
echo "==> Run: python scripts/track-competitor-status.py --all-nodes"
