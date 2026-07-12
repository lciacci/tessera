"""Regression tests for doccheck — one per doc-drift bug a human caught by hand.

THIS FILE IS THE POINT. Six doc-drift bugs were found 2026-07-09..11, every one by Lorenzo
asking "all docs updated?" on a hunch, and every one fixed without leaving a check behind —
so the next was found the same way. The base skill's bug-fix workflow says: write a failing
test that reproduces the bug BEFORE fixing it. We did that zero times out of six.

Each test below reintroduces a real bug into a temp doc tree and asserts doccheck fires.
A checker that has never been shown to catch its own corpus is a checker nobody should
trust — green means nothing until you have watched it go red for the right reason.

STANDING RULE: every doc-drift bug a human finds gets a test here. If one is ever found
that no test covers, that is a finding about the checker, not just the doc.
"""
import importlib
import json
import subprocess
from pathlib import Path

import pytest

import doccheck


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A minimal repo whose docs doccheck will read. Points ROOT at tmp_path."""
    (tmp_path / "docs" / "contracts").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / ".claude" / "scripts").mkdir(parents=True)
    (tmp_path / ".claude" / "settings.json").write_text("{}")
    (tmp_path / "docs" / "adr" / "README.md").write_text("| 0001 | x | y | Accepted |\n")
    (tmp_path / "docs" / "adr" / "0001-first.md").write_text("# ADR 1")
    monkeypatch.setattr(doccheck, "ROOT", tmp_path)
    return tmp_path


def _violations(results: dict) -> list[str]:
    return [v for vs in results.values() for v in vs]


# ─── BUG 1 (2026-07-09): docs named `mnemos-compact-recovery.sh` — a script that did not
# exist, for ~6 weeks, across three docs. design-principles.md:560 recorded the lesson in
# prose ("when a doc claims N layers, `ls` all N") and the `ls` was never built. This is it.
def test_catches_phantom_script(fake_repo):
    (fake_repo / "docs" / "x.md").write_text(
        "Layer 2 is `.claude/scripts/mnemos-compact-recovery.sh`, which restores context."
    )
    bad = doccheck.check_referenced_paths_exist()
    assert any("mnemos-compact-recovery.sh" in v for v in bad), bad


def test_passes_when_named_script_exists(fake_repo):
    (fake_repo / ".claude" / "scripts" / "real.sh").write_text("#!/bin/bash\n")
    (fake_repo / "docs" / "x.md").write_text("Layer 2 is `.claude/scripts/real.sh`.")
    assert doccheck.check_referenced_paths_exist() == []


# ─── BUG 2 (2026-07-11): ADR 0005 was on disk but missing from the ADR index.
def test_catches_unindexed_adr(fake_repo):
    (fake_repo / "docs" / "adr" / "0005-autonomy-inflection.md").write_text("# ADR 5")
    bad = doccheck.check_adr_index_complete()
    assert any("0005" in v for v in bad), bad


def test_passes_when_adr_indexed(fake_repo):
    (fake_repo / "docs" / "adr" / "0005-autonomy-inflection.md").write_text("# ADR 5")
    index = fake_repo / "docs" / "adr" / "README.md"
    index.write_text(index.read_text() + "| 0005 | x | y | Accepted |\n")
    assert doccheck.check_adr_index_complete() == []


# ─── BUGS 3-5 (2026-07-11): three docs stated the Mnemos trial threshold as ">=3
# compaction_fired" AFTER trigger-tagging landed. Unqualified, it invites three hand-run
# /compact TESTS to deliver the trial's verdict on manufactured evidence — the P2 failure.
def test_catches_unqualified_compaction_threshold(fake_repo):
    (fake_repo / "docs" / "x.md").write_text("Judge after ≥3 recorded `compaction_fired` events.")
    bad = doccheck.check_compaction_threshold_qualified()
    assert any("non-manual qualifier" in v for v in bad), bad


def test_passes_when_threshold_qualified(fake_repo):
    (fake_repo / "docs" / "x.md").write_text("Judge after ≥3 non-manual `compaction_fired` events.")
    assert doccheck.check_compaction_threshold_qualified() == []


def test_struck_through_threshold_is_history_not_drift(fake_repo):
    """A superseded claim is the record, not a lie. Immutable-history docs must stay green."""
    (fake_repo / "docs" / "x.md").write_text("~~Judge after ≥3 `compaction_fired` events.~~")
    assert doccheck.check_compaction_threshold_qualified() == []


# ─── BUG 6 (2026-07-11): gate-event.md still claimed gate recording rode model recall
# ("Reliability = the CLAUDE.md convention itself") long after a Stop hook backstopped it.
# A doc that UNDERSTATES a guarantee is as wrong as one that overstates it — it tells the
# reader to distrust a channel that works.
def test_catches_stale_recall_claim_when_hook_is_wired(fake_repo):
    (fake_repo / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"Stop": [{"hooks": [{"command": ".claude/scripts/tessera-gate-scan.sh"}]}]}})
    )
    (fake_repo / "docs" / "contracts" / "gate-event.md").write_text(
        "Reliability = the CLAUDE.md convention itself — Claude forgetting is a finding."
    )
    bad = doccheck.check_gate_recording_not_claimed_as_recall()
    assert any("gate-event.md" in v for v in bad), bad


def test_recall_claim_is_true_when_hook_absent(fake_repo):
    """Without the backstop the claim is CORRECT. The checker must not fire on a true statement."""
    (fake_repo / "docs" / "contracts" / "gate-event.md").write_text(
        "Reliability = the CLAUDE.md convention itself."
    )
    assert doccheck.check_gate_recording_not_claimed_as_recall() == []


# ─── Precision guards. A first cut of this checker produced 98 violations, ~95% false,
# by treating specs/skills/CHANGELOG as claims about disk state. A checker that cries wolf
# gets ignored, and an ignored checker is worse than none: it looks like coverage.
def test_ignores_fenced_code_blocks(fake_repo):
    (fake_repo / "docs" / "x.md").write_text("```bash\ncat `docs/not-real.md`\n```\n")
    assert doccheck.check_referenced_paths_exist() == []


def test_ignores_placeholders(fake_repo):
    (fake_repo / "docs" / "x.md").write_text(
        "Create `docs/adr/NNNN-draft-TITLE.md` and `_project_specs/features/{name}.md`."
    )
    assert doccheck.check_referenced_paths_exist() == []


def test_real_repo_is_green():
    """The live repo must pass. Seeding to green once is what makes future red mean something."""
    importlib.reload(doccheck)
    assert doccheck.ROOT == Path(__file__).resolve().parent.parent
    assert _violations(doccheck.run()) == [], "tessera's own docs make a false claim"


# ─── The gate must not go INERT. Commit 8589280 was pushed with doccheck red because nothing
# was listening — the checker worked and enforced nothing. These two tests guard the wiring,
# not the logic: an unwired gate looks exactly like a passing one, which is the worse failure.
REPO = Path(__file__).resolve().parent.parent


def test_precommit_hook_is_executable():
    hook = REPO / ".githooks" / "pre-commit"
    assert hook.exists(), "the pre-commit gate is missing"
    assert hook.stat().st_mode & 0o111, "pre-commit hook is not executable — git will skip it"


def test_git_is_actually_pointed_at_the_tracked_hooks():
    """THE ONE THAT MATTERS. `.githooks/pre-commit` being present proves nothing: git only
    runs it if core.hooksPath says so, and that is per-clone config, not tracked. Without it
    git runs .git/hooks/ (empty) and the gate is silently inert — present in the repo,
    enforcing nothing. Same shape as config.yml existing but gitignored, and the PATH export
    existing but interactive-only. install.sh sets and verifies this; so does this test."""
    configured = subprocess.run(["git", "config", "core.hooksPath"], cwd=REPO,
                                capture_output=True, text=True).stdout.strip()
    assert configured == ".githooks", (
        f"core.hooksPath is {configured!r}, not '.githooks' — the pre-commit doccheck gate "
        f"is INERT. Run ./install.sh, or: git config core.hooksPath .githooks")
