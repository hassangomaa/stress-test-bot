#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODES_JSON="${ROOT}/configs/egress-nodes.json"

FIN_CORE_PASS='6.CiFB1BQGAQTX81eMFz'
ECO7_PASS='Ax7a7pM0IPhbk49fs2kyaI8M'

pass=0
fail=0
skip=0

ssh_egress() {
  local host="$1" port="$2" user="$3" auth="$4" key="${5:-}" pass="${6:-}"
  local cmd="curl -s --max-time 12 https://ifconfig.me || curl -s --max-time 12 https://api.ipify.org"
  if [[ "$auth" == "key" && -n "$key" ]]; then
    ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
      -p "$port" "${user}@${host}" "$cmd" 2>/dev/null || return 1
  elif [[ "$auth" == "password" && -n "$pass" ]]; then
    SSHPASS="$pass" sshpass -e ssh -o StrictHostKeyChecking=accept-new \
      -o PreferredAuthentications=password -o PubkeyAuthentication=no \
      -p "$port" "${user}@${host}" "$cmd" 2>/dev/null || return 1
  else
    return 2
  fi
}

echo "=== Fleet egress verification ==="

while IFS= read -r node; do
  id=$(echo "$node" | jq -r '.id')
  expected=$(echo "$node" | jq -r '.public_ip')
  enabled=$(echo "$node" | jq -r '.enabled')
  user=$(echo "$node" | jq -r '.ssh.user')
  port=$(echo "$node" | jq -r '.ssh.port // 22')
  auth=$(echo "$node" | jq -r '.ssh.auth')

  if [[ "$enabled" != "true" ]]; then
    echo "[SKIP] $id"
    skip=$((skip + 1))
    continue
  fi

  key=""
  password=""
  case "$id" in
    fin-core) password="$FIN_CORE_PASS" ;;
    slt-ocr) key="${HOME}/.ssh/egyguests_vps" ;;
    eco7-dev|eco7-prod) password="$ECO7_PASS" ;;
    ttakka) key="${HOME}/.ssh/cursor_ttakka"; user="deploy" ;;
  esac

  actual=$(ssh_egress "$expected" "$port" "$user" "$auth" "$key" "$password" || true)
  actual=$(echo "$actual" | tr -d '[:space:]')

  if [[ -z "$actual" ]]; then
    echo "[FAIL] $id — SSH/curl failed (expected $expected)"
    fail=$((fail + 1))
  elif [[ "$actual" == "$expected" ]]; then
    echo "[OK]   $id — $actual"
    pass=$((pass + 1))
  else
    echo "[FAIL] $id — got $actual expected $expected"
    fail=$((fail + 1))
  fi
done < <(jq -c '.nodes[]' "$NODES_JSON")

echo "Summary: ok=$pass fail=$fail skip=$skip"
[[ "$fail" -eq 0 ]]
