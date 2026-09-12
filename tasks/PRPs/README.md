# PRPs — Product Requirement Prompts (stress-test-bot)

Implementation-ready specs for future agent sessions. Each PRP includes the plan, POC credentials, and runnable config stubs.

| PRP | Status | POC |
|-----|--------|-----|
| [Distributed Headless Stress Fleet](./distributed-headless-stress-fleet.md) | **Planned** (not implemented) | [`poc/`](./poc/) |

## Quick start (fleet POC)

```bash
cd /Users/hassangomaa/Projects/fin-core-ecosystem/stress-test-bot
source tasks/PRPs/poc/env.fleet.poc   # exports HOSTINGER_API_TOKEN, SSH helpers
bash tasks/PRPs/poc/verify-egress-ip.sh
python -m stressbot dry-run --profile comp-goldalreem --url-key prod
```

Vault mirrors: `geoenergy-ecosystem/credentials/vault.json`, `zaedl-store/credentials/vault.json`.
