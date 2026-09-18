"""Tests for competitor-gemini-check message formatting and fallback."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "competitor_gemini_check",
    _SCRIPTS / "competitor-gemini-check.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["competitor_gemini_check"] = _mod
# competitor-gemini-check loads competitor-report-telegram internally
_spec.loader.exec_module(_mod)


def test_first_line_no_new():
    assert _mod.build_first_line([]) == "منافسون جدد: لا"


def test_first_line_with_new():
    line = _mod.build_first_line(["newclone.com"])
    assert line.startswith("منافسون جدد: نعم")
    assert "newclone.com" in line


def test_force_fallback_mode(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("COMPETITOR_LOOKUP_PATH", str(_SCRIPTS.parent.parent / "zaedl-store" / "credentials" / "competitor-lookup.json"))
    # Dry run should not require telegram or artisan
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "competitor-gemini-check.py"), "--dry-run", "--no-telegram", "--force-fallback"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(_SCRIPTS.parent),
    )
    assert proc.returncode == 0
    assert proc.stdout.strip().startswith("منافسون جدد:")
