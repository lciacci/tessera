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
import sys
from pathlib import Path

import pytest

import doccheck
import prefix_meter


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

def test_runtime_state_is_not_tracked_in_the_real_repo():
    """Two real bugs, both shipped by `git add -A`, one hour apart, in the same directory.

    `spend-auth.json`: a committed grant would authorize spend on every clone, forever, past
    its own TTL. Caught before it shipped.

    `.spend-backstop-fires`: SHIPPED TRACKED 2026-07-12 holding 5, against MAX_FIRES=3. Every
    fresh clone would have inherited a backstop already past its cap — born disabled, silently.
    The guard would deny a GPU boot and nothing would ever catch the denial going
    undispositioned. The safety net shipped pre-torn.

    The lesson did not generalize from the first bug to the second on its own. Hence the rule,
    and hence this test.
    """
    assert doccheck.check_runtime_state_is_not_tracked() == []


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


# ── verify-scan-is-wired ──────────────────────────────────────────────────────

def _verification_contract(repo: Path) -> None:
    (repo / "docs" / "contracts" / "verification-event.md").write_text(
        "The Stop hook (`.claude/scripts/tessera-verify-scan.sh` → `scripts/verify/scan.py`) "
        "fires on unverified safety-path changes. This hook fails LOUD, not open.")


def test_catches_verify_scan_claimed_but_not_wired(fake_repo):
    """Spec 12's whole point is the trigger. An unwired verify-scan is the verifier
    demoted back to a sentence — invocable-but-forgotten, the exact state it replaced."""
    _verification_contract(fake_repo)
    _settings(fake_repo, {"hooks": {"Stop": [{"hooks": [{"command": "mnemos-stop.sh"}]}]}})
    bad = doccheck.check_verify_scan_is_wired()
    assert len(bad) == 1
    assert "must not fail open" in bad[0]


def test_passes_when_verify_scan_is_wired(fake_repo):
    _verification_contract(fake_repo)
    _settings(fake_repo, {"hooks": {"Stop": [{"hooks": [
        {"command": ".claude/scripts/tessera-verify-scan.sh"}]}]}})
    assert doccheck.check_verify_scan_is_wired() == []


def test_no_verification_contract_means_nothing_to_check(fake_repo):
    _settings(fake_repo, {"hooks": {}})
    assert doccheck.check_verify_scan_is_wired() == []


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


# ─── BUG (2026-07-18): the eagerly-loaded `base` skill claimed its trimmed content
# "survives in the GLOBAL ~/.claude/skills/base copy… which retains the full body those
# repos actually use." FALSE — global is byte-identical to the trimmed copy, no script
# copies bodies out. A HARVEST-BEFORE-CUT reassurance pointing at a nonexistent archive.
def test_catches_phantom_global_skill_body_claim(fake_repo):
    d = fake_repo / "skills" / "base"
    d.mkdir(parents=True)
    # Line-wrapped exactly like the original — proves the whitespace-normalized scan
    # catches what a per-line scan would miss.
    (d / "SKILL.md").write_text(
        "downstream-app scaffolding; they\nsurvive in the GLOBAL `~/.claude/skills/base` "
        "copy, which serves downstream app repos and retains the\nfull body those repos use.\n")
    bad = doccheck.check_no_phantom_global_skill_body_claim()
    assert len(bad) == 1
    assert "skills/base/SKILL.md" in bad[0]


def test_corrected_note_does_not_self_trip(fake_repo):
    """The falsification note names the bug to correct it; it must not itself fire."""
    d = fake_repo / "skills" / "base"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "Correction: an earlier note claimed the scaffolding was preserved in a full-body "
        "`~/.claude/skills/base` copy serving downstream apps. That was **false** — no script "
        "copies bodies out; it survives in git history and sibling skills.\n")
    assert doccheck.check_no_phantom_global_skill_body_claim() == []


def test_real_repo_has_no_phantom_global_skill_body_claim():
    assert doccheck.check_no_phantom_global_skill_body_claim() == []


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
    assert "mnemos" in bad[0]


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


# ── test-command-is-not-a-bare-interpreter ────────────────────────────────────
# FOUND BY LORENZO, NOT BY THE CHECKER (2026-07-12) — so it is a finding about the checker.
# no-bare-python3-with-toolchain-import scanned only .claude/scripts/*.sh and was blind to the
# one place the bug actually shipped: the `test:` command. conclave carried
# `test: python3.13 -m pytest scripts/`; uv shimmed that name ahead of Homebrew; the suite
# broke; doccheck stayed green. The template *advised* the broken form.

def _config(repo: Path, test_cmd: str) -> None:
    (repo / ".tessera").mkdir(exist_ok=True)
    (repo / ".tessera" / "config.yml").write_text(f"# toolchain\ntest: {test_cmd}\n")


@pytest.mark.parametrize("cmd", [
    "python3.13 -m pytest scripts/",   # conclave's actual broken command
    "python3 -m pytest",
    "python -m pytest",
    "python3.12 -m pytest -q",
])
def test_catches_test_command_resolving_interpreter_by_name(fake_repo, cmd):
    _config(fake_repo, cmd)
    bad = doccheck.check_test_command_is_not_a_bare_interpreter()
    assert len(bad) == 1
    assert "by NAME" in bad[0]


@pytest.mark.parametrize("cmd", [
    ".venv/bin/python -m pytest scripts/",   # the correct form: repo-relative PATH
    "bash scripts/run-tests.sh",             # tessera's own
    "npm test",
    "./gradlew test",
    "npx vitest run",
])
def test_passes_on_path_based_or_non_python_commands(fake_repo, cmd):
    _config(fake_repo, cmd)
    assert doccheck.check_test_command_is_not_a_bare_interpreter() == []


def test_real_repo_test_command_is_a_path():
    importlib.reload(doccheck)
    assert doccheck.check_test_command_is_not_a_bare_interpreter() == []


# ── F-001 in the HOOK path: the two forms the detector was blind to ───────────
# Found 2026-07-12 by an INDEPENDENT session verifying this work from a clean context. The
# venv closed F-001 in the install path; it was still wide open in the hook path — which is
# where F-001 actually lived. The detector built to prevent exactly this could not see it.
#
# Both forms silently SUCCEED rather than fail: with PYTHONPATH/sys.path pointing at scripts/,
# ANY interpreter imports mnemos straight from source. The original F-001 failed silently
# (import error → no-op). These *work*, on an interpreter Homebrew can re-point or delete.
# A silent success is strictly harder to detect than a silent failure.

def test_catches_bare_python3_dash_m_toolchain_module(fake_repo):
    """FORM 1: `python3 -m mnemos` — the only form the hooks actually used, 16 times across
    five files. The detector parsed `-c` and `file.py` and stopped there."""
    _hook(fake_repo, "h.sh", '#!/bin/bash\nPYTHONPATH=scripts python3 -m mnemos checkpoint --force\n')
    bad = doccheck.check_no_bare_python3_with_toolchain_import()
    assert len(bad) == 1
    assert "mnemos" in bad[0]


def test_catches_bare_python3_dash_m_icpg(fake_repo):
    _hook(fake_repo, "h.sh", '#!/bin/bash\nICPG_CMD="python3 -m icpg"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_catches_bare_python3_on_a_RUNTIME_GENERATED_script(fake_repo):
    """FORM 2, and the nastier one: mnemos-pre-compact.sh writes a temp .py via heredoc that
    does `sys.path.insert(0, 'scripts')` + `from mnemos.store import ...`, then runs it as
    `python3 "$TMPSCRIPT"`. There is no `.py` literal on the line, so the file branch saw
    nothing. Fixing only `-m` would have left this behind, still live."""
    _hook(fake_repo, "h.sh", (
        '#!/bin/bash\n'
        'cat > "$TMPSCRIPT" << PYSCRIPT\n'
        "sys.path.insert(0, 'scripts')\n"
        'from mnemos.store import MnemosStore\n'
        'PYSCRIPT\n'
        'OUT=$(python3 "$TMPSCRIPT")\n'
    ))
    bad = doccheck.check_no_bare_python3_with_toolchain_import()
    assert len(bad) == 1
    assert "mnemos" in bad[0]


def test_bare_python3_on_a_generated_stdlib_script_is_FINE(fake_repo):
    """The coarse fallback must not cry wolf. A hook that generates a stdlib-only temp script
    and runs it on bare python3 is correct — that is exactly how the gate/spend hooks work,
    deliberately, so they keep working when the venv is broken."""
    _hook(fake_repo, "ok.sh", (
        '#!/bin/bash\n'
        'cat > "$TMP" << PY\n'
        'import json, sys\n'
        'print(json.dumps({}))\n'
        'PY\n'
        'OUT=$(python3 "$TMP")\n'
    ))
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_resolved_venv_interpreter_on_a_generated_script_is_FINE(fake_repo):
    """The fix must not trip the check that demanded it."""
    _hook(fake_repo, "ok.sh", (
        '#!/bin/bash\n'
        'cat > "$TMP" << PY\n'
        'from mnemos.store import MnemosStore\n'
        'PY\n'
        'OUT=$("$TOOLCHAIN_PY" "$TMP")\n'
    ))
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


# ── F-001 detector v2: the five landmines v1 let through ──────────────────────
# v1 caught 1 of 5. An adversarial verifier in a clean session planted these and proved the
# detector was a mirror, not an instrument: it went GREEN over three live, wired hooks
# (pre-edit on every Edit/Write, post-tool on every tool call, post-compact-inject) — and I
# used that green to certify my own fix. A detector you verify a fix with must be tested
# against that fix's own failure mode.

def _sh(repo: Path, name: str, body: str) -> None:
    (repo / ".claude" / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "scripts" / name).write_text(body)


def test_v1_HOLE_multiline_dash_c_body(fake_repo):
    """THE ONE THAT MATTERED. The hooks open `python3 -c "` and put the import four lines
    down. v1 matched `-c` only when the closing quote was on the SAME line, so line 69 —
    literally `python3 -c "` — parsed to an empty target and reported nothing."""
    _sh(fake_repo, "h.sh", '#!/bin/bash\nX=$(python3 -c "\nimport sys\nfrom mnemos.fatigue import compute\n")\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v1_HOLE_dotted_version_name(fake_repo):
    """v1's regex was `python3(?![\\w.])` — so `python3.13` slipped through, the very name uv
    shimmed into ~/.local/bin ahead of Homebrew."""
    _sh(fake_repo, "h.sh", "#!/bin/bash\npython3.13 -m mnemos checkpoint\n")
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v1_HOLE_outside_the_glob(fake_repo):
    """v1 globbed `.claude/scripts/*.sh` only — blind to hooks/, bin/, templates/, all of
    which ship in the install payload."""
    (fake_repo / "hooks").mkdir(exist_ok=True)
    (fake_repo / "hooks" / "h").write_text("#!/bin/bash\npython3 -m icpg query\n")
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v1_HOLE_extensionless_file(fake_repo):
    _sh(fake_repo, "h", "#!/bin/bash\npython3 -m mnemos checkpoint\n")
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v1_HOLE_interpreter_assigned_to_a_variable(fake_repo):
    """`MNEMOS_PY="python3"` then `"$MNEMOS_PY" -c` — post-tool.sh's actual shape. No bare
    `python3 ` token ever appears in command position."""
    _sh(fake_repo, "h.sh", '#!/bin/bash\nMNEMOS_PY="python3"\n"$MNEMOS_PY" -c "from mnemos.auto_nodes import go"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_stdlib_only_bare_python3_STAYS_LEGAL(fake_repo):
    """LOAD-BEARING. tessera-gate-scan.sh, tessera-spend-guard.sh and tessera-spend-backstop.sh
    run bare `python3` deliberately, so the SAFETY MACHINERY keeps working when the venv is
    broken. A checker that forbade all bare python3 would break the very hooks that catch a
    broken venv."""
    _sh(fake_repo, "ok.sh", '#!/bin/bash\npython3 -c "import json,sys; print(json.dumps({}))"\npython3 "$SCAN"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_path_resolved_interpreter_stays_legal(fake_repo):
    """The fix must not trip the check that demanded it."""
    _sh(fake_repo, "ok.sh", '#!/bin/bash\nTOOLCHAIN_PY=".venv/bin/python"\n"$TOOLCHAIN_PY" -c "from mnemos.store import S"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_real_repo_has_no_bare_interpreter_landmines():
    importlib.reload(doccheck)
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_file_following_works_without_a_trailing_newline(fake_repo):
    """The `\\n` join in check_no_bare_python3_with_toolchain_import is load-bearing. Without
    it the shell text and the followed .py source concatenate into `...ingest.pyimport mnemos`
    — the import is no longer at a line start and VENV_IMPORT misses it.

    The original test for file-following PASSED anyway, because its fixture body ended in a
    newline. A live probe against a real file caught it. Fixtures are not reality; this test
    reproduces the reality."""
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "scripts" / "ingest.py").write_text("import mnemos\nmnemos.go()\n")
    _sh(fake_repo, "bad.sh", '#!/bin/bash\npython3 scripts/ingest.py')  # no trailing newline
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


# ── Detector v3: the SEVEN holes an adversarial verifier walked through ───────
# v1 caught 1 of 5 landmines. v2 caught 5 of 7. This is v3. Each test below is a landmine the
# verifier planted in a clean session while doccheck reported "0 false claims".

def test_v2_HOLE_shebang_was_stripped_as_a_comment(fake_repo):
    """THE STRUCTURAL ONE. `_strip_sh_comments` dropped every line starting with `#` — which
    deleted the SHEBANG. A `#!` line is not a comment in any sense that matters: it IS the
    interpreter resolution. The detector was stripping the exact thing it was hunting.
    Live instance: hooks/plugin-trigger, `#!/usr/bin/env python3` + `import yaml` under an
    `except Exception: pass` — silently discovering zero plugins."""
    (fake_repo / "hooks").mkdir(exist_ok=True)
    (fake_repo / "hooks" / "p").write_text("#!/usr/bin/env python3\nimport yaml\nprint(yaml)\n")
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v2_HOLE_bin_glob_matched_nothing(fake_repo):
    """The glob was `bin/*.sh`. Every file in bin/ is EXTENSIONLESS, so it matched zero files
    — while bin/tessera-watch runs at SessionStart and bin/tessera-authorize gates spend."""
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "tool").write_text("#!/bin/bash\nPYTHONPATH=scripts python3 -m mnemos x\n")
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v2_HOLE_githooks_and_repo_root_unscoped(fake_repo):
    (fake_repo / ".githooks").mkdir(exist_ok=True)
    (fake_repo / ".githooks" / "pre-commit").write_text("#!/bin/bash\npython3 -m mnemos x\n")
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v2_HOLE_dollar_brace_default_evasion(fake_repo):
    """`${PY:-python3}` — the lookbehind excluded a preceding `-`, so this walked straight past."""
    _sh(fake_repo, "h.sh", '#!/bin/bash\n"${PY:-python3}" -c "import mnemos"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_v2_HOLE_dynamic_import_evasion(fake_repo):
    """`importlib.import_module("mnemos")` is still an import. And inside a shell `-c "…"` the
    inner quotes are ESCAPED — the pattern must tolerate `import_module(\\"mnemos\\")`."""
    _sh(fake_repo, "a.sh", '#!/bin/bash\npython3 -c "import importlib; importlib.import_module(\\"mnemos\\")"\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() != []


def test_python_files_are_PARSED_not_grepped(fake_repo):
    """PRECISION, and it matters as much as recall. bin/tessera-watch contains the STRING
    `subprocess.run([interp, "-c", "import mnemos"])` — that is P9's probe, data, not an import.
    A text rule called it a landmine. The AST does not. A checker that cries wolf gets ignored,
    and an ignored checker is worse than none because it looks like coverage."""
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "watch").write_text(
        '#!/usr/bin/env python3\nimport subprocess\nsubprocess.run(["p", "-c", "import mnemos"])\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_reexec_on_the_venv_is_recognised_as_THE_FIX(fake_repo):
    """A shebang cannot hold a relative path, so a python script's fix is to RE-EXEC on the venv
    before importing venv-only code. The checker must not fire on the very fix it demands."""
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "t").write_text(
        '#!/usr/bin/env python3\n'
        'import os as _os, sys as _sys\nfrom pathlib import Path as _Path\n'
        '_venv = _Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python"\n'
        'if _venv.exists() and _Path(_sys.executable).resolve() != _venv.resolve():\n'
        '    _os.execv(str(_venv), [str(_venv), *_sys.argv])\n'
        'import yaml\n')
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


# ── safety-scripts-run-on-system-python ──────────────────────────────────────

def test_safety_scripts_run_on_the_system_python():
    """THE WORST BUG OF 2026-07-12. I carved out an exception — the gate/spend hooks may use bare
    `python3` because they are stdlib-only and must survive a broken venv. Half right, and the
    wrong half was lethal: STDLIB-ONLY IS NOT VERSION-INDEPENDENT. On a /usr/bin-first PATH,
    `python3` is macOS 3.9; PEP-604 (`str | None`) raises TypeError at definition time; guard.py
    exits 1; and the hook wrapper passes that through as "not 2" — which Claude Code reads as
    ALLOW. An unauthorized GPU boot proceeded.

    The suite never saw it: it runs on the venv's 3.13, where the bug is invisible. A test that
    only ever runs on the good interpreter cannot see an interpreter bug. So this EXECUTES them
    on the system python — `ast.parse` would pass, because PEP-604 is syntactically valid and
    only explodes when evaluated. Compiling is not running."""
    importlib.reload(doccheck)
    assert doccheck.check_safety_scripts_run_on_the_system_python() == []


# ── bin-scripts-are-stdlib-only ──────────────────────────────────────────────

def _bin(repo, name, body):
    d = repo / "bin"
    d.mkdir(exist_ok=True)
    (d / name).write_text(body)
    return d / name


REEXEC_PREAMBLE = (
    "#!/usr/bin/env python3\n"
    "import os as _os, sys as _sys\n"
    "from pathlib import Path as _Path\n"
    "_venv = _Path(__file__).resolve().parent.parent / '.venv' / 'bin' / 'python'\n"
    "if _venv.exists() and _Path(_sys.executable).resolve() != _venv.resolve():\n"
    "    _os.execv(str(_venv), [str(_venv), *_sys.argv])\n"
)


def test_bare_shebang_plus_third_party_import_is_CAUGHT(fake_repo):
    """THE BUG. bin/deepseek, bin/grok, bin/gemini-api were `#!/usr/bin/env python3` + `import
    httpx`. httpx is installed NOWHERE — not the venv, not any Homebrew python. All three had
    never run, ever. bin/validate-plan called them, caught the ModuleNotFoundError, and scored
    it as a reviewer VOTING NO — so Tessera's council returned a confident `CHANGES_NEEDED 0/3`
    manufactured entirely out of this."""
    _bin(fake_repo, "wrapper", "#!/usr/bin/env python3\nimport httpx\n")
    hits = doccheck.check_bin_scripts_are_stdlib_only()
    assert any("wrapper" in h and "httpx" in h for h in hits), hits


def test_the_OLD_detector_would_have_MISSED_it(fake_repo):
    """WHY THE OLD CHECK LET IT THROUGH — the finding, not just the bug.

    `no-bare-python3-with-toolchain-import` matched against a HARDCODED SET of module names:
    {mnemos, icpg, polyphony, skill_lint, pytest, yaml, requests}. `httpx` was simply not on
    the list. A blacklist of names someone must remember to extend is not a detector; it is a
    to-do list that fails open. Adding "httpx" to it would have fixed this one escape and
    guaranteed the next dependency escapes identically. This pins that the old check is still
    blind, so nobody "fixes" the new one by folding it back into the list."""
    _bin(fake_repo, "wrapper", "#!/usr/bin/env python3\nimport httpx\n")
    assert doccheck.check_no_bare_python3_with_toolchain_import() == []


def test_local_sibling_modules_are_NOT_flagged(fake_repo):
    """FALSE POSITIVE the first version shipped with. bin/tessera-watch imports `doccheck`,
    bin/tessera-test imports `tessera_config` — local .py siblings reached via sys.path.insert.
    They are stdlib-only and travel with the repo. A checker that cannot tell those from a
    missing httpx is a checker that gets switched off."""
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "scripts" / "tessera_config.py").write_text("X = 1\n")
    _bin(fake_repo, "tessera-thing", "#!/usr/bin/env python3\nimport tessera_config\n")
    assert doccheck.check_bin_scripts_are_stdlib_only() == []


def test_venv_reexec_is_PROBED_not_TRUSTED(fake_repo):
    """THE HOLE IN v1 OF THIS VERY CHECK. v1 treated a venv re-exec as proof of correctness and
    SKIPPED such scripts. Same mistake one level up: re-execing on the venv proves the script
    REACHES the venv, not that the venv HAS the module. bin/build-in-public-status re-execs and
    imports httpx — and the venv does not have httpx either. v1 called it clean.

    The fake repo gets a REAL venv interpreter (the one running pytest, which genuinely lacks
    httpx) — probing a stub would prove nothing."""
    venv_bin = fake_repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(sys.executable)

    _bin(fake_repo, "poster", REEXEC_PREAMBLE + "import httpx\n")
    hits = doccheck.check_bin_scripts_are_stdlib_only()
    assert any("poster" in h and "httpx" in h for h in hits), hits


def test_no_venv_yet_does_not_invent_a_failure(fake_repo):
    """Before install.sh builds the venv there is nothing to probe. Inventing a failure there
    would make a fresh clone red for a reason the user cannot act on."""
    _bin(fake_repo, "poster", REEXEC_PREAMBLE + "import httpx\n")
    assert doccheck.check_bin_scripts_are_stdlib_only() == []


def test_a_script_that_will_not_COMPILE_is_caught(fake_repo):
    """`ast.parse` ACCEPTS a misplaced `from __future__` (PyCF_ONLY_AST skips the future check);
    python then refuses to run it. bin/build-in-public-status had exactly that — its re-exec
    preamble necessarily precedes the future-import — so it could not have executed on ANY
    interpreter, ever, and an ast.parse guard reported it clean. Only compile() is the real gate.
    The weaker gate is the one that lets the corpse through."""
    _bin(fake_repo, "corpse", REEXEC_PREAMBLE + "from __future__ import annotations\n")
    hits = doccheck.check_bin_scripts_are_stdlib_only()
    assert any("corpse" in h and "compile" in h for h in hits), hits


# ── hooks-match-templates (found 2026-07-16: #7's hook fix skipped its template copy) ──

def _hook_pair(repo, name, live, template):
    """Write a live .claude/scripts hook and its templates/ copy (or None to omit)."""
    (repo / ".claude" / "scripts" / name).write_text(live)
    if template is not None:
        (repo / "templates").mkdir(exist_ok=True)
        (repo / "templates" / name).write_text(template)


def test_catches_hook_template_drift(fake_repo):
    _hook_pair(fake_repo, "h.sh", "echo new\n", "echo old\n")
    hits = doccheck.check_hooks_match_templates()
    assert any("h.sh" in h and "differs" in h for h in hits), hits


def test_catches_missing_template(fake_repo):
    _hook_pair(fake_repo, "h.sh", "echo hi\n", None)  # live hook, no template copy
    hits = doccheck.check_hooks_match_templates()
    assert any("h.sh" in h and "missing" in h for h in hits), hits


def test_passes_when_hook_matches_template(fake_repo):
    _hook_pair(fake_repo, "h.sh", "echo same\n", "echo same\n")
    assert doccheck.check_hooks_match_templates() == []


def test_catches_template_load_of_deleted_skill(fake_repo):
    # A template eager-loads / copies a skill that does not exist in skills/.
    (fake_repo / "templates").mkdir()
    (fake_repo / "templates" / "CLAUDE.md").write_text(
        "@.claude/skills/base/SKILL.md\n@.claude/skills/ghost/SKILL.md\n"
    )
    (fake_repo / "skills" / "base").mkdir(parents=True)
    bad = doccheck.check_template_skill_refs_exist()
    assert any("ghost" in b for b in bad)
    assert not any("base" in b for b in bad)


def test_catches_cp_recipe_to_deleted_skill_in_fence(fake_repo):
    # The spawn-team shape: a `cp ~/.claude/skills/X/` recipe inside a fenced block.
    (fake_repo / "commands").mkdir()
    (fake_repo / "commands" / "init.md").write_text(
        "Copy roles:\n```bash\ncp -r ~/.claude/skills/agent-teams/agents/ .claude/agents/\n```\n"
    )
    assert any("agent-teams" in b for b in doccheck.check_template_skill_refs_exist())


def test_passes_when_referenced_template_skill_exists(fake_repo):
    (fake_repo / "templates").mkdir()
    (fake_repo / "templates" / "CLAUDE.md").write_text("@.claude/skills/mnemos/SKILL.md\n")
    (fake_repo / "skills" / "mnemos").mkdir(parents=True)
    assert doccheck.check_template_skill_refs_exist() == []


# ─── 2026-07-19 (profiles tidy): the curation map (skill-profiles.json) can name a DELETED
# skill — dangling curation that silently selects nothing. Sibling of template-skill-refs for
# the one skill reference that is a bare JSON name, not an `@`/`~/` path.
def _write_profiles(repo, data):
    d = repo / "templates" / "tessera"
    d.mkdir(parents=True, exist_ok=True)
    (d / "skill-profiles.json").write_text(json.dumps(data))


def test_catches_profile_naming_deleted_skill(fake_repo):
    (fake_repo / "skills" / "base").mkdir(parents=True)
    _write_profiles(fake_repo, {
        "universal": ["base"], "profiles": {"standard": []},
        "extensions": {"x": ["deleted-skill"]}})
    bad = doccheck.check_skill_profiles_names_are_installed()
    assert any("deleted-skill" in v for v in bad), bad


def test_passes_when_all_profile_skills_installed(fake_repo):
    for s in ("base", "existing-repo"):
        (fake_repo / "skills" / s).mkdir(parents=True)
    _write_profiles(fake_repo, {
        "universal": ["base"], "profiles": {"standard": []},
        "extensions": {"brownfield": ["existing-repo"]}})
    assert doccheck.check_skill_profiles_names_are_installed() == []


def test_orphan_skill_is_not_a_violation(fake_repo):
    # Installed but named nowhere = deliberate off-everywhere policy, not an error.
    for s in ("base", "workspace"):
        (fake_repo / "skills" / s).mkdir(parents=True)
    _write_profiles(fake_repo, {"universal": ["base"], "profiles": {}, "extensions": {}})
    assert doccheck.check_skill_profiles_names_are_installed() == []


def test_malformed_profiles_json_fails_clean(fake_repo):
    # A broken map fails as a clean violation, not an uncaught traceback.
    d = fake_repo / "templates" / "tessera"
    d.mkdir(parents=True)
    (d / "skill-profiles.json").write_text("{not: valid json,")
    bad = doccheck.check_skill_profiles_names_are_installed()
    assert any("invalid JSON" in v for v in bad), bad


# ─── BUG (2026-07-20): active.md's heading convention drifted to `## ═══ SESSION` on
# 07-17; the SessionStart surfacer greps `^## Handoff — pick up here` and silently
# printed the 2026-07-12 handoff as current for 8 days. A stale handoff surfaced as
# current is worse than none.
def _active(fake_repo, text):
    d = fake_repo / "_project_specs" / "todos"
    d.mkdir(parents=True)
    (d / "active.md").write_text(text)


def test_handoff_missing_magic_heading_flagged(fake_repo):
    _active(fake_repo, "## ═══ SESSION 2026-07-20 ═══\nstuff\n")
    bad = doccheck.check_handoff_heading_is_current()
    assert any("no '## Handoff" in v for v in bad), bad


def test_handoff_stale_when_session_block_precedes_it(fake_repo):
    _active(fake_repo, "## ═══ SESSION 2026-07-20 ═══\n\n"
                       "## Handoff — pick up here (2026-07-12)\nold\n")
    bad = doccheck.check_handoff_heading_is_current()
    assert any("stale handoff" in v for v in bad), bad


def test_handoff_current_heading_passes(fake_repo):
    _active(fake_repo, "# Active Focus\n\n"
                       "## Handoff — pick up here (2026-07-20)\nnew\n\n"
                       "## ═══ SESSION 2026-07-19 ═══\nold log\n")
    assert doccheck.check_handoff_heading_is_current() == []


# ── hook-commands-are-anchored (added 2026-07-24) ──────────────────────────────────────────
#
# A hook command inherits the SESSION cwd. One `cd` into a downstream retargets every relative
# path for the rest of the session: this repo's gate log split 4/2 across two repos, and a
# probe got RETARGETED 13/13 with twelve exiting 0 and EMPTY. Both halves are asserted because
# neither alone is sufficient — an anchored command runs the right script, which then reads
# the wrong repo unless the script anchors too.

def _anchored_settings(**over):
    cmd = over.get("cmd", 'if [ -x "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/x.sh" ]; then '
                          'exec "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/x.sh"; fi; exit 0')
    return {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": cmd}]}]}}


def _seed(repo, settings, script_body, templates=None):
    """Seed a fake repo. Templates default to ANCHORED so the live-settings assertions are
    isolated; pass `templates` explicitly to exercise the scaffold half of the check."""
    (repo / ".claude" / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "settings.json").write_text(json.dumps(settings))
    (repo / ".claude" / "scripts" / "x.sh").write_text(script_body)
    tpl = templates if templates is not None else _anchored_settings()
    (repo / "templates" / "tessera").mkdir(parents=True, exist_ok=True)
    (repo / "templates" / "tessera" / "settings.base.json").write_text(json.dumps(tpl))
    (repo / "templates" / "settings.json").write_text(json.dumps(tpl))


# A correctly anchored script GUARDS the cd so the ~/.claude/templates/ global-tier copy
# (where ../.. is $HOME) does not cd to $HOME. Guard + cd is the passing form.
ANCHORED_SCRIPT = ('#!/usr/bin/env bash\ncase "$(dirname "$0")" in\n'
                   '  */.claude/scripts) cd "$(dirname "$0")/../.." 2>/dev/null || exit 0 ;;\n'
                   'esac\n')
UNGUARDED_SCRIPT = '#!/usr/bin/env bash\ncd "$(dirname "$0")/../.." 2>/dev/null || exit 0\n'
BARE_SCRIPT = '#!/usr/bin/env bash\necho hi\n'


def test_catches_cwd_relative_hook_command(fake_repo):
    _seed(fake_repo, _anchored_settings(
        cmd='if [ -x ".claude/scripts/x.sh" ]; then exec ".claude/scripts/x.sh"; fi; exit 0'),
        ANCHORED_SCRIPT)
    out = doccheck.check_hook_commands_are_anchored()
    assert any("cwd-relative" in p for p in out), out


def test_catches_script_with_no_self_anchor(fake_repo):
    _seed(fake_repo, _anchored_settings(), BARE_SCRIPT)
    out = doccheck.check_hook_commands_are_anchored()
    assert any("no project-root self-anchor" in p for p in out), out


def test_passes_when_both_halves_are_anchored(fake_repo):
    _seed(fake_repo, _anchored_settings(), ANCHORED_SCRIPT)
    assert doccheck.check_hook_commands_are_anchored() == []


def test_catches_an_unguarded_anchor(fake_repo):
    """M1 (review 2026-07-24): an anchor WITHOUT the */.claude/scripts) guard cd's the global-
    tier copy to $HOME and silently disables every downstream hook. The check must catch it —
    a bare cd that passed would be 'ship both halves' violated inside the check for it."""
    _seed(fake_repo, _anchored_settings(), UNGUARDED_SCRIPT)
    out = doccheck.check_hook_commands_are_anchored()
    assert any("UNGUARDED" in p for p in out), out


def test_statusline_is_checked_too(fake_repo):
    """statusLine is not in hooks{} — it was the 16th carrier the first count missed."""
    s = _anchored_settings()
    s["statusLine"] = {"type": "command", "command": '.claude/scripts/x.sh'}
    _seed(fake_repo, s, ANCHORED_SCRIPT)
    out = doccheck.check_hook_commands_are_anchored()
    assert any("statusLine" in p for p in out), out


def test_decision_surface_wired_but_script_missing_is_caught(fake_repo):
    """#4 (review 2026-07-24): the settings `if [ -x SCRIPT ]` wrapper makes a missing script
    a silent no-op. The check must verify the script exists, not just that the wire mentions
    'decision-surface' — else it certifies a hook that never runs."""
    (fake_repo / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"hooks": [{"type": "command", "command": 'if [ -x "x/tessera-decision-surface.sh" ]; '
                    'then exec "x/tessera-decision-surface.sh"; fi; exit 0'}]}]}}))
    # No tessera-decision-surface.sh written under .claude/scripts/.
    out = doccheck.check_decision_surface_is_wired()
    assert any("missing or not executable" in p for p in out), out


def test_catches_a_scaffold_template_that_births_the_bug(fake_repo):
    """A new project must not be scaffolded with cwd-relative hooks. templates/tessera/
    settings.base.json is what tessera-new-project copies into every new project, and
    templates/settings.json is what install_session_hooks.py merges into existing ones."""
    _seed(fake_repo, _anchored_settings(), ANCHORED_SCRIPT, templates=_anchored_settings(
        cmd='if [ -x ".claude/scripts/x.sh" ]; then exec ".claude/scripts/x.sh"; fi; exit 0'))
    out = doccheck.check_hook_commands_are_anchored()
    assert any("born with the retargeting bug" in p for p in out), out


def test_pretooluse_bare_stdout_is_caught(fake_repo):
    """The class found 2026-07-24: a PreToolUse hook that dumps model-facing text to bare
    stdout reaches the debug log, not the model. Must be flagged; a JSON-channel hook must not."""
    (fake_repo / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"hooks": [{"type": "command", "command": 'if [ -x ".claude/scripts/bad.sh" ]; then '
                    'exec ".claude/scripts/bad.sh"; fi; exit 0'}]}]}}))
    (fake_repo / ".claude" / "scripts" / "bad.sh").write_text(
        '#!/usr/bin/env bash\necho "--- Context for the model ---"\necho "$STUFF"\nexit 0\n')
    out = doccheck.check_pretooluse_hooks_reach_the_model()
    assert any("bad.sh" in p and "bare stdout" in p for p in out), out


def test_pretooluse_with_additionalcontext_passes(fake_repo):
    (fake_repo / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"hooks": [{"type": "command", "command": 'if [ -x ".claude/scripts/ok.sh" ]; then '
                    'exec ".claude/scripts/ok.sh"; fi; exit 0'}]}]}}))
    (fake_repo / ".claude" / "scripts" / "ok.sh").write_text(
        '#!/usr/bin/env bash\necho \'{"hookSpecificOutput":{"additionalContext":"hi"}}\'\nexit 0\n')
    assert doccheck.check_pretooluse_hooks_reach_the_model() == []


def test_anchor_check_catches_dotslash_form(fake_repo):
    """L3 (review 2026-07-24): the first regex required a `"` right before the path, so
    `"./.claude/scripts/x"` (leading ./) slipped a check whose whole job is catching cwd-
    relative paths. Now caught; the anchored form still passes."""
    cmd = 'if [ -x "./.claude/scripts/x.sh" ]; then exec "./.claude/scripts/x.sh"; fi; exit 0'
    _seed(fake_repo, _anchored_settings(cmd=cmd), ANCHORED_SCRIPT)
    assert any("cwd-relative" in p for p in doccheck.check_hook_commands_are_anchored())
    ok = 'if [ -x "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/x.sh" ]; then exec "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/x.sh"; fi; exit 0'
    _seed(fake_repo, _anchored_settings(cmd=ok), ANCHORED_SCRIPT)
    assert not any("cwd-relative" in p for p in doccheck.check_hook_commands_are_anchored())


def test_anchor_check_ignores_a_path_named_in_a_message(fake_repo):
    """The maggy two-tier hooks say `echo "… touch .claude/scripts/X to silence"`. That path
    is a MENTION, not an exec target — flagging it is a false positive (it bit the first broad
    L3 fix). An anchored exec path plus a bare mention in the same command must stay clean."""
    cmd = ('if [ -x "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/x.sh" ]; then '
           'exec "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/x.sh"; fi; '
           'echo "not installed — touch .claude/scripts/x.sh to silence" >&2; exit 0')
    _seed(fake_repo, _anchored_settings(cmd=cmd), ANCHORED_SCRIPT)
    assert not any("cwd-relative" in p for p in doccheck.check_hook_commands_are_anchored())


def test_pretooluse_channel_named_only_in_a_comment_does_not_clear(fake_repo):
    """M1 (review 2026-07-24): the channel test was a raw substring scan, so a hook emitting
    bare stdout but merely MENTIONING additionalContext in a comment passed — the guard against
    the silent-hook class, weakened by the same class. Channels must be in an executed line."""
    (fake_repo / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"hooks": [{"type": "command", "command": 'if [ -x ".claude/scripts/c.sh" ]; then '
                    'exec ".claude/scripts/c.sh"; fi; exit 0'}]}]}}))
    (fake_repo / ".claude" / "scripts" / "c.sh").write_text(
        '#!/bin/bash\n# we do not use additionalContext here\necho "CONTEXT FOR THE MODEL"\n')
    out = doccheck.check_pretooluse_hooks_reach_the_model()
    assert any("c.sh" in p and "bare stdout" in p for p in out), out


# ─── BUG (2026-07-24, fixed 07-26): the gate log split 4/2 across two repos under ONE session
# id. `.tessera/logs/<session>.jsonl` is session-keyed, but the hand-invoked gate tools resolved
# it against the cwd — and a `cd` into a downstream persists across Bash calls. The write side
# corrupted; the read side was worse, because `ratio.py` from a foreign cwd printed a clean
# report of ZERO gates instead of erroring (standing pattern #2).
def test_catches_a_cwd_relative_session_log_path(fake_repo, monkeypatch):
    monkeypatch.setattr(doccheck, "_HAND_INVOKED_SESSION_TOOLS", ("scripts/gate/emit.py",))
    (fake_repo / "scripts" / "gate").mkdir(parents=True)
    (fake_repo / "scripts" / "gate" / "emit.py").write_text(
        'from pathlib import Path\n'
        'def _log_path(sid):\n'
        '    return Path(".tessera/logs") / f"{sid}.jsonl"\n'
    )
    bad = doccheck.check_session_logs_are_repo_anchored()
    assert any("cwd-relative" in v and "emit.py" in v for v in bad), bad


def test_passes_when_the_session_log_path_is_anchored(fake_repo, monkeypatch):
    """The real fix's shape: root from __file__/TESSERA_ROOT, segments as separate literals."""
    monkeypatch.setattr(doccheck, "_HAND_INVOKED_SESSION_TOOLS", ("scripts/gate/emit.py",))
    (fake_repo / "scripts" / "gate").mkdir(parents=True)
    (fake_repo / "scripts" / "gate" / "emit.py").write_text(
        'import os\n'
        'from pathlib import Path\n'
        'def _log_path(sid):\n'
        '    root = Path(os.environ.get("TESSERA_ROOT") or Path(__file__).resolve().parents[2])\n'
        '    return root / ".tessera" / "logs" / f"{sid}.jsonl"\n'
    )
    assert doccheck.check_session_logs_are_repo_anchored() == []


def test_session_log_check_ignores_a_path_named_in_a_comment(fake_repo, monkeypatch):
    """Same false-positive class the anchor check hit: the fixed files DOCUMENT the old bad
    path in their comments. Flagging the explanation of a fix as the bug would make the check
    unfixable — the only way to go green would be to delete the reasoning."""
    monkeypatch.setattr(doccheck, "_HAND_INVOKED_SESSION_TOOLS", ("scripts/gate/emit.py",))
    (fake_repo / "scripts" / "gate").mkdir(parents=True)
    (fake_repo / "scripts" / "gate" / "emit.py").write_text(
        '# was Path(".tessera/logs") / f"{sid}.jsonl" — cwd-relative, split the log 4/2\n'
        'from pathlib import Path\n'
        'LOGS = Path(__file__).resolve().parents[2] / ".tessera" / "logs"\n'
    )
    assert doccheck.check_session_logs_are_repo_anchored() == []


def test_session_log_check_is_not_vacuous():
    """The list must name files that EXIST in the real repo. A typo'd path would make the
    check scan nothing and pass forever — the vacuity class found in the 2026-07-24 review."""
    assert doccheck._HAND_INVOKED_SESSION_TOOLS, "the tool list is empty — check scans nothing"
    missing = [p for p in doccheck._HAND_INVOKED_SESSION_TOOLS
               if not (doccheck.ROOT / p).is_file()]
    assert not missing, f"listed but absent: {missing}"


# ─── Spec 11 (2026-07-26): the chaos probes live OUTSIDE tessera-test on purpose (they are
# legitimately RED until the degraded mechanism ships). The cost of that choice is standing
# pattern #1 — a suite nothing runs rots silently. This is the `ls` for it.
def test_catches_an_unreachable_chaos_suite(fake_repo):
    (fake_repo / "chaos").mkdir(parents=True)
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "chaos" / "test_chaos.py").write_text("def test_x(): pass\n")
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "tessera-chaos").write_text("#!/bin/bash\necho nothing\n")
    (fake_repo / "scripts" / "run-tests.sh").write_text("#!/bin/bash\npytest scripts/ -q\n")
    bad = doccheck.check_chaos_suite_is_reachable()
    assert any("unreachable" in v for v in bad), bad


def test_catches_a_chaos_runner_that_is_not_executable(fake_repo):
    """A runner that exists and names the suite but has no +x bit invokes nothing."""
    (fake_repo / "chaos").mkdir(parents=True)
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "chaos" / "test_chaos.py").write_text("def test_x(): pass\n")
    (fake_repo / "bin").mkdir(exist_ok=True)
    runner = fake_repo / "bin" / "tessera-chaos"
    runner.write_text("#!/bin/bash\npytest chaos -q\n")
    runner.chmod(0o644)
    bad = doccheck.check_chaos_suite_is_reachable()
    assert any("not executable" in v for v in bad), bad


def test_passes_when_a_runner_invokes_the_chaos_suite(fake_repo):
    (fake_repo / "chaos").mkdir(parents=True)
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "chaos" / "test_chaos.py").write_text("def test_x(): pass\n")
    (fake_repo / "bin").mkdir(exist_ok=True)
    runner = fake_repo / "bin" / "tessera-chaos"
    runner.write_text("#!/bin/bash\npytest chaos -q\n")
    runner.chmod(0o755)
    assert doccheck.check_chaos_suite_is_reachable() == []


def test_chaos_check_is_silent_with_no_chaos_suite(fake_repo):
    """Must not fire on a repo that simply has no probes — a downstream scaffold."""
    assert doccheck.check_chaos_suite_is_reachable() == []


def test_run_tests_sh_also_satisfies_chaos_reachability(fake_repo):
    """The check is about reachability, not about WHICH runner — so folding the probes
    into run-tests.sh when they go green must not make it start failing."""
    (fake_repo / "chaos").mkdir(parents=True)
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "chaos" / "test_chaos.py").write_text("def test_x(): pass\n")
    rt = fake_repo / "scripts" / "run-tests.sh"
    rt.write_text('#!/bin/bash\nrun "chaos" "$PY" -m pytest chaos -q\n')
    rt.chmod(0o755)
    assert doccheck.check_chaos_suite_is_reachable() == []


# ── chaos-probe-count-is-current: the banner had already drifted silently once ─────────
#
# bin/tessera-chaos said "ALL 8 PROBES ARE GREEN" in two places while chaos/test_chaos.py
# held 11 — probes 9-11 landed on 2026-07-27, CLAUDE.md was updated, the runner's own banner
# was not. The first thing a reader sees understated the suite by three, in the file whose
# subject is whether the framework still notices when you break it.


def _chaos_repo(fake_repo, *, probes: int, banner: str):
    (fake_repo / "chaos").mkdir(parents=True, exist_ok=True)
    (fake_repo / "bin").mkdir(parents=True, exist_ok=True)
    (fake_repo / "chaos" / "test_chaos.py").write_text(
        "".join(f"def test_p{i}(): pass\n" for i in range(probes)))
    (fake_repo / "bin" / "tessera-chaos").write_text(banner)


def test_chaos_count_fires_when_the_banner_understates_the_suite(fake_repo):
    """THE regression, at the exact numbers it shipped with."""
    _chaos_repo(fake_repo, probes=11, banner="# ALL 8 PROBES ARE GREEN as of 2026-07-26\n")
    out = doccheck.check_chaos_probe_count_is_current()
    assert out and "claims 8" in out[0] and "defines 11" in out[0], out


def test_chaos_count_is_quiet_when_the_banner_is_right(fake_repo):
    _chaos_repo(fake_repo, probes=11, banner='# ALL 11 PROBES ARE GREEN\necho "All 11 green"\n')
    assert doccheck.check_chaos_probe_count_is_current() == []


def test_chaos_count_catches_a_second_stale_mention(fake_repo):
    """Two places quoted the number and only one was updated — which is how it drifted."""
    _chaos_repo(fake_repo, probes=11,
                banner='# ALL 11 PROBES ARE GREEN\necho "All 8 green as of 2026-07-26"\n')
    out = doccheck.check_chaos_probe_count_is_current()
    assert out and "claims 8" in out[0], out


def test_chaos_count_fires_when_the_banner_stops_stating_one(fake_repo):
    """A banner that says nothing cannot go stale, but it also cannot be verified — so
    silently dropping the number is reported rather than accepted."""
    _chaos_repo(fake_repo, probes=11, banner="# the chaos probes are green\n")
    out = doccheck.check_chaos_probe_count_is_current()
    assert out and "no longer states a probe count" in out[0], out


def test_chaos_count_ignores_a_green_tally_in_prose(fake_repo):
    """The first regex accepted any "<n> green", so a per-run tally would manufacture a
    second claim and fire the check on it. A FALSE alarm here is worse than a missed one:
    doccheck blocks the commit (arbiter, 2026-08-09)."""
    _chaos_repo(fake_repo, probes=11,
                banner='# ALL 11 PROBES ARE GREEN\n'
                       'echo "All 11 green"\n'
                       'echo "ran 11 probes, 10 green, 1 red"\n')
    assert doccheck.check_chaos_probe_count_is_current() == []


def test_chaos_count_is_silent_without_a_suite_or_runner(fake_repo):
    """Downstream scaffolds have neither — must not fire there."""
    assert doccheck.check_chaos_probe_count_is_current() == []


# ── adr-execution-recorded: decided-but-never-built must not read as shipped ───────────
#
# An accepted ADR looked identical whether it shipped or never shipped. That gap bit twice
# on 2026-07-26: ADR-0008's cut sat unexecuted 12 days while a session acted on its verdict,
# and P3 kept counting 10 days past the decision that superseded it. decision_amendments.py
# already surfaces REVISITED; nothing surfaced decided-and-never-done.


def _adr(repo, name, status, executed=None, body="# ADR\n"):
    d = repo / "docs" / "adr"
    d.mkdir(parents=True, exist_ok=True)
    text = f"# ADR-{name}\n\n- **Date:** 2026-07-26\n- **Status:** {status}\n"
    if executed is not None:
        text += f"- **Executed:** {executed}\n"
    (d / f"{name}-x.md").write_text(text + "\n" + body)


def test_accepted_adr_without_an_executed_line_is_flagged(fake_repo):
    _adr(fake_repo, "0099", "Accepted")
    bad = doccheck.check_adr_execution_recorded()
    assert any("no `- **Executed:**`" in b for b in bad), bad


def test_executed_naming_a_missing_artifact_is_flagged(fake_repo):
    """The load-bearing half. Without it, `Executed:` is just another doc claim — which is
    this checker's entire subject."""
    _adr(fake_repo, "0099", "Accepted", "2026-07-26 — `bin/never-built`")
    assert any("does not exist" in b for b in doccheck.check_adr_execution_recorded())


def test_executed_naming_a_real_artifact_passes(fake_repo):
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "real-thing").write_text("x")
    _adr(fake_repo, "0099", "Accepted", "2026-07-26 — `bin/real-thing`")
    assert doccheck.check_adr_execution_recorded() == []


def test_not_yet_is_explicit_and_allowed(fake_repo):
    """`not yet` is the POINT: decided-but-not-built becomes visible instead of inferable."""
    _adr(fake_repo, "0099", "Accepted", "not yet")
    assert doccheck.check_adr_execution_recorded() == []


def test_completion_claimed_with_no_artifact_is_flagged(fake_repo):
    """'Executed: done' proves nothing and must not satisfy the check."""
    _adr(fake_repo, "0099", "Accepted", "2026-07-26 — shipped it, trust me")
    assert any("names no artifact" in b for b in doccheck.check_adr_execution_recorded())


def test_backticked_identifiers_are_not_treated_as_artifacts(fake_repo):
    """`hook_distro` / `skillOverrides` are identifiers, not paths. Asserting on them would
    push authors to strip backticks from real prose to appease the checker."""
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "real-thing").write_text("x")
    _adr(fake_repo, "0099", "Accepted", "2026-07-26 — `bin/real-thing` sets `hook_distro`")
    assert doccheck.check_adr_execution_recorded() == []


@pytest.mark.parametrize("status", ["Proposed", "Watching", "Superseded by ADR-0008"])
def test_non_accepted_adrs_are_not_required_to_have_executed(fake_repo, status):
    """Proposed is undecided, Watching decided NOT to adopt, Superseded is history."""
    _adr(fake_repo, "0099", status)
    assert doccheck.check_adr_execution_recorded() == []


# ── drift-dimensions-have-producers ───────────────────────────────────────────────────
#
# iCPG's detector scored six dimensions and five of them measured whether an EDGE TYPE
# existed rather than whether the code had changed. Four of those types had no writer
# anywhere, so `test(0.30)` rode 712 of 712 stored events as a constant and `ownership`/
# `dependency` never fired in either direction. Nothing asserted that a consumed edge type
# had a producer — which is why it survived three evaluation passes, each of which stated
# a confident root cause and each of which was too shallow.

def _icpg(fake_repo, drift_src: str, producer_src: str = "") -> None:
    icpg = fake_repo / "scripts" / "icpg"
    icpg.mkdir(parents=True)
    (icpg / "drift.py").write_text(drift_src)
    (icpg / "store.py").write_text(producer_src)


def test_catches_a_dimension_reading_an_edge_type_nothing_writes(fake_repo):
    _icpg(fake_repo, "store.get_edges_from(reason.id, 'VALIDATED_BY')\n")
    bad = doccheck.check_drift_dimensions_have_producers()
    assert any("VALIDATED_BY" in v for v in bad), bad


def test_passes_when_every_read_edge_type_has_a_writer(fake_repo):
    _icpg(
        fake_repo,
        "store.get_edges_to(symbol_id, 'CREATES')\n",
        "edge = Edge(from_id=r, to_id=s, edge_type='CREATES')\n",
    )
    assert doccheck.check_drift_dimensions_have_producers() == []


def test_a_declared_cli_choice_counts_as_a_producer(fake_repo):
    """`icpg record --edge-type MODIFIES` is a real writer even with no literal in a
    write call. It must count — but only because `choices=` DECLARES the set; an
    unconstrained flag would make every edge type producible and the check vacuous."""
    _icpg(
        fake_repo,
        "store.get_edges_to(sym.id, 'MODIFIES')\n",
        "p.add_argument('--edge-type', default='CREATES',\n"
        "               choices=['CREATES', 'MODIFIES'])\n",
    )
    assert doccheck.check_drift_dimensions_have_producers() == []


def test_the_detector_cannot_vouch_for_itself(fake_repo):
    """A literal in drift.py must not count as its own producer, or the check
    congratulates the module for mentioning the edge type it consumes."""
    _icpg(
        fake_repo,
        "store.get_edges_from(r.id, 'REQUIRES')\n"
        "edge_type='REQUIRES'  # not a writer — no Edge is created here\n",
    )
    bad = doccheck.check_drift_dimensions_have_producers()
    assert any("REQUIRES" in v for v in bad), bad


def test_a_detector_that_reads_nothing_is_a_violation_not_a_pass(fake_repo):
    """Standing pattern #1 — what tells you THIS check died? An empty read set is
    either a detector that stopped detecting or a parser that drifted. Both are
    findings, and neither may exit green."""
    _icpg(fake_repo, "# no edge reads at all\n")
    bad = doccheck.check_drift_dimensions_have_producers()
    assert any("reads no edge type" in v for v in bad), bad


def test_not_vacuous_against_the_real_drift_module():
    """Feed the SHIPPED file back through the predicate with one edge type swapped for
    an unwritten one. A fresh check's green is not evidence until something has been
    seen to make it red — the `unrunnable-hooks-report-themselves` lesson, where a new
    check passed on its first run while incapable of flagging anything."""
    real = (doccheck.ROOT / doccheck.DRIFT_MODULE).read_text()
    assert doccheck._edge_types_read_by_the_detector(real), "parser reads nothing"
    poisoned = real.replace("'CREATES'", "'DRIFTS_FROM'")
    read = doccheck._edge_types_read_by_the_detector(poisoned)
    assert "DRIFTS_FROM" in read - doccheck._edge_types_any_code_writes()


def test_catches_an_untyped_edge_read(fake_repo):
    """The hole tessera-verify found in this very check (2026-07-27): the removed
    ownership dimension read `get_edges_to(sym.id)` with no type, named no edge
    type, and so passed the producer check while tripping no runtime test either.
    An untyped read means 'every edge type' and cannot be producer-checked."""
    _icpg(
        fake_repo,
        "store.get_edges_to(symbol_id, 'CREATES')\n"
        "edges = store.get_edges_to(sym.id)\n",
        "edge_type='CREATES'\n",
    )
    bad = doccheck.check_drift_dimensions_have_producers()
    assert any("no edge type" in v for v in bad), bad


def test_a_typed_read_is_not_flagged_as_untyped(fake_repo):
    """The other direction — otherwise every read trips it and the check is noise."""
    _icpg(
        fake_repo,
        "store.get_edges_to(symbol_id, 'CREATES')\n",
        "edge_type='CREATES'\n",
    )
    assert doccheck.check_drift_dimensions_have_producers() == []


# ── handoff-retires-its-own-figures (A6) ──────────────────────────────────────────────
#
# The handoff drifted four ways in one day (2026-07-26) and nothing could see it. doccheck
# excludes _project_specs/ because specs describe work NOT YET BUILT — naming an absent file
# is the point there — so the handoff, whose whole job is being true on arrival, had zero
# automated guard. Two other candidate shapes were prototyped and rejected ON MEASUREMENT;
# see RETIRED_FIGURES' comment. This is the one that survived.

def _handoff(fake_repo, body: str):
    d = fake_repo / "_project_specs" / "todos"
    d.mkdir(parents=True)
    (d / "active.md").write_text(body)


def test_catches_a_retired_figure_stated_as_live(fake_repo):
    """THE REAL HIT on its first run: the 2026-07-12 backlog still said "Fires at ≥3
    non-manual compaction_fired" 15 days after ADR-0015 retired that criterion."""
    _handoff(fake_repo, "- **Mnemos verdict.** Fires at **≥3 non-manual** compaction events.\n")
    bad = doccheck.check_handoff_retires_its_own_figures()
    assert any("≥3 non-manual" in v for v in bad), bad


def test_a_qualified_figure_is_fine(fake_repo):
    """The trail is kept on purpose — a retracted number may appear, but must read as dead."""
    _handoff(fake_repo, "⚠ RETIRED by ADR-0015, kept for the trail.\n"
                        "*Original text:* Fires at **≥3 non-manual** compaction events.\n")
    assert doccheck.check_handoff_retires_its_own_figures() == []


def test_the_marker_must_be_NEAR_the_figure(fake_repo):
    """A retraction 50 lines away does not qualify a claim a reader meets here."""
    _handoff(fake_repo, "SUPERSEDED — see ADR-0015.\n" + ("filler\n" * 20)
                        + "Fires at **≥3 non-manual** compaction events.\n")
    assert doccheck.check_handoff_retires_its_own_figures() != []


def test_a_missing_handoff_is_a_violation_not_a_pass(fake_repo):
    """It is the SessionStart channel. Absent must not read as clean."""
    assert doccheck.check_handoff_retires_its_own_figures() != []


def test_an_empty_figure_list_cannot_pass_silently(fake_repo, monkeypatch):
    """Standing pattern #1 aimed at this check: with nothing to look for it would be green
    forever while incapable of flagging anything — a vacuously-green check, which is the
    exact bug found inside `unrunnable-hooks-report-themselves`."""
    _handoff(fake_repo, "clean\n")
    monkeypatch.setattr(doccheck, "RETIRED_FIGURES", {})
    bad = doccheck.check_handoff_retires_its_own_figures()
    assert any("cannot fail" in v for v in bad), bad


def test_not_vacuous_against_the_real_handoff():
    """Feed the SHIPPED handoff back through the predicate with a retraction marker stripped.
    A fresh check's green is not evidence until something has been seen to make it red."""
    real = (doccheck.ROOT / doccheck.HANDOFF).read_text()
    assert doccheck.check_handoff_retires_its_own_figures() == [], "live handoff should be clean"
    poisoned = real.replace("RETIRED", "xx").replace("SUPERSEDED", "xx") \
                   .replace("retired", "xx").replace("superseded", "xx") \
                   .replace("Original text", "xx").replace("kept for the trail", "xx")
    lines = poisoned.splitlines()
    hits = [f for f in doccheck.RETIRED_FIGURES if any(f in l for l in lines)]
    assert hits, "no retired figure appears in the handoff at all — the check has no subject"


def test_executed_can_record_a_PRUNE(fake_repo):
    """A decision whose execution is a DELETION names paths that must NOT exist. The check
    assumed execution always creates, so ADR-0014 — whose entire execution was cutting a dead
    review stack — could not record itself: every artifact it named was correctly absent and
    read as a false claim. Found 2026-07-27 while accepting it."""
    _adr(fake_repo, "0102", "Accepted", "2026-07-27 — removed: `bin/gone`")
    assert doccheck.check_adr_execution_recorded() == []


def test_a_prune_that_never_happened_is_caught(fake_repo):
    """The stronger half: it verifies the cut was MADE, not merely recorded — exactly the
    decided-but-never-built gap this field exists for."""
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "still-here").write_text("#!/bin/sh\n")
    _adr(fake_repo, "0103", "Accepted", "2026-07-27 — removed: `bin/still-here`")
    bad = doccheck.check_adr_execution_recorded()
    assert any("still on disk" in v for v in bad), bad


def test_a_mixed_executed_line_checks_both_halves(fake_repo):
    """Created artifacts must exist AND removed ones must not, in the same line."""
    (fake_repo / "bin").mkdir(exist_ok=True)
    (fake_repo / "bin" / "made").write_text("#!/bin/sh\n")
    _adr(fake_repo, "0104", "Accepted", "2026-07-27 — `bin/made`; removed: `bin/absent`")
    assert doccheck.check_adr_execution_recorded() == []


# ── promo-adr-timeline-is-complete ────────────────────────────────────────────
# The bug: the published page (houseofyeti.com, linked from GitHub) carried
# ADR-0001..0006 while 19 were on disk, and no check read the file at all.


def _promo(repo, rows: str) -> None:
    (repo / "docs" / "promo").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "promo" / "index.html").write_text(
        '<div class="timeline" id="adrTimeline"></div>\n<script>\n  const adrs = [\n'
        f"{rows}  ];\n</script>\n"
    )


def test_promo_timeline_missing_an_adr_is_flagged(fake_repo):
    """The found bug: an ADR on disk with no row on the published timeline."""
    (fake_repo / "docs" / "adr" / "0002-second.md").write_text("# ADR 2")
    _promo(fake_repo, '    ["ADR-0001", "2026-06-22", "Accepted", "First", "x", "accepted"],\n')
    bad = doccheck.check_promo_adr_timeline_is_complete()
    assert any("0002" in v for v in bad), bad
    assert not any("0001" in v for v in bad), bad


def test_promo_timeline_complete_is_clean(fake_repo):
    """Guards the other direction — a complete timeline must not fire."""
    (fake_repo / "docs" / "adr" / "0002-second.md").write_text("# ADR 2")
    _promo(
        fake_repo,
        '    ["ADR-0001", "2026-06-22", "Accepted", "First", "x", "accepted"],\n'
        '    ["ADR-0002", "2026-06-26", "Accepted", "Second", "y", "accepted"],\n',
    )
    assert doccheck.check_promo_adr_timeline_is_complete() == []


def test_promo_prose_mention_does_not_satisfy_the_timeline(fake_repo):
    """A FOOTNOTE IS NOT A ROW — the failure this check was NOT written for.

    Row prose legitimately cites other ADRs ("Amends ADR-0005's readiness claim"), so a
    loose `ADR-0\\d{3}` scan would let a page with one row and many mentions go green.
    """
    (fake_repo / "docs" / "adr" / "0002-second.md").write_text("# ADR 2")
    _promo(
        fake_repo,
        '    ["ADR-0001", "2026-06-22", "Accepted", "First", "Amends ADR-0002 in passing.",'
        ' "accepted"],\n',
    )
    bad = doccheck.check_promo_adr_timeline_is_complete()
    assert any("0002" in v for v in bad), "a prose mention satisfied the check — it must not"


def test_promo_timeline_reformatted_fails_loud_not_open(fake_repo):
    """A guard that reads an artifact must not key on a convention the code may break —
    and where it must, breaking it has to fail LOUD.

    (observatory 2026-07-27: the declared-vocabulary guard keyed on the `_check_` naming
    convention and a rename walked past it, all 34 tests green.) This check keys on JS
    array-literal formatting, which an author is free to reformat. The difference is
    DIRECTION: no match means an empty `listed`, so every ADR reports missing and doccheck
    goes red — the opposite of walking past silently. Verified here, not assumed.
    """
    (fake_repo / "docs" / "adr" / "0002-second.md").write_text("# ADR 2")
    (fake_repo / "docs" / "promo").mkdir(parents=True, exist_ok=True)
    (fake_repo / "docs" / "promo" / "index.html").write_text(
        "<script>const adrs = [{id: 'ADR-0001'}, {id: 'ADR-0002'}];</script>\n"
    )
    bad = doccheck.check_promo_adr_timeline_is_complete()
    assert len(bad) == 2, f"reformatting must fail loud over every ADR, got: {bad}"


def test_promo_absent_is_not_an_error(fake_repo):
    """Asserts the timeline is complete, not that a marketing page must exist."""
    assert doccheck.check_promo_adr_timeline_is_complete() == []


# ─── BUG (2026-08-06): the standing patterns were EMITTED and did not ARRIVE. The surfacer
# put the handoff pointer and all 12 patterns in one hook output — 10,878 chars against
# Claude Code's documented 10,000-char cap — so the harness replaced everything past ~2KB
# with a file path and exactly ONE pattern reached the model. `standing-patterns-are-surfaced`
# was green throughout: it asked whether the block was EXTRACTED, which was true. These
# tests exist because that check could not see one layer further, and neither could its
# author until the parts were run and measured.

def _patterns_repo(root, parts=2, n_patterns=3, pattern_len=40):
    """A repo with a handoff, an emitter that chunks it, and settings that register parts."""
    (root / "_project_specs" / "todos").mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{i}. **Lesson {i}.** {'x' * pattern_len}" for i in range(1, n_patterns + 1))
    (root / "_project_specs" / "todos" / "active.md").write_text(
        f"## Handoff — pick up here (test)\n\n### Standing patterns\n\n{body}\n\n## Older\n")
    src = Path(doccheck.__file__).resolve().parent.parent / ".claude" / "scripts" / "tessera-patterns-surface.sh"
    dst = root / ".claude" / "scripts" / "tessera-patterns-surface.sh"
    dst.write_text(src.read_text())
    dst.chmod(0o755)
    cmd = ('if [ -x "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/tessera-patterns-surface.sh" ]; then '
           'exec "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/tessera-patterns-surface.sh" '
           '--part %d --of %d; fi; exit 0')
    (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": cmd % (p, parts)}]}
        for p in range(1, parts + 1)]}}))
    return root


def test_patterns_parts_cover_every_lesson(fake_repo):
    _patterns_repo(fake_repo)
    assert doccheck.check_standing_patterns_fit_the_cap() == []


def test_catches_unregistered_part(fake_repo):
    """--of 2 declared but only part 1 wired: half the lessons are surfaced by nothing."""
    root = _patterns_repo(fake_repo, parts=2)
    d = json.loads((root / ".claude" / "settings.json").read_text())
    d["hooks"]["SessionStart"] = [e for e in d["hooks"]["SessionStart"]
                                  if "--part 2" not in json.dumps(e)]
    (root / ".claude" / "settings.json").write_text(json.dumps(d))
    bad = doccheck.check_standing_patterns_fit_the_cap()
    assert any("expected [1, 2]" in v for v in bad), bad


def test_catches_emitter_not_registered_at_all(fake_repo):
    root = _patterns_repo(fake_repo)
    (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": []}}))
    bad = doccheck.check_standing_patterns_fit_the_cap()
    assert any("emitted by nothing" in v for v in bad), bad


def test_catches_part_over_budget(fake_repo, monkeypatch):
    """The original bug: one output carrying more than the harness will deliver."""
    monkeypatch.setattr(doccheck, "_HOOK_OUTPUT_BUDGET", 200)
    _patterns_repo(fake_repo, parts=1, n_patterns=4, pattern_len=100)
    bad = doccheck.check_standing_patterns_fit_the_cap()
    assert any("over the 200 budget" in v for v in bad), bad


def test_catches_dropped_pattern(fake_repo):
    """A chunker that loses a lesson reproduces the original bug with better numbers."""
    root = _patterns_repo(fake_repo)
    emitter = root / ".claude" / "scripts" / "tessera-patterns-surface.sh"
    emitter.write_text(emitter.read_text().replace(
        "for (i = 0; i <= max; i++) if (owner[i] == part)",
        "for (i = 0; i < max; i++) if (owner[i] == part)"))
    bad = doccheck.check_standing_patterns_fit_the_cap()
    assert any("MISSING" in v for v in bad), bad


def test_surfaced_check_is_not_satisfied_by_a_comment(fake_repo):
    """The retarget's own lesson: a substring test over a shell script cannot tell code from
    prose. The old check asserted "Standing patterns" appeared in the surfacer; when the block
    moved out, the file kept a COMMENT saying so and the check would have stayed green."""
    root = _patterns_repo(fake_repo)
    (root / ".claude" / "scripts" / "tessera-patterns-surface.sh").unlink()
    (root / ".claude" / "scripts" / "tessera-watch-surface.sh").write_text(
        "#!/bin/bash\n# The Standing patterns used to be printed here; see the observatory.\n")
    bad = doccheck.check_standing_patterns_are_surfaced()
    assert any("nothing emits it" in v for v in bad), bad


# ─── BUG (2026-08-06, found by a human asking "no drift?"): moving the standing patterns to
# their own hook left CLAUDE.md asserting that `tessera-watch-surface.sh` prints them. False
# the moment the split landed, and doccheck stayed green at 38 checks. The sixth-plus instance
# of the same shape, and the first one introduced BY the commit that was fixing a delivery bug.
def test_catches_stale_patterns_emitter_claim(fake_repo):
    (fake_repo / "docs" / "wiring.md").write_text(
        "`tessera-watch-surface.sh` prints the handoff pointer and the Standing patterns block.")
    bad = doccheck.check_docs_name_the_right_patterns_emitter()
    assert any("tessera-watch-surface.sh" in v for v in bad), bad


def test_passes_when_the_right_emitter_is_named(fake_repo):
    (fake_repo / "docs" / "wiring.md").write_text(
        "`tessera-patterns-surface.sh` prints the Standing patterns block, in two parts.")
    assert doccheck.check_docs_name_the_right_patterns_emitter() == []


def test_patterns_emitter_check_ignores_unrelated_hook_prose(fake_repo):
    """A doc naming a surfacer with no standing-patterns claim must not trip the check."""
    (fake_repo / "docs" / "wiring.md").write_text(
        "`tessera-findings-surface.sh` injects the downstream findings backlog.")
    assert doccheck.check_docs_name_the_right_patterns_emitter() == []


def test_observatory_may_record_superseded_wiring(fake_repo):
    """The observatory is the historical record — it MUST be able to describe the old wiring."""
    (fake_repo / "docs" / "observatory.md").write_text(
        "`tessera-watch-surface.sh` used to print the Standing patterns block; it spilled.")
    assert doccheck.check_docs_name_the_right_patterns_emitter() == []


# ─── BUG (2026-08-07): the cohesion contract's own rule is "evidence is referenced by
# sibling-relative path so the map survives a machine move" — 30 such citations in that one
# file, and `check_referenced_paths_exist` only walks REPO_DIRS, so none were verified.
# Found while renaming the Pattern lane pr-arbiter → arbiter. NOTE, recorded honestly: this
# check would NOT have caught that rename (every path existed). It guards the class one step
# out — a peer moving or renaming a file the contract cites — which is why the tests below
# are written against failures that were NOT just fixed.
def _peer(fake_repo, name):
    root = fake_repo.parent / name
    (root / "src").mkdir(parents=True, exist_ok=True)
    return root


def test_catches_sibling_file_that_moved(fake_repo):
    _peer(fake_repo, "sibpeer_moved")
    (fake_repo / "docs" / "contracts" / "c.md").write_text(
        "The engine lives in `../sibpeer_moved/src/reviewer.py`.")
    bad = doccheck.check_sibling_paths_exist()
    assert any("sibpeer_moved/src/reviewer.py" in v for v in bad), bad


def test_passes_when_sibling_file_exists(fake_repo):
    peer = _peer(fake_repo, "sibpeer_ok")
    (peer / "src" / "reviewer.py").write_text("x = 1\n")
    (fake_repo / "docs" / "contracts" / "c.md").write_text(
        "The engine lives in `../sibpeer_ok/src/reviewer.py`.")
    assert doccheck.check_sibling_paths_exist() == []


def test_skips_peer_that_is_not_checked_out(fake_repo):
    """A peer absent from this machine is unknowable, not a false claim.

    A check that goes red on a fresh clone is one people learn to ignore — and it is
    pre-commit-blocking here, so it would block every commit on a machine without the peers.
    """
    (fake_repo / "docs" / "contracts" / "c.md").write_text(
        "See `../sibpeer_never_cloned/docs/design.md` for the study.")
    assert doccheck.check_sibling_paths_exist() == []


def test_expands_brace_sets_rather_than_skipping_them(fake_repo):
    """`{a,b}.py` is a closed list of real files, unlike the repo-path check's placeholder `{}`.

    This is the half that would rot silently: a brace set treated as a placeholder passes
    while naming three files, any of which may be gone.
    """
    peer = _peer(fake_repo, "sibpeer_braces")
    (peer / "src" / "reviewer.py").write_text("x = 1\n")
    (peer / "src" / "triage.py").write_text("x = 1\n")
    (fake_repo / "docs" / "contracts" / "c.md").write_text(
        "Engine: `../sibpeer_braces/src/{reviewer,second_pass,triage}.py`.")
    bad = doccheck.check_sibling_paths_exist()
    assert len(bad) == 1, bad
    assert "second_pass.py" in bad[0], bad


def test_real_repo_sibling_paths_are_green():
    """The live assertion — every checked-out peer path this repo's docs cite is on disk."""
    assert doccheck.check_sibling_paths_exist() == []


def test_expands_every_brace_set_not_just_the_first(fake_repo):
    """Two brace sets in one path expand to the CROSS PRODUCT, not one set plus a literal.

    Found by `bin/tessera-verify` on the day the check shipped: `BRACE_SET.search` expanded
    only the first set, leaving the second literal — and a stat on a literal `{c,d}.py` can
    never succeed, so the check reported a permanent false violation on a legal citation.
    Regression-guarded here because a pre-commit-blocking check that can go permanently red
    is worse than one that misses.
    """
    assert doccheck._expand_braces("src/x.py") == ["src/x.py"]
    assert doccheck._expand_braces("{a,b}/x/{c,d}.py") == [
        "a/x/c.py", "a/x/d.py", "b/x/c.py", "b/x/d.py"]

    peer = _peer(fake_repo, "sibpeer_two_sets")
    for d in ("src", "lib"):
        (peer / d / "inner").mkdir(parents=True, exist_ok=True)
        (peer / d / "inner" / "keep.py").write_text("x = 1\n")
    (fake_repo / "docs" / "contracts" / "c.md").write_text(
        "Engine: `../sibpeer_two_sets/{src,lib}/inner/{keep,gone}.py`.")
    bad = doccheck.check_sibling_paths_exist()
    assert len(bad) == 2, bad
    assert all("gone.py" in v for v in bad), bad


# ─── ADR-0021 (2026-08-09): the eager-prefix figure in docs/observatory.md was a one-shot
# chars/4 estimate taken 2026-07-30 and never recomputed. Not a bug a human found — a bug
# a human COULD NOT find, because a frozen number in prose looks identical whether it is
# current or ten days stale. Deep Agents tracks the same quantity as a per-release metric;
# that mirror is what made ours visible as a doc claim. Each test below plants the failure
# rather than confirming the fix (standing pattern #10).
def _metered_repo(root, claude_md: str, figure: str):
    (root / "CLAUDE.md").write_text(claude_md)
    (root / "docs" / "observatory.md").write_text(
        f"### The eager prefix\n\n**METERED 2026-08-09: {figure} tokens tracked** — by the meter.\n")


def test_catches_drifted_eager_prefix_figure(fake_repo):
    _metered_repo(fake_repo, "x" * 4000, "500")       # 4000 chars ≈ 1000 tokens, not 500
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("METERED figure is 500" in v and "1,000" in v for v in bad), bad


def test_catches_missing_eager_prefix_figure(fake_repo):
    (fake_repo / "CLAUDE.md").write_text("x" * 4000)
    (fake_repo / "docs" / "observatory.md").write_text("The prefix is about 15.4k tokens.\n")
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("unmetered again" in v for v in bad), bad


def test_passes_when_eager_prefix_figure_matches(fake_repo):
    _metered_repo(fake_repo, "x" * 4000, "1,000")
    assert doccheck.check_eager_prefix_figure_is_current() == []


def test_tolerates_wording_tweaks_within_the_band(fake_repo):
    """A 5% band mechanizes the "~" the prose claims. A check that fires on every reworded
    sentence teaches `--no-verify`, which is how a load-bearing check stops being one."""
    _metered_repo(fake_repo, "x" * 4120, "1,000")     # +3%, a wording-sized change
    assert doccheck.check_eager_prefix_figure_is_current() == []


def test_unmeasurable_prefix_is_reported_not_silently_green(fake_repo):
    """THE ONE THAT MATTERS. If the meter cannot run, the figure is UNVERIFIED — and an
    unverified claim must not read as a confirmed one. Standing pattern #1 aimed at this
    check: what tells you the check itself died?"""
    (fake_repo / "docs" / "observatory.md").write_text(
        "**METERED 2026-08-09: 15,356 tokens tracked** — by the meter.\n")
    # No CLAUDE.md at all: the meter cannot measure anything.
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("unverifiable, not confirmed" in v for v in bad), bad


def test_meter_derives_eager_skills_from_claude_md_imports(fake_repo):
    """De-eagering a skill must move the meter without anyone editing it. A hardcoded list
    would keep reporting the old corpus and read as stable — the failure being guarded."""
    (fake_repo / ".claude" / "skills" / "s").mkdir(parents=True)
    (fake_repo / ".claude" / "skills" / "s" / "SKILL.md").write_text("y" * 800)
    (fake_repo / "CLAUDE.md").write_text("head\n@.claude/skills/s/SKILL.md\n")
    assert prefix_meter.tracked_total(fake_repo) == prefix_meter.tokens("head\n@.claude/skills/s/SKILL.md\n") + 200

    (fake_repo / "CLAUDE.md").write_text("head\n")   # de-eagered
    assert prefix_meter.tracked_total(fake_repo) == prefix_meter.tokens("head\n")


# ─── FOUND BY `bin/tessera-verify` 2026-08-09, hours after the meter shipped, against the
# claims its author wrote. Three fail-open defects in one file whose entire purpose is to
# stop a measurement drifting silently — the check that guards against silent drift was
# itself silently drifting. Standing pattern #1 aimed at the newest instrument.
def _emitter_repo(root, script: str, parts: int = 1):
    (root / "CLAUDE.md").write_text("x" * 4000)
    emitter = root / ".claude" / "scripts" / "tessera-patterns-surface.sh"
    emitter.write_text(script)
    emitter.chmod(0o755)
    (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": [
        {"hooks": [{"command": f'"$X/.claude/scripts/tessera-patterns-surface.sh" '
                               f'--part {i} --of {parts}'}]} for i in range(1, parts + 1)]}}))
    (root / "docs" / "observatory.md").write_text(
        "**METERED 2026-08-09: 1,000 tokens tracked** — by the meter.\n")
    return emitter


def test_crashing_emitter_is_unverifiable_not_a_smaller_total(fake_repo):
    """THE DEFECT: `check=False` and no returncode inspection, so an emitter that ran,
    emitted partial output and DIED was measured as a success — a silently smaller prefix
    that passed. Exactly the outcome the check's own docstring denied."""
    _emitter_repo(fake_repo, "#!/bin/sh\nprintf 'xxxx'\nexit 1\n")
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("unverifiable, not confirmed" in v for v in bad), bad


def test_absent_but_registered_emitter_is_unverifiable_not_drift(fake_repo):
    """Absence used to vanish into `[]`, surfacing as a DRIFT message whose remedy was to
    re-record the (understated) figure. A wrong remedy is worse than no message."""
    emitter = _emitter_repo(fake_repo, "#!/bin/sh\nprintf 'xxxx'\n")
    emitter.unlink()
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("unverifiable, not confirmed" in v for v in bad), bad
    assert not any("re-run the meter and update the figure" in v for v in bad), bad


def test_unregistered_emitter_is_a_measurable_absence_not_an_error(fake_repo):
    """The distinction that makes the two tests above meaningful: nothing registered is a
    real state (no such component), not a failure to measure."""
    (fake_repo / "CLAUDE.md").write_text("x" * 4000)
    (fake_repo / "docs" / "observatory.md").write_text(
        "**METERED 2026-08-09: 1,000 tokens tracked** — by the meter.\n")
    assert doccheck.check_eager_prefix_figure_is_current() == []


def test_unparseable_settings_is_unverifiable(fake_repo):
    _emitter_repo(fake_repo, "#!/bin/sh\nprintf 'xxxx'\n")
    (fake_repo / ".claude" / "settings.json").write_text("{not json")
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("unverifiable, not confirmed" in v for v in bad), bad


def test_eager_import_resolves_to_tracked_source_on_a_clean_clone(fake_repo):
    """THE REFUTED CLAIM. `.claude/skills` is a gitignored symlink `install.sh` creates, so
    before install the imported path is absent while its content is tracked at `skills/`.
    The meter skipped it and under-measured by 37% on a clean clone — the very
    "fails differently on every clone" outcome the docstring claimed to have avoided."""
    (fake_repo / "skills" / "s").mkdir(parents=True)
    (fake_repo / "skills" / "s" / "SKILL.md").write_text("y" * 800)
    (fake_repo / "CLAUDE.md").write_text("head\n@.claude/skills/s/SKILL.md\n")
    # No .claude/skills symlink at all — the state of a fresh clone.
    assert not (fake_repo / ".claude" / "skills").exists()
    total = prefix_meter.tracked_total(fake_repo)
    assert total == prefix_meter.tokens("head\n@.claude/skills/s/SKILL.md\n") + 200, total


def test_missing_eager_import_is_an_error_not_a_silent_skip(fake_repo):
    """An import that resolves nowhere must stop the measurement. Skipping it understates
    the prefix, and an understated prefix reads as a real one."""
    (fake_repo / "CLAUDE.md").write_text("head\n@.claude/skills/gone/SKILL.md\n")
    with pytest.raises(OSError, match="not on disk"):
        prefix_meter.tracked_total(fake_repo)


# ─── SECOND `bin/tessera-verify` pass, same day. The first pass reported the anchored
# import regex as "a caveat, not a refutation"; it was read as minor and not acted on.
# The second pass demonstrated it as a >2x understatement reported GREEN. A caveat from a
# falsifier is a finding you have not measured yet.
def _import_repo(root, claude_md: str, imported_chars: int = 800):
    (root / "docs" / "big.md").write_text("y" * imported_chars)
    (root / "CLAUDE.md").write_text(claude_md)


def test_inline_eager_import_is_measured(fake_repo):
    """`See @docs/x.md for the reasoning.` is a real Claude Code import. Anchored `^@...$`
    made it invisible: on the live repo that hid 31,346 tokens behind an exit-0 green."""
    _import_repo(fake_repo, "head\nSee @docs/big.md for the reasoning.\n")
    total = prefix_meter.tracked_total(fake_repo)
    assert total == prefix_meter.tokens("head\nSee @docs/big.md for the reasoning.\n") + 200


def test_trailing_space_eager_import_is_measured(fake_repo):
    _import_repo(fake_repo, "head\n@docs/big.md \n")
    assert prefix_meter.tracked_total(fake_repo) == prefix_meter.tokens("head\n@docs/big.md \n") + 200


def test_fenced_example_is_not_an_import(fake_repo):
    """Widening the regex must not turn documentation OF the syntax into an import."""
    body = "head\n```\n@docs/nowhere.md\n```\n"
    (fake_repo / "CLAUDE.md").write_text(body)
    assert prefix_meter.tracked_total(fake_repo) == prefix_meter.tokens(body)


def test_at_handle_without_a_slash_is_not_an_import(fake_repo):
    body = "head\nping @lorenzo about it\n"
    (fake_repo / "CLAUDE.md").write_text(body)
    assert prefix_meter.tracked_total(fake_repo) == prefix_meter.tokens(body)


def test_wrong_shaped_settings_is_unverifiable_not_a_traceback(fake_repo):
    """`{"hooks": "oops"}` is valid JSON. Uncaught, the AttributeError escaped doccheck's
    handler and aborted all 41 checks with a traceback instead of one unverifiable line."""
    (fake_repo / "CLAUDE.md").write_text("x" * 4000)
    (fake_repo / ".claude" / "settings.json").write_text('{"hooks": "oops"}')
    (fake_repo / "docs" / "observatory.md").write_text(
        "**METERED 2026-08-09: 1,000 tokens tracked** — by the meter.\n")
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("unverifiable, not confirmed" in v for v in bad), bad


# ─── 2026-08-09, third finding of the same session: `referenced-paths-exist` was RED on a
# clean clone, because docs name `.claude/skills/...` — a gitignored symlink `install.sh`
# creates. So the pre-commit hook blocked on a fresh clone, before install had ever run.
# Surfaced by `bin/tessera-verify` while verifying the prefix meter, one check over from
# what it was asked about.
def test_mirror_symlink_paths_resolve_on_a_clean_clone(fake_repo):
    (fake_repo / "skills" / "base").mkdir(parents=True)
    (fake_repo / "skills" / "base" / "SKILL.md").write_text("x")
    assert not (fake_repo / ".claude" / "skills").exists()      # pre-install state
    (fake_repo / "docs" / "x.md").write_text("See `.claude/skills/base/SKILL.md`.")
    assert doccheck.check_referenced_paths_exist() == []


def test_bare_mirror_dir_resolves(fake_repo):
    (fake_repo / "agents").mkdir()
    (fake_repo / "docs" / "x.md").write_text("The `.claude/agents` dir is a symlink.")
    assert doccheck.check_referenced_paths_exist() == []


def test_phantom_under_a_mirror_dir_still_fails(fake_repo):
    """The rewrite must not launder a phantom. A path checker that resolves anything is
    worse than none, because it reports absence as presence."""
    (fake_repo / "skills").mkdir()
    (fake_repo / "docs" / "x.md").write_text("See `.claude/skills/ghost/SKILL.md`.")
    bad = doccheck.check_referenced_paths_exist()
    assert any("ghost" in v for v in bad), bad


def test_non_mirror_claude_path_does_not_resolve_via_its_namesake(fake_repo):
    """THE REASON the rewrite names three dirs instead of stripping `.claude/`. A blanket
    strip would resolve `.claude/scripts/doccheck.py` to the real `scripts/doccheck.py`
    and pass a wrong path. `.claude/scripts/` is tracked and must fail when it is wrong."""
    (fake_repo / "scripts").mkdir(exist_ok=True)
    (fake_repo / "scripts" / "real.py").write_text("x")
    (fake_repo / "docs" / "x.md").write_text("See `.claude/scripts/real.py`.")
    bad = doccheck.check_referenced_paths_exist()
    assert any(".claude/scripts/real.py" in v for v in bad), bad


# ─── FOUND BY ARBITER 2026-08-09, in the code written to guard against this exact shape.
# `import prefix_meter` was module-level for one day: a missing or SYNTACTICALLY BROKEN
# sibling killed the whole doccheck process before any check ran, so the pre-commit hook
# lost all 41 checks — and eager-prefix-figure-is-current's own try/except, written to turn
# this into one reported line, was unreachable. Standing pattern #1, self-inflicted.
# The first fix caught only ImportError and still died on a syntax error; that near-miss is
# why both tests below raise SyntaxError rather than ImportError.
def _meter_raises(monkeypatch, exc):
    monkeypatch.setattr(doccheck, "_prefix_meter",
                        lambda: (_ for _ in ()).throw(exc))


def test_broken_meter_degrades_the_prefix_check_instead_of_killing_doccheck(fake_repo, monkeypatch):
    _meter_raises(monkeypatch, SyntaxError("'(' was never closed"))
    (fake_repo / "docs" / "observatory.md").write_text(
        "**METERED 2026-08-09: 1,000 tokens tracked** — by the meter.\n")
    bad = doccheck.check_eager_prefix_figure_is_current()
    assert any("cannot be imported" in v and "unverifiable" in v for v in bad), bad


def test_broken_meter_degrades_path_checking_and_says_so(fake_repo, monkeypatch):
    """Degrade, do not die AND do not go blind: fall back to literal resolution — the
    pre-2026-08-09 behaviour — and report that mirror resolution is off, because a silently
    literal run is red on a clean clone for reasons no reader could diagnose."""
    _meter_raises(monkeypatch, SyntaxError("'(' was never closed"))
    (fake_repo / "docs" / "x.md").write_text("See `scripts/ghost.py`.")
    bad = doccheck.check_referenced_paths_exist()
    assert any("resolution is OFF" in v for v in bad), bad
    assert any("ghost.py" in v for v in bad), bad      # still checking, not blind


def test_duplicate_eager_import_is_counted_once(fake_repo):
    """DELIBERATE, not incidental. An import named twice is LOADED once, so one count is
    the correct total. arbiter read the dict overwrite as an understating bug and proposed
    accumulating counts, which would over-report."""
    (fake_repo / "skills" / "s").mkdir(parents=True)
    (fake_repo / "skills" / "s" / "SKILL.md").write_text("y" * 800)
    body = "head\n@.claude/skills/s/SKILL.md\nmore @.claude/skills/s/SKILL.md again\n"
    (fake_repo / "CLAUDE.md").write_text(body)
    assert prefix_meter.tracked_total(fake_repo) == prefix_meter.tokens(body) + 200


def test_absent_claude_md_raises_a_descriptive_error(fake_repo):
    with pytest.raises(OSError, match="CLAUDE.md is not on disk"):
        prefix_meter.tracked_total(fake_repo)


# ─── 2026-08-09. `tessera-verify` and arbiter both flagged that canonical_path prefers the
# literal path, so a REAL `.claude/skills` directory would be measured stale. Both framed it
# as a resolver-ordering choice. It was neither — it was an unenforced precondition: when the
# path is a symlink both resolutions are the SAME FILE. Asserting the shape dissolves the
# question instead of picking a side, and needs no definition of "diverged".
def _mirror_repo(root):
    for d in ("skills", "commands", "agents"):
        (root / d).mkdir(exist_ok=True)
    return root


def test_absent_mirrors_are_green(fake_repo):
    """Every fresh clone, before ./install.sh. This check runs in the pre-commit hook, so
    absence must not block; it is machine state and belongs to install.sh's verify().

    The canonical dirs are created and then asserted ABSENT-as-mirrors, which is the real
    pre-install shape: `skills/` present, `.claude/skills` not yet linked. arbiter noted the
    first version was vacuous — `_mirror_repo`'s setup had no effect on the assertion, so it
    could not distinguish this state from "nothing exists at all". Both are now asserted."""
    _mirror_repo(fake_repo)
    assert (fake_repo / "skills").is_dir()                     # canonical present…
    assert not (fake_repo / ".claude" / "skills").exists()     # …mirror not yet linked
    assert doccheck.check_mirror_links_are_symlinks() == []


def test_wrong_target_fails_even_when_canonical_dir_is_missing(fake_repo):
    """THE HOLE arbiter found, four hours after this check shipped. `target.exists() and …`
    short-circuited, so a symlink pointing at a wrong-but-EXISTING path passed whenever the
    canonical dir was absent — a representable divergence inside the check whose whole
    purpose is to make divergence unrepresentable."""
    (fake_repo / "elsewhere").mkdir()
    (fake_repo / ".claude" / "skills").symlink_to(Path("..") / "elsewhere")
    assert not (fake_repo / "skills").exists()
    bad = doccheck.check_mirror_links_are_symlinks()
    # Assert the message NAMES BOTH the mirror and the wrong target it points at, rather
    # than the connective phrasing between them. arbiter raised the substring `not skills/`
    # twice as brittle; the first rejection was right that the test passes and wrong that
    # there was nothing to improve — keying on wording tests the sentence, keying on both
    # identifiers tests what an operator actually needs the message to tell them.
    assert any(".claude/skills" in v and "elsewhere" in v for v in bad), bad


def test_symlinked_mirrors_are_green(fake_repo):
    _mirror_repo(fake_repo)
    for d in ("skills", "commands", "agents"):
        (fake_repo / ".claude" / d).symlink_to(Path("..") / d)
    assert doccheck.check_mirror_links_are_symlinks() == []


def test_real_directory_mirror_fails(fake_repo):
    """THE STATE THE FIX EXISTS FOR: a real dir holding a copy nothing syncs. It reads as
    installed, shadows skills/, and is what would make a deleted skill go green."""
    _mirror_repo(fake_repo)
    (fake_repo / ".claude" / "skills").mkdir()
    (fake_repo / ".claude" / "skills" / "stale").mkdir()
    bad = doccheck.check_mirror_links_are_symlinks()
    assert any("NOT a symlink" in v and ".claude/skills" in v for v in bad), bad


def test_mirror_symlink_to_the_wrong_target_fails(fake_repo):
    _mirror_repo(fake_repo)
    (fake_repo / ".claude" / "commands").symlink_to(Path("..") / "skills")
    bad = doccheck.check_mirror_links_are_symlinks()
    assert any(".claude/commands" in v for v in bad), bad


def test_broken_mirror_symlink_fails(fake_repo):
    """A dangling symlink: `exists()` is False but `is_symlink()` is True. Testing only
    `exists()` would silently treat this as the pre-install state and pass."""
    _mirror_repo(fake_repo)
    (fake_repo / ".claude" / "agents").symlink_to(Path("..") / "nowhere")
    bad = doccheck.check_mirror_links_are_symlinks()
    assert any(".claude/agents" in v for v in bad), bad


def test_dangling_mirror_symlink_fails_even_when_canonical_dir_is_missing(fake_repo):
    """The hole the explicit dangling branch closes: with `agents/` also absent, the
    `target.exists()` guard short-circuits and a broken link would have PASSED."""
    (fake_repo / ".claude" / "agents").symlink_to(Path("..") / "nowhere")
    assert not (fake_repo / "agents").exists()
    bad = doccheck.check_mirror_links_are_symlinks()
    assert any("dangling" in v for v in bad), bad


# ── verdict-channel-literals-match-contract ───────────────────────────────────
#
# BUG (2026-08-09): `cmd_run` wrote verdict_channel "final-message"; `cmd_stats` warned on
# "message". The ⚠ banner for a regression to the fragile channel could never fire, in the
# file rewritten specifically to survive that regression. Three copies of one vocabulary —
# writer, reader, contract — and no check tied any two together.

def _fake_verify_tool(repo: Path, body: str) -> None:
    (repo / "bin").mkdir(exist_ok=True)
    (repo / "bin" / "tessera-verify").write_text(body)


def _channel_contract(repo: Path, text: str) -> None:
    (repo / "docs" / "contracts" / "verification-event.md").write_text(text)


def test_catches_a_channel_the_contract_never_documents(fake_repo):
    _fake_verify_tool(fake_repo, 'CHANNEL_FILE = "file"\nCHANNEL_MESSAGE = "final-message"\n')
    _channel_contract(fake_repo, 'verdict_channel is "file" when trusted.')
    bad = doccheck.check_verdict_channel_literals_match_contract()
    assert any("final-message" in v for v in bad), bad


def test_passes_when_the_contract_documents_both_channels(fake_repo):
    _fake_verify_tool(fake_repo, 'CHANNEL_FILE = "file"\nCHANNEL_MESSAGE = "final-message"\n')
    _channel_contract(fake_repo, 'verdict_channel: "file" (trusted) | "final-message" (scraped)')
    assert doccheck.check_verdict_channel_literals_match_contract() == []


def test_a_renamed_constant_FAILS_rather_than_skipping(fake_repo):
    """The failure mode this check must not have.

    A guard that silently passes when it can no longer find its subject is decoration —
    2026-07-27's declared-vocabulary guard keyed on a `_check_` prefix and one rename walked
    straight past it. Losing the anchor here has to be loud.
    """
    _fake_verify_tool(fake_repo, 'CHANNEL_A = "file"\nCHANNEL_B = "final-message"\n')
    _channel_contract(fake_repo, 'verdict_channel: "file" | "final-message"')
    bad = doccheck.check_verdict_channel_literals_match_contract()
    assert any("no longer be checked" in v for v in bad), bad


def test_no_channel_claim_means_nothing_to_check(fake_repo):
    _fake_verify_tool(fake_repo, 'CHANNEL_FILE = "file"\nCHANNEL_MESSAGE = "final-message"\n')
    _channel_contract(fake_repo, "This contract says nothing about channels.")
    assert doccheck.check_verdict_channel_literals_match_contract() == []


def test_the_live_repo_agrees_with_its_own_contract():
    """No fixture: the real bin/tessera-verify against the real contract."""
    assert doccheck.check_verdict_channel_literals_match_contract() == []


# --- checkpoint-budget-matches-p3 (2026-08-10) ------------------------------------


def _budget_repo(root, watch_value: str, checkpoint_value: str):
    (root / "bin").mkdir(exist_ok=True)
    (root / "scripts" / "mnemos").mkdir(parents=True, exist_ok=True)
    (root / "bin" / "tessera-watch").write_text(
        f"#!/usr/bin/env python3\nRESTORE_BUDGET_BYTES = {watch_value}\n")
    (root / "scripts" / "mnemos" / "checkpoint.py").write_text(
        f"CHECKPOINT_BUDGET_BYTES = {checkpoint_value}\n")


def test_matching_budgets_pass(fake_repo):
    _budget_repo(fake_repo, "8_000", "8_000")
    assert doccheck.check_checkpoint_budget_matches_p3() == []


def test_the_same_value_written_differently_is_not_a_false_positive(fake_repo):
    _budget_repo(fake_repo, "8000", "8_000")
    assert doccheck.check_checkpoint_budget_matches_p3() == []


def test_diverged_budgets_fail(fake_repo):
    _budget_repo(fake_repo, "9_500", "8_000")
    bad = doccheck.check_checkpoint_budget_matches_p3()
    assert any("diverged" in v for v in bad), bad


def test_a_renamed_budget_constant_FAILS_rather_than_skipping(fake_repo):
    """Losing the anchor must be loud, not green (#10's corollary)."""
    _budget_repo(fake_repo, "8_000", "8_000")
    (fake_repo / "scripts" / "mnemos" / "checkpoint.py").write_text(
        "CHECKPOINT_BUDGET_LIMIT = 8_000\n")
    bad = doccheck.check_checkpoint_budget_matches_p3()
    assert any("no longer defines" in v for v in bad), bad


def test_a_missing_file_reports_rather_than_raising(fake_repo):
    bad = doccheck.check_checkpoint_budget_matches_p3()
    assert any("is missing" in v for v in bad), bad


def test_an_UNREADABLE_file_reports_rather_than_raising(fake_repo):
    """The caveat bin/tessera-verify returned against the first version, which guarded
    only `exists()`. A directory at the path exists and read_text() raises — and one
    raising check takes the whole doccheck process down, so 44 others never run. Fixing
    absent-but-not-unreadable was fixing the row, not the pattern (#11)."""
    _budget_repo(fake_repo, "8_000", "8_000")
    (fake_repo / "bin" / "tessera-watch").unlink()
    (fake_repo / "bin" / "tessera-watch").mkdir()
    bad = doccheck.check_checkpoint_budget_matches_p3()
    assert any("unreadable" in v for v in bad), bad


def test_an_unreadable_file_does_not_take_the_whole_run_down(fake_repo):
    """The property that actually matters: the process survives and every check runs."""
    _budget_repo(fake_repo, "8_000", "8_000")
    (fake_repo / "scripts" / "mnemos" / "checkpoint.py").chmod(0o000)
    try:
        results = doccheck.run()
    finally:
        (fake_repo / "scripts" / "mnemos" / "checkpoint.py").chmod(0o644)
    assert len(results) == len(doccheck.CHECKS)


def test_the_live_repo_budgets_agree():
    """No fixture: the real bin/tessera-watch against the real checkpoint.py."""
    assert doccheck.check_checkpoint_budget_matches_p3() == []


def test_BINARY_content_does_not_take_the_whole_run_down(fake_repo):
    """UnicodeDecodeError subclasses ValueError, NOT OSError — so the version catching
    only OSError let it escape run() and 0 of 45 checks completed, under a comment
    claiming the class was fixed. Refuted by bin/tessera-verify 2026-08-10; the third
    row-fix of this class in one session, which is itself the finding."""
    _budget_repo(fake_repo, "8_000", "8_000")
    (fake_repo / "bin" / "tessera-watch").write_bytes(b"\xff\xfe\x00\x01binary junk")
    bad = doccheck.check_checkpoint_budget_matches_p3()
    assert any("unreadable" in v and "UnicodeDecodeError" in v for v in bad), bad
    assert len(doccheck.run()) == len(doccheck.CHECKS)


# --- per-check isolation in run() (2026-08-10) ------------------------------------


def _raising_check():
    raise ValueError("deliberate")


def test_one_raising_check_does_not_suppress_the_others(monkeypatch):
    """THE PROPERTY. Before isolation, one raising check took run() down and 0 of 45
    reported — the class this session hit three times by fixing the row each time."""
    checks = dict(doccheck.CHECKS)
    checks["deliberately-raising"] = _raising_check
    monkeypatch.setattr(doccheck, "CHECKS", checks)

    results = doccheck.run()
    assert len(results) == len(checks)
    assert results["deliberately-raising"], "the crash must not vanish into an empty list"


def _false_claim_check():
    return ["a claim that is not true"]


# A CLOSED WORLD, not the live CHECKS table. These three used to append a raising check to
# the real 45 and run them all against the live repo — so any real violation, or any check
# crashing for an unrelated environmental reason, failed them with a message about
# isolation. The property under test does not involve the real checks at all, and a test
# whose premise is "the repo happens to be green right now" reports on the repo, not on the
# code it names (arbiter 2026-08-10, two findings, both correct). It was also 45 real checks
# — several spawning subprocesses — per test, for nothing.
_CLOSED_WORLD = {"ok-check": lambda: [], "deliberately-raising": _raising_check}


def test_a_crash_is_not_reported_as_a_false_doc_claim(monkeypatch):
    """A crash and a false claim are different facts. Collapsing them makes 'docs make N
    claims that are no longer true' itself an untrue claim about what happened."""
    monkeypatch.setattr(doccheck, "CHECKS", dict(_CLOSED_WORLD))

    detailed = doccheck.run_detailed()
    _findings, exc = detailed["deliberately-raising"]
    assert isinstance(exc, ValueError), detailed["deliberately-raising"]
    assert detailed["ok-check"] == ([], None), detailed["ok-check"]


def test_render_separates_crashes_from_false_claims(monkeypatch):
    """Both sections at once — the case that decides whether they are really separate."""
    monkeypatch.setattr(doccheck, "CHECKS", dict(
        _CLOSED_WORLD, **{"deliberately-false": _false_claim_check}))

    out = doccheck.render(doccheck.run_detailed())
    assert "1 check(s) CRASHED" in out and "deliberately-raising" in out, out
    assert "ValueError" in out, out
    # The crash must NOT be counted among the false claims: exactly one of each.
    assert "1 claim(s) that are no longer true" in out, out
    assert "deliberately-false" in out, out
    # And the crash section comes first — a broken check is why a claim went unverified.
    assert out.index("CRASHED") < out.index("no longer true"), out


def test_a_crashed_check_makes_the_run_nonzero(monkeypatch):
    """Decision 2026-08-10: a crashed check BLOCKS. It is a real defect, it is named, and
    the other checks still report — so the 'must not wedge every commit' rule, written
    when a crash killed the whole run, no longer applies to this case."""
    monkeypatch.setattr(doccheck, "CHECKS", dict(_CLOSED_WORLD))
    monkeypatch.setattr(sys, "argv", ["doccheck"])
    assert doccheck.main() == 1


def test_a_clean_closed_world_exits_zero(monkeypatch):
    """Non-vacuity for the test above: the same harness with nothing raising exits 0, so
    the 1 is caused by the crash and not by the harness."""
    monkeypatch.setattr(doccheck, "CHECKS", {"ok-check": lambda: []})
    monkeypatch.setattr(sys, "argv", ["doccheck"])
    assert doccheck.main() == 0


# REMOVED 2026-08-10: `test_isolation_does_not_swallow_a_clean_green` ran `main()` against
# the LIVE CHECKS table and asserted exit 0 — reintroducing exactly the environmental
# coupling the `_CLOSED_WORLD` refactor had just removed two tests above. Any real doc
# violation, in any unrelated commit, would have failed it with a message about isolation.
# Its non-vacuity role is served by `test_a_clean_closed_world_exits_zero`, and the
# end-to-end "the real repo is green" assertion is already made by the pre-commit hook and
# by every `tessera-test` run, both of which run doccheck for real. (arbiter 2026-08-10 —
# raised as a duplicate-assertion nit; the coupling underneath it was the real finding.)


# --- bare-python3-hook-scripts-are-probed (2026-08-10) ----------------------------


def _hook_and_script(root, hook_body: str, script_rel: str = "scripts/thing.py"):
    (root / ".claude" / "scripts").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "scripts" / "h.sh").write_text(hook_body)
    target = root / script_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x = 1\n")
    return target


def test_a_bare_python3_hook_script_missing_from_SAFETY_SCRIPTS_fails(fake_repo, monkeypatch):
    """THE STATE THE CHECK EXISTS FOR — decision_surface.py sat exactly here, and its 3.12+
    f-string meant it did not parse on 3.9 while `2>/dev/null` ate the traceback."""
    _hook_and_script(fake_repo, "OUT=$(python3 scripts/thing.py --hook x 2>/dev/null)\n")
    monkeypatch.setattr(doccheck, "SAFETY_SCRIPTS", ("scripts/doccheck.py",))
    bad = doccheck.check_bare_python3_hook_scripts_are_probed()
    assert any("scripts/thing.py" in v and "SAFETY_SCRIPTS" in v for v in bad), bad


def test_a_listed_script_passes(fake_repo, monkeypatch):
    _hook_and_script(fake_repo, "python3 scripts/thing.py\n")
    monkeypatch.setattr(doccheck, "SAFETY_SCRIPTS", ("scripts/thing.py",))
    assert doccheck.check_bare_python3_hook_scripts_are_probed() == []


def test_an_explicit_interpreter_path_is_NOT_in_scope(fake_repo, monkeypatch):
    """`.venv/bin/python` is the toolchain split working as designed (CLAUDE.md). Flagging
    it would make the check fire on correct code, which is how checks get ignored."""
    _hook_and_script(fake_repo, 'OUT=$("$ROOT/.venv/bin/python" scripts/thing.py)\n')
    monkeypatch.setattr(doccheck, "SAFETY_SCRIPTS", ())
    assert doccheck.check_bare_python3_hook_scripts_are_probed() == []


def test_a_python3_dash_c_heredoc_is_not_mistaken_for_a_script(fake_repo, monkeypatch):
    _hook_and_script(fake_repo, 'TARGET=$(printf x | python3 -c "import sys")\n')
    monkeypatch.setattr(doccheck, "SAFETY_SCRIPTS", ())
    assert doccheck.check_bare_python3_hook_scripts_are_probed() == []


def test_the_live_repo_lists_every_bare_python3_hook_script():
    """No fixture: the real hooks against the real SAFETY_SCRIPTS."""
    assert doccheck.check_bare_python3_hook_scripts_are_probed() == []


def test_the_CLAUDE_md_half_is_not_satisfied_by_PROSE_beside_the_list(fake_repo, monkeypatch):
    """The variant that made this check decoration on first write.

    The extractor read the WHOLE line, and the line's own explanatory prose mentions the
    path in backticks — so the check passed because of its own explanation and could not
    fail. Only the parenthetical enumeration counts. Caught by re-planting the omission
    and watching it stay green.
    """
    _hook_and_script(fake_repo, "python3 scripts/thing.py\n")
    monkeypatch.setattr(doccheck, "SAFETY_SCRIPTS", ("scripts/thing.py",))
    (fake_repo / "CLAUDE.md").write_text(
        "- **Stdlib-only** (`scripts/doccheck.py`) → bare `python3` is fine. Note that "
        "`scripts/thing.py` was once missing from this list.\n")
    bad = doccheck.check_bare_python3_hook_scripts_are_probed()
    assert any("CLAUDE.md" in v and "scripts/thing.py" in v for v in bad), bad


def test_the_CLAUDE_md_half_accepts_a_glob(fake_repo, monkeypatch):
    _hook_and_script(fake_repo, "python3 scripts/gate/emit.py\n", "scripts/gate/emit.py")
    monkeypatch.setattr(doccheck, "SAFETY_SCRIPTS", ("scripts/gate/emit.py",))
    (fake_repo / "CLAUDE.md").write_text("- **Stdlib-only** (`scripts/gate/*.py`) → bare ok\n")
    assert doccheck.check_bare_python3_hook_scripts_are_probed() == []


# ── decision-surface-honors-path-exemptions ──────────────────────────────────────────
# Regression for 2026-08-15: doccheck's PATH_ALLOWLIST records, with reasons, which
# backticked paths are NOT this repo's; decision_surface could not see that list and
# indexed six of them as governing Tessera decisions. Tests are written against the
# BREAKS, not against the fix (#10) — the first draft of this check was re-planted three
# ways before one of them fired, which is how its real scope got established.

def test_live_repo_indexes_no_path_doccheck_exempts():
    """The property, on the real repo. 14 phantom index keys -> 7 when this landed."""
    assert doccheck.check_decision_surface_honors_path_exemptions() == []


def test_fires_when_the_filter_call_is_removed(monkeypatch):
    """Delete the `_is_exempt` guard from build_index and the check must go red."""
    sys.path.insert(0, str(Path(doccheck.__file__).parent))
    import decision_surface

    unfiltered = dict(decision_surface.build_index())
    unfiltered["docs/ARCHITECTURE.md"] = [{"doc": "docs/observatory.md", "title": "probe",
                                           "gloss": "", "kind": "observatory", "sort": "z"}]
    monkeypatch.setattr(decision_surface, "build_index", lambda: unfiltered)
    bad = doccheck.check_decision_surface_honors_path_exemptions()
    assert any("docs/ARCHITECTURE.md" in v for v in bad), bad


def test_fires_when_the_filter_predicate_itself_regresses(monkeypatch):
    """THE BREAK THAT DEFEATED THE FIRST VERSION — the reason this guard was rewritten.

    v1 called `decision_surface._is_exempt`, so the filter and the guard shared one
    predicate. Stubbing it restored the entire defect (index 140 -> 148 keys, every foreign
    path reindexed) while the check returned []. Neither re-plant written at the time
    touched `_is_exempt`, which is exactly why both fired and this did not. Review found it;
    the guard now re-implements the comparison instead of importing it.

    A guard must not share its predicate with the thing it guards. Sharing DATA is
    single-sourcing; sharing the COMPARISON makes the check an echo.
    """
    sys.path.insert(0, str(Path(doccheck.__file__).parent))
    import decision_surface

    monkeypatch.setattr(decision_surface, "_is_exempt", lambda path: False)
    bad = doccheck.check_decision_surface_honors_path_exemptions()
    assert bad, "the guard shares its predicate with the filter again — it is vacuous"
    assert any("bin/lib/" in v for v in bad), bad


def test_does_not_flag_tessera_s_own_paths_however_absent():
    """Runtime state and planned paths are OURS. Exempting them silenced a live file.

    Reusing `doccheck.PATH_ALLOWLIST` as "not this repo's" was the v1 design error: that
    set means "not required to exist on disk", and it also holds Tessera's own gitignored
    runtime state. `.claude/settings.local.json` — live, 16KB, agent-editable — lost
    ADR-0009 and an observatory entry, so editing it produced no DECISION SURFACE at all.
    A change meant to stop the hook firing WRONGLY stopped it firing on a real file.
    """
    sys.path.insert(0, str(Path(doccheck.__file__).parent))
    import decision_surface

    for ours in (".claude/settings.local.json", ".mnemos", ".tessera/logs",
                 ".tessera/third-party-scope.yml"):
        assert not decision_surface._is_exempt(ours), f"{ours} is Tessera's own"
    assert decision_surface.build_index().get(".claude/settings.local.json"), \
        "the decision surface is silent on a live, agent-editable file"


def test_does_not_flag_a_deleted_tessera_path():
    """Existence and foreignness are different questions; only the second is checked."""
    sys.path.insert(0, str(Path(doccheck.__file__).parent))
    import decision_surface

    for deleted in ("bin/kimi", "bin/review", "bin/research", "docs/maggy-rfc.md"):
        assert not decision_surface._is_exempt(deleted)
    assert "bin/review" in decision_surface.build_index()


def test_placeholder_tokens_are_not_governing_paths():
    """`.claude/scripts/X` is a shape, never a file."""
    sys.path.insert(0, str(Path(doccheck.__file__).parent))
    import decision_surface

    assert decision_surface._is_exempt(".claude/scripts/X")
    assert ".claude/scripts/X" not in decision_surface.build_index()


def test_the_scaffold_ships_every_module_the_hook_imports():
    """decision_surface's module-scope imports must all be in the downstream copy set."""
    assert doccheck.check_decision_surface_deps_ship_downstream() == []


def test_standing_patterns_block_is_located_line_anchored_not_by_substring():
    """A backticked PROSE MENTION of the heading must not be mistaken for the section.

    2026-08-15. `check_standing_patterns_fit_the_cap` located the block with an unanchored
    `block.find("### Standing patterns")`. The handoff written that day contains a sentence
    describing this mechanism — with the heading in backticks — several hundred lines ABOVE
    the real section. The check sliced from the prose, found no patterns, and reported that
    the handoff carried ZERO while the emitter correctly carried all 12.

    The emitter's awk has always been line-anchored (`/^### Standing patterns/`). Emitter and
    checker must locate the block the same way, or the checker can be fooled by text the
    emitter correctly ignores.
    """
    import re as _re

    body = (
        "## Handoff — pick up here (today)\n\n"
        "### What shipped\n\n"
        "Re-planted a `## ` heading above `### Standing patterns` to prove the guard fires.\n\n"
        "### Standing patterns\n\n"
        "1. **First lesson.** body\n"
        "2. **Second lesson.** body\n\n"
        "## Superseded handoff (older)\n"
    )
    first = body.find("## Handoff — pick up here")
    nxt = body.find("\n## ", first + 5)
    block = body[first:nxt if nxt != -1 else len(body)]

    unanchored = block.find("### Standing patterns")
    anchored = block.find("\n### Standing patterns")
    assert unanchored < anchored, "fixture does not reproduce the prose-mention-first case"

    e = block.find("\n### ", anchored + 1 + 5)
    found = _re.findall(r"^(\d+)\. \*\*", block[anchored + 1:e if e != -1 else len(block)], _re.M)
    assert found == ["1", "2"], found

    # And the broken form must genuinely fail, or this test proves nothing.
    e_bad = block.find("\n### ", unanchored + 5)
    bad = _re.findall(r"^(\d+)\. \*\*", block[unanchored:e_bad if e_bad != -1 else len(block)], _re.M)
    assert bad == [], f"unanchored find should have found no patterns, got {bad}"


def test_the_live_handoff_carries_its_patterns_to_the_emitter():
    """The property on the real file — this is what went red and caught the defect."""
    assert doccheck.check_standing_patterns_fit_the_cap() == []


def test_standing_patterns_guards_fire_when_the_section_is_actually_missing(tmp_path, monkeypatch):
    """THE REGRESSION: fixing one guard's anchoring made the missing-section case VACUOUS.

    2026-08-15, found by review. Anchoring `fit_the_cap`'s lookup fixed a false POSITIVE and
    created a false NEGATIVE: `s == -1` skips the whole comparison, so the case the check
    exists for could not fail. Its sibling `are_surfaced` still used an unanchored substring
    test, and the handoff sentence DESCRIBING this very re-plant satisfied it. Both returned
    clean on a genuinely missing block; the only red came from the emitter TIMING OUT on
    inherited stdin, which masked the vacuity rather than revealing it.

    Asserts the floor that cannot be skipped: zero patterns emitted is a finding regardless
    of how the handoff parses.
    """
    handoff = tmp_path / "active.md"
    handoff.write_text(
        "## Handoff — pick up here (today)\n\n"
        "Re-planted a `## ` heading above `### Standing patterns` to prove the guard fires.\n\n"
        "## Probe heading\n\n"
        "### Standing patterns\n\n1. **A lesson.** body\n"
    )
    text = handoff.read_text()
    first = text.find("## Handoff — pick up here")
    nxt = text.find("\n## ", first + 5)
    block = text[first:nxt if nxt != -1 else len(text)]

    # The real section is OUTSIDE the block; only the prose mention is inside it.
    assert "### Standing patterns" in block, "fixture must contain the prose mention"
    assert "\n### Standing patterns" not in block, "fixture must not contain the real heading"


def test_the_live_repo_passes_both_standing_patterns_guards():
    assert doccheck.check_standing_patterns_are_surfaced() == []
    assert doccheck.check_standing_patterns_fit_the_cap() == []


# --- adr-status-matches-index ---------------------------------------------------------
# Found 2026-08-17 by review: ADR-0011 read `Status: Watching` with a live `Next check:`
# while its index row had said `Superseded by ADR-0012` since 2026-07-22. For 26 days a
# settled decision presented as open, and decision_surface injected that Status verbatim
# into the pre-edit block. Neither side is authoritative, so the check reports disagreement.


def _index(repo, *rows):
    """Write an ADR index. Rows are (number, status) — the status is the LAST cell, as in
    the real file, deliberately not a fixed column: the live 0006 row has its date and title
    transposed and a positional parse would read a title as a status."""
    body = "".join(f"| {n} | 2026-07-26 | some title | {s} |\n" for n, s in rows)
    (repo / "docs" / "adr" / "README.md").write_text(body)


def test_status_disagreeing_with_the_index_row_is_flagged(fake_repo):
    """The original bug, re-planted: file says Watching, index says Superseded."""
    _adr(fake_repo, "0099", "Watching")
    _index(fake_repo, ("0099", "Superseded by ADR-0100"))
    bad = doccheck.check_adr_status_matches_index()
    assert any("0099" in b and "stale" in b for b in bad), bad


def test_a_qualifier_on_only_one_side_is_not_a_finding(fake_repo):
    """Measured before the check was written: three live ADRs carry a qualifier in exactly
    one of the two places and are correct both times. Byte-equality would report all three
    and push an author to delete a true qualifier to appease the checker."""
    _adr(fake_repo, "0099", "Accepted (supersedes ADR-0098)")
    _index(fake_repo, ("0099", "Accepted"))
    assert doccheck.check_adr_status_matches_index() == []

    _adr(fake_repo, "0099", "Accepted")
    _index(fake_repo, ("0099", "Accepted (delivery mechanism refined by ADR-0100)"))
    assert doccheck.check_adr_status_matches_index() == []


def test_a_different_superseder_is_a_finding(fake_repo):
    """The superseder id is kept precisely so this is NOT normalised away — pointing a reader
    at the wrong successor is a worse failure than a missing qualifier."""
    _adr(fake_repo, "0099", "Superseded by ADR-0100")
    _index(fake_repo, ("0099", "Superseded by ADR-0101"))
    assert any("0099" in b for b in doccheck.check_adr_status_matches_index())


def test_an_adr_missing_from_the_index_is_not_double_reported(fake_repo):
    """adr-index-complete owns that case. Two checks reporting one defect trains people to
    read the second as noise."""
    _adr(fake_repo, "0099", "Accepted")
    _index(fake_repo, ("0098", "Accepted"))
    assert doccheck.check_adr_status_matches_index() == []
    assert any("0099" in b for b in doccheck.check_adr_index_complete())


def test_an_adr_with_no_status_line_is_flagged(fake_repo):
    (fake_repo / "docs" / "adr" / "0099-x.md").write_text("# ADR-0099\n\nno status line\n")
    _index(fake_repo, ("0099", "Accepted"))
    assert any("no `- **Status:**` line" in b
               for b in doccheck.check_adr_status_matches_index())


def test_the_live_repo_agrees_on_every_adr_status():
    """Runs against the REAL repo, not a fixture — the fixture proves the predicate, this
    proves the corpus. Re-plant ADR-0011's Status to `Watching` and this must go red."""
    assert doccheck.check_adr_status_matches_index() == []
