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


# ── ignored-test-suites-are-run ───────────────────────────────────────────────
# The regression check for the 2026-07-11 "ran 6 of 12 files, reported green" bug. That bug
# was fixed without a check, which is the one thing the standing rule forbids. This is it.

def _run_tests_sh(repo: Path, body: str) -> None:
    (repo / "scripts").mkdir(exist_ok=True)
    (repo / "scripts" / "run-tests.sh").write_text(body)


def test_catches_ignored_suite_that_nothing_runs(fake_repo):
    _run_tests_sh(fake_repo, "pytest scripts/ -q --ignore=scripts/gate --ignore=scripts/spend\n"
                             "pytest scripts/gate -q\n")  # spend ignored, never run
    bad = doccheck.check_ignored_test_suites_are_run()
    assert len(bad) == 1
    assert "scripts/spend" in bad[0]
    assert "silently skipped" in bad[0]


def test_passes_when_every_ignored_suite_is_run(fake_repo):
    _run_tests_sh(fake_repo, "pytest scripts/ -q --ignore=scripts/gate --ignore=scripts/spend\n"
                             "pytest scripts/gate -q\npytest scripts/spend -q\n")
    assert doccheck.check_ignored_test_suites_are_run() == []


def test_module_run_suites_count_as_run(fake_repo):
    """mnemos ships assert-based self-checks run via `-m`, not pytest targets."""
    _run_tests_sh(fake_repo, "pytest scripts/ -q --ignore=scripts/mnemos\n"
                             '"$PY" -m scripts.mnemos.test_haziness\n')
    assert doccheck.check_ignored_test_suites_are_run() == []


def test_missing_run_tests_sh_is_a_violation(fake_repo):
    assert doccheck.check_ignored_test_suites_are_run() != []


# ── spend-guard-is-wired ──────────────────────────────────────────────────────

def _spend_contract(repo: Path) -> None:
    (repo / "docs" / "contracts" / "spend-authorization.md").write_text(
        "PreToolUse, matcher Bash, blocks unauthorized spend.")


def _settings(repo: Path, hooks: dict) -> None:
    (repo / ".claude" / "settings.json").write_text(json.dumps(hooks))


def test_catches_spend_contract_with_no_hook_wired(fake_repo):
    _spend_contract(fake_repo)
    _settings(fake_repo, {"hooks": {"PreToolUse": [{"matcher": "Edit|Write", "hooks": []}]}})
    bad = doccheck.check_spend_guard_is_wired()
    assert len(bad) == 1
    assert "boot a GPU with no authorization" in bad[0]


def test_passes_when_spend_guard_is_wired(fake_repo):
    _spend_contract(fake_repo)
    _settings(fake_repo, {"hooks": {"PreToolUse": [{
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": ".claude/scripts/tessera-spend-guard.sh"}],
    }]}})
    assert doccheck.check_spend_guard_is_wired() == []


def test_spend_guard_wired_under_wrong_matcher_is_a_violation(fake_repo):
    """Wired to Edit|Write instead of Bash: the script exists, and guards nothing."""
    _spend_contract(fake_repo)
    _settings(fake_repo, {"hooks": {"PreToolUse": [{
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": ".claude/scripts/tessera-spend-guard.sh"}],
    }]}})
    assert doccheck.check_spend_guard_is_wired() != []


def test_no_spend_contract_means_no_claim_to_check(fake_repo):
    _settings(fake_repo, {"hooks": {}})
    assert doccheck.check_spend_guard_is_wired() == []


# ── spend-auth-is-not-tracked ─────────────────────────────────────────────────

def test_spend_auth_is_not_tracked_in_the_real_repo():
    """A committed grant would authorize spend on every clone, forever, past its own TTL."""
    assert doccheck.check_spend_auth_is_not_tracked() == []


# ── spend-backstop-is-wired ───────────────────────────────────────────────────

def _escalation_contract(repo: Path) -> None:
    (repo / "docs" / "contracts" / "escalation.md").write_text(
        "Stop hook `.claude/scripts/tessera-spend-backstop.sh` catches undispositioned denials.")


def test_catches_backstop_claimed_but_not_wired(fake_repo):
    _escalation_contract(fake_repo)
    _settings(fake_repo, {"hooks": {"Stop": [{"hooks": [{"command": "mnemos-stop.sh"}]}]}})
    bad = doccheck.check_spend_backstop_is_wired()
    assert len(bad) == 1
    assert "riding model recall" in bad[0]


def test_passes_when_backstop_is_wired(fake_repo):
    _escalation_contract(fake_repo)
    _settings(fake_repo, {"hooks": {"Stop": [{"hooks": [
        {"command": ".claude/scripts/tessera-spend-backstop.sh"}]}]}})
    assert doccheck.check_spend_backstop_is_wired() == []


def test_no_backstop_claim_means_nothing_to_check(fake_repo):
    (fake_repo / "docs" / "contracts" / "escalation.md").write_text("Escalation packets.")
    _settings(fake_repo, {"hooks": {}})
    assert doccheck.check_spend_backstop_is_wired() == []


# ── no-upstream-clone-instructions ────────────────────────────────────────────

def test_catches_getting_started_telling_you_to_clone_maggy(fake_repo):
    """The real 2026-07-12 bug: ADR-0003 decoupled in code, the front door still said clone."""
    (fake_repo / "GETTING_STARTED.md").write_text(
        "## Install\n\n```bash\ngit clone https://github.com/alinaqi/maggy.git\ncd maggy\n```\n")
    bad = doccheck.check_no_upstream_clone_instructions()
    assert len(bad) == 1
    assert "GETTING_STARTED.md:4" in bad[0]
    assert "ADR-0003" in bad[0]


def test_catches_pipx_install_of_upstream(fake_repo):
    (fake_repo / "README.md").write_text("```bash\npipx install maggy-harness\n```\n")
    assert len(doccheck.check_no_upstream_clone_instructions()) == 1


def test_attribution_is_not_an_instruction(fake_repo):
    """MIT REQUIRES naming maggy. The check must never punish the credit it mandates."""
    (fake_repo / "NOTICE").write_text(
        "Tessera is a fork of [Maggy](https://github.com/alinaqi/maggy), "
        "Copyright (c) 2025 Ali Naqi. Credit for the skills architecture belongs there.\n")
    (fake_repo / "README.md").write_text("Forked from Maggy (MIT). See NOTICE.\n")
    assert doccheck.check_no_upstream_clone_instructions() == []


def test_front_door_docs_are_actually_in_scope(fake_repo):
    """The meta-bug: README/GETTING_STARTED were outside DOC_GLOBS, so NOTHING checked them.

    Guards the scope, not just the rule — if a future edit narrows DOC_GLOBS back to
    docs/**, every front-door check silently becomes a no-op and still reports green.
    """
    (fake_repo / "README.md").write_text("names `scripts/phantom.py`\n")
    (fake_repo / "GETTING_STARTED.md").write_text("names `bin/phantom`\n")
    named = {_p for b in doccheck.check_referenced_paths_exist() for _p in [b.split(":")[0]]}
    assert "README.md" in named and "GETTING_STARTED.md" in named


def test_real_repo_has_no_upstream_clone_instructions():
    assert doccheck.check_no_upstream_clone_instructions() == []


# ── no-bare-python3-with-toolchain-import ─────────────────────────────────────
# THE F-001 REGRESSION. F-001 was a hook invoking the toolchain through bare `python3` while
# Homebrew silently re-pointed that name; every checkpoint write no-op'd for weeks, invisibly,
# and it confounded the whole Mnemos trial. The venv fixes resolution — this stops the NEXT one.
# Nothing has ever tested for it. This is the first time.

def _hook(repo: Path, name: str, body: str) -> None:
    (repo / ".claude" / "scripts" / name).write_text(body)


def test_catches_f001_bare_python3_running_inline_toolchain_import(fake_repo):
    _hook(fake_repo, "bad.sh", '#!/bin/bash\npython3 -c "import mnemos; mnemos.checkpoint()"\n')
    bad = doccheck.check_no_bare_python3_with_toolchain_import()
    assert len(bad) == 1
    assert "mnemos" in bad[0] and "silently no-op" in bad[0]


def test_catches_f001_bare_python3_running_a_toolchain_script(fake_repo):
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "scripts" / "ingest.py").write_text("import mnemos\nmnemos.go()\n")
    _hook(fake_repo, "bad.sh", '#!/bin/bash\npython3 "$DIR/scripts/ingest.py"\n')
    bad = doccheck.check_no_bare_python3_with_toolchain_import()
    assert len(bad) == 1
    assert "ingest" in bad[0] or "mnemos" in bad[0]


def test_bare_python3_on_stdlib_only_code_is_FINE(fake_repo):
    """The whole design rests on this split. guard.py, backstop.py, emit.py, scan.py and
    doccheck itself are deliberately stdlib-only precisely so bare `python3` is safe for them.
    A checker that forbade all bare python3 would be wrong, and would get ignored."""
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "scripts" / "guard.py").write_text("import json, re, sys\nprint('ok')\n")
    _hook(fake_repo, "ok.sh", '#!/bin/bash\npython3 "$DIR/scripts/guard.py"\npython3 -c "import json"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_commented_out_bare_python3_is_not_a_landmine(fake_repo):
    _hook(fake_repo, "ok.sh", '#!/bin/bash\n# python3 -c "import mnemos"  (old, do not use)\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_pathful_interpreter_is_not_bare(fake_repo):
    """`$ROOT/.venv/bin/python -c "import mnemos"` is the CORRECT form — a path, not a name.
    The checker must not fire on the fix it is demanding."""
    _hook(fake_repo, "ok.sh", '#!/bin/bash\n"$ROOT/.venv/bin/python" -c "import mnemos"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_real_repo_has_no_f001_landmines():
    """The live hooks must be clean. Green here is the claim that F-001 cannot recur silently."""
    importlib.reload(doccheck)
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []
