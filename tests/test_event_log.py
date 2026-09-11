import json
import os
from pathlib import Path

from stressbot.event_log import EventLogger


def test_event_log_writes_json_with_unix_ts(tmp_path, monkeypatch):
    monkeypatch.setenv("STRESSBOT_LOG_DIR", str(tmp_path))
    EventLogger._instances.clear()

    logger = EventLogger.for_profile("comp-goldalreem", "https://goldalreem.com")
    logger.step("catalog", ok=True, http_status=200, duration_ms=12.5)

    log_file = tmp_path / "comp-goldalreem.log"
    assert log_file.exists()
    line = log_file.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["event"] == "step"
    assert payload["step"] == "catalog"
    assert payload["profile"] == "comp-goldalreem"
    assert isinstance(payload["ts_unix"], float)


def test_load_manifest():
    from stressbot.config import load_manifest

    manifest = load_manifest("competitors-all")
    assert len(manifest["profiles"]) == 9
    assert "comp-agdalreem" in manifest["profiles"]
