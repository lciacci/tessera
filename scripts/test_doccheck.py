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
