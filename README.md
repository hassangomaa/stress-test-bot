# stress-test-bot

CLI load tester for fin-core storefront checkout journeys (Zaedl, Altmiz). Generates synthetic users and cards (Luhn-valid PANs) and drives the same HTTP steps a real browser would.

**Warning:** `dry-run` and `run` hit real URLs. Use only against environments you own and have permission to load-test. Default Zaedl profile targets production.

## Requirements

- Python 3.11+

## Install

```bash
cd stress-test-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## List profiles

```bash
python -m stressbot list-profiles
```

## Dry-run (single journey)

Smoke-test one full journey without starting the worker pool:

```bash
# Zaedl production (from configs/profiles/zaedl.json → configs/urls.json prod URL)
python -m stressbot dry-run --profile zaedl --url-key prod

# Local Zaedl storefront
python -m stressbot dry-run --profile zaedl --url-key local
```

## Run (continuous load)

Runs until you press Ctrl+C. Worker count defaults to the profile JSON (`zaedl` uses 200 unless overridden):

```bash
# Zaedl production
python -m stressbot run --profile zaedl --url-key prod

# Fewer workers, gradual ramp (50 workers every 10s)
python -m stressbot run --profile zaedl --url-key prod --workers 50 --ramp 25:10s
```

## Configuration

| Path | Purpose |
|------|---------|
| `configs/urls.json` | Base URLs per brand (`prod` / `local`) |
| `configs/profiles/*.json` | Journey steps, workers, delays, payment methods |

## Tests

```bash
pytest -q
```
