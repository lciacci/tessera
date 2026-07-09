"""Checks for bin/tessera-changelog. Run: pytest scripts/test_tessera_changelog.py"""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "bin" / "tessera-changelog"
_loader = SourceFileLoader("tessera_changelog", str(_path))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
tc = importlib.util.module_from_spec(_spec)
_loader.exec_module(tc)


def test_classify_maps_type_scope_breaking():
    assert tc.classify("feat(findings): add scan") == ("Added", "**findings:** add scan", False)
    assert tc.classify("fix: guard null") == ("Fixed", "guard null", False)
    assert tc.classify("docs(adr): 0005") == ("Documentation", "**adr:** 0005", False)
    assert tc.classify("feat!: drop v1 api")[2] is True  # breaking


def test_non_conventional_goes_to_other():
    assert tc.classify("Import baseline") == ("Other", "Import baseline", False)


def test_render_groups_and_omits_empty_sections():
    sections, breaking = tc.group(["feat(a): x", "fix: y", "feat!: z"])
    out = tc.render(sections, breaking, "## [1.0.0] - 2026-07-09")
    assert "### Added" in out and "### Fixed" in out
    assert "### ⚠ BREAKING CHANGES" in out
    assert "### Changed" not in out  # empty section omitted


def test_no_coauthor_trailer_can_appear():
    # Subject-only by construction: a trailer lives in bodies, never a subject.
    sections, _ = tc.group(["feat: real work"])
    out = tc.render(sections, [], "## [x]")
    assert "Co-Authored-By" not in out and "Co-authored-by" not in out


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
