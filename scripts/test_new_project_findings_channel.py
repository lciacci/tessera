"""The scaffold must ship the findings channel — empty is not the same as missing.

Caught 2026-07-21 while adopting settempo. `docs/contracts/findings.md` states that EVERY
Tessera project carries `docs/FINDINGS.md`, and that the scanner deliberately distinguishes an
*empty* channel ("nothing open ✓") from a *missing* one ("channel missing"). All four existing
downstreams had the file — every one placed there by hand. `bin/tessera-new-project` never
created it, so every project born from the scaffold started life in the "missing" state, i.e.
permanently flagged by the framework's own SessionStart surface until someone noticed.

The contract had a producer requirement with no producer. This asserts the scaffold is one.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAFFOLD = REPO / "bin" / "tessera-new-project"
FINDINGS = REPO / "bin" / "tessera-findings"


def _scaffold(tmp_path, name="toy"):
    target = tmp_path / name
    out = subprocess.run([str(SCAFFOLD), str(target), name, "standard"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return target


def test_scaffold_ships_a_findings_channel(tmp_path):
    target = _scaffold(tmp_path)
    channel = target / "docs" / "FINDINGS.md"
    assert channel.is_file(), "scaffold did not create docs/FINDINGS.md"

    body = channel.read_text()
    # The scanner keys on `## F-NNN` sections and `**Status:**` lines; a channel that does not
    # explain its own shape is how a downstream invents an incompatible one.
    assert "**Status:**" in body
    assert "F-NNN" in body
    assert "toy" in body, "channel not personalized to the project name"


def test_scanner_reads_the_scaffold_as_empty_not_missing(tmp_path):
    """The distinction is the whole point — assert it end-to-end, not just file existence."""
    _scaffold(tmp_path)
    r = subprocess.run([sys.executable, str(FINDINGS), "--root", str(tmp_path)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "channel missing" not in r.stdout, f"scaffold reads as a MISSING channel:\n{r.stdout}"
    assert "nothing open" in r.stdout, r.stdout


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
