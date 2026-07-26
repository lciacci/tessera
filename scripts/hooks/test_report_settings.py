"""report_settings: the fixer, its scope, and the guarantee that its detector agrees with it.

The load-bearing test here is `test_fixer_output_is_clean_under_the_detector`. A fixer and a
detector that disagree is the failure this repo keeps rediscovering — one flags what the other
cannot fix, so `doccheck` stays red forever or, worse, goes green on unfixed input. The sibling
anchoring pair needs a lockstep test because it mirrors a regex; this pair shares one predicate
outright, and this test is what proves the sharing actually holds end to end.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_settings  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
P = '${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/tessera-gate-scan.sh'
LOCAL_ONLY = f'if [ -x "{P}" ]; then exec "{P}"; fi; exit 0'
WITH_FALLBACK = (
    f'if [ -x "{P}" ]; then exec "{P}"; '
    f'elif [ -x "$HOME/.claude/templates/tessera-gate-scan.sh" ]; then '
    f'exec "$HOME/.claude/templates/tessera-gate-scan.sh"; fi; exit 0'
)
UNANCHORED = ('if [ -x ".claude/scripts/tessera-gate-scan.sh" ]; then '
              'exec ".claude/scripts/tessera-gate-scan.sh"; fi; exit 0')


def test_local_only_command_gains_a_reporting_branch():
    out = report_settings.report_command(LOCAL_ONLY)
    assert out is not None
    assert "tessera-degraded" in out
    assert "--component gate-scan" in out
    assert "--reason hook-unavailable" in out
    assert out.rstrip().endswith("exit 0"), "must still fail open"
    assert out.startswith(f'if [ -x "{P}" ]; then exec "{P}"; fi;'), \
        "the working path must be untouched — this only adds an else-branch"


def test_is_idempotent():
    once = report_settings.report_command(LOCAL_ONLY)
    assert report_settings.report_command(once) is None, \
        "re-running must not stack a second branch"


def test_global_fallback_command_is_out_of_scope():
    """ADR-0004: a missing local file resolves through the global copy, so the hook still runs."""
    assert report_settings.report_command(WITH_FALLBACK) is None


def test_unanchored_command_is_skipped():
    """Reporting on a cwd-relative path would name the wrong file. Anchor first."""
    assert report_settings.report_command(UNANCHORED) is None


def test_unrecognised_shape_is_left_alone():
    assert report_settings.report_command('echo hi && something-else') is None


def test_component_is_derived_not_looked_up():
    assert report_settings.component_of("tessera-spend-backstop.sh") == "spend-backstop"
    assert report_settings.component_of("tessera-gate-scan.sh") == "gate-scan"


def test_fixer_output_is_clean_under_the_detector():
    """THE CONSISTENCY GUARD. Whatever the fixer emits, the detector must call clean."""
    fixed = report_settings.report_command(LOCAL_ONLY)
    assert report_settings.needs_reporting(fixed) is None, \
        "detector still flags the fixer's own output — they disagree"


def test_detector_is_not_vacuous_on_the_real_repo():
    """doccheck reporting 0 findings must mean 'clean', not 'looked at nothing'.

    Feeds the real settings.json back through the predicate with the reporting branch stripped
    from every command. If the check were vacuous — wrong key, wrong shape, no local-only hooks
    — nothing would be flagged and its green would be meaningless.
    """
    data = json.loads((REPO / ".claude" / "settings.json").read_text())
    stripped = 0
    for groups in (data.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if "tessera-degraded" not in cmd:
                    continue
                head = cmd.split("; for d in bin scripts;")[0]
                if report_settings.needs_reporting(head + "; exit 0"):
                    stripped += 1
    assert stripped >= 1, (
        "no command in the real settings.json is in scope for this rule — the check would be "
        "vacuously green. Either the wiring changed shape or the predicate no longer matches it.")


def test_no_local_only_hook_silently_escapes_scope():
    """SCOPE COMPLETENESS — the hole the not-vacuous test could not see.

    `test_detector_is_not_vacuous_on_the_real_repo` only samples commands that ALREADY contain
    tessera-degraded, so it proves the predicate matches *something*, never that it matches
    *everything in scope*. A scope hole is invisible to it by construction, and one shipped:
    `_ANCHORED` required `/.claude/scripts/`, while .claude/settings.json also wires local-only
    hooks under `hooks/` (subagent-route-hook, tier-classify-hook). Both fixer and detector
    skipped them — and because doccheck imports this predicate, the check read green while two
    wired hooks stayed in the pre-spec-11 fail-silent state. Found by cloud review, not by us.

    This asserts the docstring's actual claim: EVERY local-only, anchored, exit-0 wired command
    is in scope. The candidate regex here is deliberately BROADER than the production one and
    written independently — a test that reuses `_ANCHORED` could never detect `_ANCHORED` being
    too narrow.
    """
    import re
    broad = re.compile(r'"\$\{CLAUDE_PROJECT_DIR:-\.\}/([A-Za-z0-9._/-]+)"')
    data = json.loads((REPO / ".claude" / "settings.json").read_text())
    escaped = []
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if "tessera-degraded" in cmd:
                    continue                                  # already reports
                if report_settings.GLOBAL_FALLBACK in cmd:
                    continue                                  # not local-only
                if not cmd.rstrip().endswith("exit 0"):
                    continue                                  # unrecognised shape
                if not broad.search(cmd):
                    continue                                  # not an anchored hook path
                if report_settings.needs_reporting(cmd) is None:
                    escaped.append(f"{event}: {broad.search(cmd).group(1)}")
    assert not escaped, (
        "local-only anchored hook(s) silently out of scope — the fixer cannot fix them AND "
        "doccheck cannot flag them, so they stay fail-silent while the check reads green: "
        + ", ".join(escaped))


def test_doccheck_registers_the_check():
    """The rule must be enforced by the pre-commit gate, not merely importable."""
    out = subprocess.run([sys.executable, str(REPO / "scripts" / "doccheck.py"), "--list"],
                         capture_output=True, text=True)
    listing = out.stdout + out.stderr
    if "unrunnable-hooks-report-themselves" not in listing:
        # --list may not exist; fall back to the registry source.
        listing = (REPO / "scripts" / "doccheck.py").read_text()
    assert "unrunnable-hooks-report-themselves" in listing


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
