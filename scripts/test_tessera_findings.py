"""Parser checks for bin/tessera-findings. Run: pytest scripts/test_tessera_findings.py"""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("sep,name", [("-", "hyphen"), ("–", "en-dash"),
                                      ("—", "em-dash")])
def test_every_dash_a_human_types_is_parsed(tmp_path, sep, name):
    """The class was `[—-]` — em-dash and hyphen. macOS substitutes an EN-dash as you
    type, so `## F-001 – Title` parsed as nothing and the finding left the backlog with
    no signal, in the scanner whose entire job is that nothing goes untransferred."""
    md = tmp_path / "FINDINGS.md"
    md.write_text(f"# T\n\n## F-001 {sep} Title\n\n**Status:** open\n")
    assert [f["id"] for f in tf.parse_findings(md)] == ["F-001"], name


def test_a_finding_that_does_not_parse_is_LOUD_not_silent(tmp_path):
    """The durable half. Widening the regex fixes today's separator; this fixes the
    class — anything claiming to be a finding heading that fails to parse is reported,
    so the next unanticipated variant announces itself instead of vanishing."""
    md = tmp_path / "FINDINGS.md"
    md.write_text("# T\n\n## F-001 ~ Title\n\n**Status:** open\n")
    findings = tf.parse_findings(md)
    assert findings == []
    assert tf.is_nonconforming(md.read_text(), findings) is True


def test_an_unrelated_section_is_not_flagged_nonconforming(tmp_path):
    """The other direction, and the reason the old predicate was wrong both ways: it
    counted `## ` headings of ANY kind, so a FINDINGS.md carrying `## Overview` and no
    findings yet was reported as malformed."""
    md = tmp_path / "FINDINGS.md"
    md.write_text("# T\n\n## Overview\n\nnotes, no findings yet\n")
    assert tf.is_nonconforming(md.read_text(), tf.parse_findings(md)) is False


def test_a_wellformed_file_is_conforming(tmp_path):
    """Guards the obvious regression: a predicate that fires on everything."""
    md = tmp_path / "FINDINGS.md"
    md.write_text("# T\n\n## F-001 — A\n\n**Status:** open\n\n## F-002 – B\n\n"
                  "**Status:** open\n")
    findings = tf.parse_findings(md)
    assert len(findings) == 2
    assert tf.is_nonconforming(md.read_text(), findings) is False


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
