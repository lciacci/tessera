"""Spec 11 chaos probes — break a component on purpose, assert Tessera says so.

THE BAR (spec 11, and it is binary):

    Break a component on purpose, and Tessera tells you within one session,
    without a human asking.

**Every probe here is expected to FAIL right now.** That is the point, and the ordering is
not style — it is the correction for how 2026-07-12 went wrong: that session built a
detector, then verified the fix *with the detector that had the hole*, three times, and
reported green each time. A detector you certify a fix with must be tested against that
fix's own failure mode, or it is a mirror, not an instrument.

So these run RED first, on purpose, via `bin/tessera-chaos` — deliberately NOT in
`tessera-test`, so the green/red signal of the main suite stays usable while these are
legitimately red. When `tessera-degraded` + `tessera-watch` P13 land, they go green and
get folded into `run-tests.sh`.

**Why this lives at top-level `chaos/` and not `scripts/chaos/`:** run-tests.sh's top-level
run is `pytest scripts/`, which would collect these and fail the main suite — the exact
outcome the separate-command choice existed to avoid. `--ignore=scripts/chaos` would then
collide with doccheck's `ignored-test-suites-are-run`, which requires every ignored suite to
be run somewhere in run-tests.sh and exists because a `test:` that skipped half the suite
once reported green all evening. Living outside `scripts/` needs no exclusion at all, so
neither check has to be weakened.

WHAT EACH PROBE DOES: scaffolds a REAL downstream with `tessera-new-project` (real hook
scripts, real settings.json, real stdin contract), breaks one thing, drives the hook the
way Claude Code drives it, and asserts a `degraded` event lands in the session log. Not a
hand-built model of the harness — standing pattern #9: a mechanism that RUNS has not
necessarily REACHED its audience, and only the real path proves the real path.

THE DISTINCTION EVERY PROBE TURNS ON (spec 11):
    "nothing to do"        → correct, silent exit. Leave alone.
    "I could not do my job" → DEGRADED. Must be loud.
Every bug on 2026-07-12 was the second kind, silently treated as the first.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCAFFOLD = REPO / "bin" / "tessera-new-project"
SESSION = "chaos-probe"

# A command the spend guard must block: external, irreversible, commitment (not teardown).
SPEND_CMD = "aws ec2 run-instances --instance-type p4d.24xlarge"
DENY = 2  # the ONLY exit code that blocks. 0 and 1 both allow the command through.


def _scaffold(target: Path, *flags: str) -> Path:
    out = subprocess.run([str(SCAFFOLD), *flags, str(target), "toy", "standard"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, f"scaffold failed:\n{out.stderr}"
    return target


@pytest.fixture
def toy(tmp_path):
    """A real scaffolded downstream. Not a fixture tree — the actual shipped harness."""
    return _scaffold(tmp_path / "toy")


@pytest.fixture
def frozen_toy(tmp_path):
    """`--frozen`: pins LOCAL mnemos hook copies (ADR-0004).

    The default `global` distribution ships none, so any probe touching a mnemos hook
    silently skips against `toy` — which is how component 4 went uncovered while the run
    still read as fine.
    """
    return _scaffold(tmp_path / "frozen-toy", "--frozen")


def hook_input(toy: Path, **extra) -> str:
    payload = {"session_id": SESSION, "cwd": str(toy), "stop_hook_active": False}
    payload.update(extra)
    return json.dumps(payload)


def run_hook(script: Path, stdin: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Invoke a hook the way Claude Code does: JSON on stdin, exit code is the verdict."""
    return subprocess.run([str(script)], input=stdin, capture_output=True, text=True,
                          timeout=60, env=env or dict(os.environ))


def run_wired(toy: Path, script_name: str, stdin: str) -> subprocess.CompletedProcess:
    """Invoke via the settings.json command string, NOT the script path.

    The wired form is `if [ -x "<path>" ]; then exec "<path>"; fi; exit 0` — so a
    non-executable or missing script is a SILENT exit 0. Calling the script directly
    would never exercise that branch, which is exactly the branch that failed.
    """
    path = toy / ".claude" / "scripts" / script_name
    cmd = f'if [ -x "{path}" ]; then exec "{path}"; fi; exit 0'
    return subprocess.run(["sh", "-c", cmd], input=stdin, capture_output=True,
                          text=True, timeout=60)


def degraded_events(toy: Path) -> list[dict]:
    """Every `degraded` event in the toy's session log. The signal that must exist."""
    log = toy / ".tessera" / "logs" / f"{SESSION}.jsonl"
    if not log.exists():
        return []
    out = []
    for line in log.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "degraded":
            out.append(event)
    return out


def assert_reported(toy: Path, what: str):
    """THE BAR. Fails today for every probe — no `degraded` channel exists yet."""
    events = degraded_events(toy)
    assert events, (
        f"SILENT FAILURE: {what}\n"
        f"    The component could not do its job and nothing recorded it. No `degraded` "
        f"event in {toy.name}/.tessera/logs/{SESSION}.jsonl, so nothing surfaces at "
        f"SessionStart and no watcher predicate can fire.\n"
        f"    This is spec 11's bar, unmet: breaking a component on purpose must tell you "
        f"within one session, without a human asking."
    )


# NOTE on hiding a tool from a probe: build a bin dir of symlinks to the tools the hook
# legitimately needs and point PATH at it (see probe 5). Do NOT use `PATH=/nonexistent` —
# that makes even `sh` unresolvable, so the probe measures its own broken setup instead of
# the hook's behaviour. It did exactly that once, returning 127 from `env: bash: not found`.


# ─────────────────────────────────────────────────────────────────────────────────────
# COMPONENT 1/5: spend guard — "unguarded GPU spend; this one already bit, and failed OPEN"
# ─────────────────────────────────────────────────────────────────────────────────────

def test_probe_1_corrupt_guard_allows_spend_silently(toy):
    """`corrupt scripts/spend/guard.py → does anything say so?`

    VERIFIED LIVE while writing this: the wrapper runs `python3 "$GUARD"` and ends with
    `exit $?`. A syntax error exits 1 — and 1 is not 2, so the spend is ALLOWED. The
    guard that exists to stop unauthorized GPU boots waves it through because it broke.
    """
    (toy / "scripts" / "spend" / "guard.py").write_text("this is not python(((\n")
    r = run_hook(toy / ".claude" / "scripts" / "tessera-spend-guard.sh",
                 hook_input(toy, tool_input={"command": SPEND_CMD}))
    assert r.returncode != DENY, "setup wrong — a corrupt guard should not still be denying"
    assert_reported(toy, "spend guard is corrupt; a spend-committing command was ALLOWED")


def test_probe_2_missing_guard_allows_spend_silently(toy):
    """Deleted guard, not corrupt: the wrapper's `[ -f "$GUARD" ] || exit 0`.

    Worse than the corrupt case — exit 0 with EMPTY stderr. Indistinguishable from
    "this command needed no guarding." This is the "nothing to do" / "could not do my
    job" confusion in its purest form.
    """
    (toy / "scripts" / "spend" / "guard.py").unlink()
    r = run_hook(toy / ".claude" / "scripts" / "tessera-spend-guard.sh",
                 hook_input(toy, tool_input={"command": SPEND_CMD}))
    assert r.returncode == 0 and r.stderr == "", "setup wrong — expected the silent bail-out"
    assert_reported(toy, "spend guard is MISSING; a spend-committing command was ALLOWED")


def test_probe_3_spend_guard_under_python_39_still_denies(toy):
    """Spec 11 success criterion 4 — the case that already failed open, on the REAL 3.9.

    `/usr/bin/python3` on this machine is genuinely 3.9.6, so this is not a stub. On
    2026-07-12 PEP-604 annotations (`str | None`) raised TypeError at definition time,
    guard.py exited 1, and the boot proceeded.

    **This probe PASSES today** — `from __future__ import annotations` fixed it and the
    fix holds. It is here as the regression guard for a bug that already cost real spend,
    NOT as evidence of the missing mechanism. Keeping a green probe among red ones is
    deliberate: criterion 4 says this case must be covered, and a suite that only proves
    what is broken cannot show when something un-breaks.
    """
    # cwd=toy is LOAD-BEARING, not tidiness. guard.py records the denial through
    # scripts/spend/event.py, whose `.tessera/logs` path is resolved against the PROCESS cwd.
    # The hook wrapper normally cds first; invoking guard.py directly (as this probe must, to
    # pin the interpreter) skips that. Without cwd=toy the probe wrote seven synthetic
    # `spend_denied` events into the REAL session log — fixtures indistinguishable from live
    # denials, which the Stop-hook spend backstop then demanded a disposition for.
    r = subprocess.run(["/usr/bin/python3", str(toy / "scripts" / "spend" / "guard.py")],
                       input=json.dumps({"tool_input": {"command": SPEND_CMD},
                                         "cwd": str(toy)}),
                       cwd=str(toy),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == DENY, (
        f"REGRESSION: the spend guard failed OPEN under python 3.9 (rc={r.returncode}). "
        f"This is the 2026-07-12 bug returning. Check `from __future__ import annotations` "
        f"is still the first import in guard.py.\n{r.stderr}"
    )


# ─────────────────────────────────────────────────────────────────────────────────────
# COMPONENT 2/5: spend backstop — "denials vanish undispositioned; the net never fires"
# ─────────────────────────────────────────────────────────────────────────────────────

def test_probe_4_unexecutable_backstop_hook_is_silent(toy):
    """`chmod -x a hook script → does anything say so?`

    Driven through the WIRED command form, because that is where the hole is:
    `if [ -x "<path>" ]; then exec ...; fi; exit 0`. Strip the bit and the hook is
    skipped with exit 0 and no output — identical, from outside, to a hook that ran and
    found nothing to report. `[ -x ]` cannot tell "not executable" from "not there", and
    on 2026-07-24 that same predicate reported a wrong-cwd as "missing or not executable".
    """
    hook = toy / ".claude" / "scripts" / "tessera-spend-backstop.sh"
    hook.chmod(0o644)
    r = run_wired(toy, "tessera-spend-backstop.sh", hook_input(toy))
    assert r.returncode == 0 and r.stdout == "", "setup wrong — expected the silent skip"
    assert_reported(toy, "the spend backstop hook is not executable and was skipped entirely")


# ─────────────────────────────────────────────────────────────────────────────────────
# COMPONENT 3/5: gate-scan — "gates go unlogged; the calibration corpus silently truncates"
# ─────────────────────────────────────────────────────────────────────────────────────

def test_probe_5_gate_scan_without_jq_is_silent(toy, tmp_path):
    """`remove jq from PATH → does anything say so?`

    `command -v jq >/dev/null 2>&1 || exit 0`. Every field the hook needs comes out of jq,
    so without it the scan cannot run at all — the definition of "could not do my job" —
    and it exits 0. The gate corpus silently stops growing; nothing distinguishes that
    from a session in which no gate was missed.
    """
    binless = tmp_path / "nojq"
    binless.mkdir()
    for tool in ("sh", "bash", "python3", "cat", "printf", "dirname"):
        found = shutil.which(tool)
        if found:
            (binless / tool).symlink_to(found)
    env = dict(os.environ, PATH=str(binless))

    transcript = tmp_path / "t.jsonl"
    transcript.write_text("")
    r = run_hook(toy / ".claude" / "scripts" / "tessera-gate-scan.sh",
                 hook_input(toy, transcript_path=str(transcript)), env=env)
    assert r.returncode == 0, "setup wrong — expected the silent jq bail-out"
    assert_reported(toy, "jq is unavailable, so gate-scan could not scan anything")


def test_probe_6_gate_scan_with_missing_scanner_is_silent(toy, tmp_path):
    """`[ -f "$SCAN" ] || exit 0` — the backstop's own payload deleted.

    The Stop-hook backstop exists because the gate recorder rides model recall and
    under-logs ~85%. Delete scan.py and the backstop for that becomes a no-op, silently:
    the framework loses its only defence against the failure it already measured.
    """
    (toy / "scripts" / "gate" / "scan.py").unlink()
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("")
    r = run_hook(toy / ".claude" / "scripts" / "tessera-gate-scan.sh",
                 hook_input(toy, transcript_path=str(transcript)))
    assert r.returncode == 0 and r.stderr == "", "setup wrong — expected the silent bail-out"
    assert_reported(toy, "gate-scan's scan.py is missing; the Stop-hook backstop is a no-op")


# ─────────────────────────────────────────────────────────────────────────────────────
# COMPONENT 4/5: Mnemos hooks — "checkpoints lost, or written through the wrong interpreter"
# ─────────────────────────────────────────────────────────────────────────────────────

def test_probe_7_toolchain_unreachable_is_silent(frozen_toy, tmp_path):
    """`rm -rf .venv → does anything say so?` — F-001's exact shape, reproduced.

    F-001 is the origin story: hooks reached Mnemos through a bare `python3`, the import
    silently failed, every checkpoint write no-op'd for WEEKS, and it confounded the whole
    Mnemos trial — "the graph is empty" read as *unused* when it meant *unreachable*.

    Scaffolded `--frozen` on purpose. The default `global` distribution ships NO local
    mnemos scripts, so this probe skipped — and a silently-skipped probe in a fail-open
    suite is the very bug the suite exists to find. Component 4 of 5 was uncovered and the
    run still looked fine.

    What is actually broken here: no `.venv/bin/mnemos`, and no `mnemos` on PATH. The hook
    then falls through to an inline `python3` block that writes a checkpoint ANYWAY. So the
    degraded path *succeeds* — spec 11's own words, "the hook fallback silently succeeded
    on an unmanaged interpreter." Nothing anywhere says the real toolchain was unreachable.
    """
    hook = frozen_toy / ".claude" / "scripts" / "mnemos-stop-checkpoint.sh"
    assert hook.exists(), "setup wrong — --frozen must ship local mnemos hooks"

    binless = tmp_path / "nomnemos"
    binless.mkdir()
    for tool in ("sh", "bash", "python3", "cat", "printf", "dirname", "date", "jq"):
        found = shutil.which(tool)
        if found:
            (binless / tool).symlink_to(found)
    env = dict(os.environ, PATH=str(binless))

    r = run_hook(hook, hook_input(frozen_toy), env=env)
    assert r.returncode == 0, "setup wrong — expected the silent fallback path"
    assert_reported(frozen_toy,
                    "mnemos is unreachable; the checkpoint took an unmanaged fallback path")


# ─────────────────────────────────────────────────────────────────────────────────────
# COMPONENT 5/5: doccheck / pre-commit — "lying commits land"
# ─────────────────────────────────────────────────────────────────────────────────────

def test_probe_8_typo_in_a_wired_hook_path_is_silent(toy):
    """`typo a hook path in settings.json → does anything say so?`

    It didn't, on tess-dashboard, for WEEKS. The wired form swallows a typo'd path as
    exit 0 — a hook that has never once run is indistinguishable from a hook with nothing
    to say. Nothing reconciles settings.json's referenced paths against what is on disk
    at RUN time (doccheck checks this repo's own settings, which is not the same claim as
    "the hook that just fired actually existed").
    """
    settings = toy / ".claude" / "settings.json"
    data = json.loads(settings.read_text())
    typoed = 0
    for groups in (data.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                if "tessera-gate-scan.sh" in hook.get("command", ""):
                    hook["command"] = hook["command"].replace("tessera-gate-scan.sh",
                                                              "tessera-gate-scn.sh")
                    typoed += 1
    assert typoed, "setup wrong — gate-scan is not wired in the scaffold"
    settings.write_text(json.dumps(data, indent=2))

    r = run_wired(toy, "tessera-gate-scn.sh", hook_input(toy))
    assert r.returncode == 0 and r.stdout == "", "setup wrong — expected the silent skip"
    assert_reported(toy, "a wired hook path is typo'd, so the hook has never run")
