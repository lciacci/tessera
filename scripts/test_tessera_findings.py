"""Parser checks for bin/tessera-findings. Run: pytest scripts/test_tessera_findings.py"""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "bin" / "tessera-findings"
_loader = SourceFileLoader("tessera_findings", str(_path))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
tf = importlib.util.module_from_spec(_spec)
_loader.exec_module(tf)

SAMPLE = """# Findings

## F-001 — transferred one

**Status:** transferred:ADR-0004
body

## F-002 — open one

**Status:** open
body

## F-003 — no status line, defaults open

**Surfaced:** today
body
"""


def _parse(tmp_path):
    md = tmp_path / "FINDINGS.md"
    md.write_text(SAMPLE)
    return tf.parse_findings(md)


def test_parses_all_headers(tmp_path):
    assert [f["id"] for f in _parse(tmp_path)] == ["F-001", "F-002", "F-003"]


def test_status_extracted_and_defaults_open(tmp_path):
    by_id = {f["id"]: f["status"] for f in _parse(tmp_path)}
    assert by_id["F-001"] == "transferred:ADR-0004"
    assert by_id["F-002"] == "open"
    assert by_id["F-003"] == "open"  # missing Status line => open, never dropped


def test_is_open_only_matches_open_state(tmp_path):
    opens = [f["id"] for f in _parse(tmp_path) if tf.is_open(f["status"])]
    assert opens == ["F-002", "F-003"]  # transferred is not open


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
