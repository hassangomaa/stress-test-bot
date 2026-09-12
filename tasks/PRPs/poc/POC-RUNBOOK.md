# Distributed Headless Stress Fleet — POC Runbook

Educational lab POC for multi-IP competitor stress testing. **Not deployed yet** — use this when implementing the PRP.

## Prerequisites

- Mac with vault SSH keys: `~/.ssh/egyguests_vps`, `~/.ssh/cursor_ttakka`
- `sshpass`, `jq`, Python 3.11+
- stress-test-bot installed: `pip install -e .` from repo root

## 1. Load environment

```bash
cd /Users/hassangomaa/Projects/fin-core-ecosystem/stress-test-bot
source tasks/PRPs/poc/env.fleet.poc
```

All passwords and API tokens are in [`credentials.json`](./credentials.json).

## 2. Hostinger inventory (Phase 0)

```bash
bash tasks/PRPs/poc/hostinger-inventory.sh
```

Expected: API returns websites + VPS list; VM `1652428` → `69.62.114.63`.

## 3. Verify egress IPs (Phase 0)

```bash
bash tasks/PRPs/poc/verify-egress-ip.sh
```

Expected: each **enabled** node reports `ifconfig.me` matching `egress-nodes.json`.

## 4. Single-node journey smoke (current bot — fin-core)

On fin-core VPS (already running `stress-test-bot-competitors`):

```bash
export SSHPASS="$SSHPASS_FIN_CORE"
sshpass -e ssh -o StrictHostKeyChecking=accept-new root@31.97.180.152 \
  'cd /opt/stress-test-bot && .venv/bin/python -m stressbot dry-run --profile comp-goldalreem --url-key prod'
```

Repeat for `comp-agdalreem` (PHP clone).

## 5. Local dry-run (Mac egress — not fleet)

```bash
python -m stressbot dry-run --profile comp-goldalreem --url-key prod
```

## 6. Full manifest (single node, foreground)

```bash
python -m stressbot run-multi --manifest competitors-all --url-key prod
```

Production uses interval scheduler via systemd on fin-core.

## 7. Fleet deploy (when implemented)

Planned commands (not built yet):

```bash
# Per-node install via SSH
bash scripts/fleet-install-node.sh --node slt-ocr --egress-nodes tasks/PRPs/poc/egress-nodes.json

# Or CLI orchestrator
python -m stressbot fleet-deploy --nodes tasks/PRPs/poc/egress-nodes.json --only slt-ocr
```

Systemd template (planned): `stress-test-bot-competitors@.service` with:

```ini
Environment=STRESSBOT_NODE_ID=%i
Environment=STRESSBOT_LOG_DIR=/var/log/stress-test-bot/%i
```

## 8. Fleet health (when implemented)

```bash
python scripts/track-competitor-status.py --all-nodes --since 1h
```

Success: ≥3 distinct `egress_ip` in logs; 0 `thread_crash`; all 9 domains `journey_end ok=true` per node.

## 9. Competitor targets (9 domains)

| Domain | Profile | Runner |
|--------|---------|--------|
| goldalreem.com | comp-goldalreem | react_clone |
| akdalreem.com | comp-akdalreem | react_clone |
| hussingold.com | comp-hussingold | react_clone |
| sadadgold.com | comp-sadadgold | react_clone |
| goldsadad.com | comp-goldsadad | react_clone |
| hussinsadad.com | comp-hussinsadad | react_clone |
| oqdalreem.com | comp-oqdalreem | react_clone |
| sadadcash.com | comp-sadadcash | react_clone |
| agdalreem.com | comp-agdalreem | php_clone |

Registry: `zaedl-store/credentials/competitor-lookup.json` → `stress_test_profiles`.

## 10. Rollout order

1. fin-core — add `STRESSBOT_NODE_ID=fin-core` to existing unit
2. slt-ocr
3. slt-shared (light: 1 worker, 256M RAM or cron fallback)
4. eco7-dev, eco7-prod
5. ttakka
6. **Skip** mysaudicore until vault password added

## Related files

| File | Purpose |
|------|---------|
| [`../distributed-headless-stress-fleet.md`](../distributed-headless-stress-fleet.md) | Full PRP plan |
| [`egress-nodes.json`](./egress-nodes.json) | Node registry POC |
| [`credentials.json`](./credentials.json) | Plaintext lab creds |
| [`../../configs/competitors-all.json`](../../configs/competitors-all.json) | Manifest |
| [`../../../zaedl-store/credentials/competitor-lookup.json`](../../../zaedl-store/credentials/competitor-lookup.json) | OSINT + stress profile registry |
