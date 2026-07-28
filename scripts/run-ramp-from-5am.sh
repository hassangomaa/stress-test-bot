#!/usr/bin/env bash
# Wait until 05:00 Asia/Riyadh (today if still before 5 AM), then run exponential ramp forever.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROFILE="${STRESSBOT_PROFILE:-zaedl-ramp-10m}"
URL_KEY="${STRESSBOT_URL_KEY:-prod}"
LOG_DIR="${STRESSBOT_LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="${STRESSBOT_LOG_FILE:-$LOG_DIR/zaedl-ramp-10m.log}"
PID_FILE="${STRESSBOT_PID_FILE:-$LOG_DIR/zaedl-ramp-10m.pid}"

PYTHON="${STRESSBOT_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

export STRESSBOT_TZ="${STRESSBOT_TZ:-Asia/Riyadh}"
export STRESSBOT_START_HOUR="${STRESSBOT_START_HOUR:-5}"
export STRESSBOT_START_MINUTE="${STRESSBOT_START_MINUTE:-0}"

START_INFO="$("$PYTHON" - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

tz = ZoneInfo(os.environ["STRESSBOT_TZ"])
hour = int(os.environ["STRESSBOT_START_HOUR"])
minute = int(os.environ["STRESSBOT_START_MINUTE"])
now = datetime.now(tz)
target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
if now >= target:
    target = target + timedelta(days=1)
sleep_s = max(0, int((target - now).total_seconds()))
print(f"{target.isoformat()}|{sleep_s}")
PY
)"

TARGET_ISO="${START_INFO%%|*}"
SLEEP_S="${START_INFO##*|}"

{
  echo "==> stress-test-bot exponential ramp"
  echo "    profile=$PROFILE url_key=$URL_KEY"
  echo "    timezone=$STRESSBOT_TZ start=$TARGET_ISO"
  echo "    sleep_s=$SLEEP_S"
  echo "    log=$LOG_FILE"
  echo "    pattern: 1 → 2 → 4 → 8 … visits every 10 minutes (forever)"
} | tee -a "$LOG_FILE"

if [[ "$SLEEP_S" -gt 0 ]]; then
  echo "==> Waiting until $TARGET_ISO ($SLEEP_S seconds)…" | tee -a "$LOG_FILE"
  sleep "$SLEEP_S"
fi

echo "==> Starting bot at $(TZ="$STRESSBOT_TZ" date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$LOG_FILE"
export PYTHONUNBUFFERED=1
echo $$ >"$PID_FILE"
exec "$PYTHON" -m stressbot run --profile "$PROFILE" --url-key "$URL_KEY" >>"$LOG_FILE" 2>&1
