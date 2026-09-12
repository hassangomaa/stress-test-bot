#!/usr/bin/env bash
# POC: verify each fleet node's public egress IP matches egress-nodes.json
# Usage: source env.fleet.poc && bash tasks/PRPs/poc/verify-egress-ip.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
NODES_JSON="${STRESSBOT_EGRESS_NODES:-$SCRIPT_DIR/egress-nodes.json}"

if [[ -f "$REPO_ROOT/tasks/PRPs/poc/env.fleet.poc" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/tasks/PRPs/poc/env.fleet.poc"
fi

pass=0
fail=0
skip=0

ssh_egress() {
  local host="$1" port="$2" user="$3" auth="$4" key="${5:-}" pass="${6:-}"
  local cmd="curl -s --max-time 15 https://ifconfig.me || curl -s --max-time 15 https://api.ipify.org"

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

echo "=== Fleet egress IP verification ==="
echo "Registry: $NODES_JSON"
echo

while IFS= read -r line; do
  id=$(echo "$line" | jq -r '.id')
  expected=$(echo "$line" | jq -r '.public_ip')
  enabled=$(echo "$line" | jq -r '.enabled')
  user=$(echo "$line" | jq -r '.ssh.user')
  port=$(echo "$line" | jq -r '.ssh.port')
  auth=$(echo "$line" | jq -r '.ssh.auth')

  if [[ "$enabled" != "true" ]]; then
    echo "[SKIP] $id — disabled ($(echo "$line" | jq -r '.blocked_reason // "enabled=false"'))"
    skip=$((skip + 1))
    continue
  fi

  key=""
  password=""
  case "$id" in
    fin-core) password="${SSHPASS_FIN_CORE:-}" ;;
    slt-ocr) key="${SLT_OCR_SSH_KEY:-}" ;;
    slt-shared) password="${SSHPASS_SLT_SHARED:-}" ;;
    eco7-dev|eco7-prod) password="${SSHPASS_ECO7:-}" ;;
    ttakka)
      key="${TTAKKA_SSH_KEY:-}"
      user="${TTAKKA_DEPLOY_USER:-deploy}"
      ;;
  esac

  host="$expected"
  actual=$(ssh_egress "$host" "$port" "$user" "$auth" "$key" "$password" || true)
  actual=$(echo "$actual" | tr -d '[:space:]')

  if [[ -z "$actual" ]]; then
    echo "[FAIL] $id — SSH or curl failed (expected $expected)"
    fail=$((fail + 1))
  elif [[ "$actual" == "$expected" ]]; then
    echo "[OK]   $id — $actual"
    pass=$((pass + 1))
  else
    echo "[FAIL] $id — got $actual expected $expected"
    fail=$((fail + 1))
  fi
done < <(jq -c '.nodes[]' "$NODES_JSON")

echo
echo "Summary: ok=$pass fail=$fail skip=$skip"
[[ "$fail" -eq 0 ]]
