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
    """Invoke the command string the project ACTUALLY ships, read from its settings.json.

    The wired form is `if [ -x "<path>" ]; then exec "<path>"; fi; exit 0` — so a
    non-executable or missing script is a SILENT exit 0. Calling the script directly
    would never exercise that branch, which is exactly the branch that failed.

    CORRECTED 2026-07-26. This used to SYNTHESIZE the command:

        cmd = f'if [ -x "{path}" ]; then exec "{path}"; fi; exit 0'

    which hardcoded the fail-open `exit 0` into the test itself. Probes 4 and 8 were
    therefore asserting against a hand-built replica of the wired form, and no change to
    the shipped settings.json could ever turn them green — probe 8 even edited
    settings.json and then never read it back. That is this file's own docstring
    violated (pattern #9: only the real path proves the real path), one layer in from
    where it was being enforced. The replica also diverged in shape: the real command
    resolves `${CLAUDE_PROJECT_DIR:-.}`, the replica used an absolute path.

    Now: find the hook command that references `script_name` and run THAT, with
    CLAUDE_PROJECT_DIR pointed at the project the way Claude Code sets it.
    """
    # An empty script_name would substring-match EVERY command below and silently run the
    # wrong hook, turning the not-vacuous guard into a tautology (criterion-5 re-read).
    assert script_name, "run_wired needs a script name; an empty one matches every command"
    settings = json.loads((toy / ".claude" / "settings.json").read_text())
    commands = [hook.get("command", "")
                for groups in (settings.get("hooks") or {}).values()
                for group in groups
                for hook in group.get("hooks", [])
                if script_name in hook.get("command", "")]
    assert commands, (
        f"setup wrong — no wired command in settings.json references {script_name}; "
        f"the probe would be testing nothing")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(toy))
    return subprocess.run(["sh", "-c", commands[0]], input=stdin, capture_output=True,
                          text=True, timeout=60, env=env, cwd=str(toy))


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


def assert_reported(toy: Path, what: str, component: str):
    """THE BAR: the broken component reported ITSELF, not merely that something spoke.

    `component` is REQUIRED (added 2026-07-26, criterion-5 re-read). This used to assert only
    that *some* degraded event existed, which meant a probe could pass on an event emitted by an
    unrelated component — a green that proves the channel works, not that the thing we broke
    said so. Every probe breaks exactly one component, so every probe can name it.
    """
    events = degraded_events(toy)
    assert events, (
        f"SILENT FAILURE: {what}\n"
        f"    The component could not do its job and nothing recorded it. No `degraded` "
        f"event in {toy.name}/.tessera/logs/{SESSION}.jsonl, so nothing surfaces at "
        f"SessionStart and no watcher predicate can fire.\n"
        f"    This is spec 11's bar, unmet: breaking a component on purpose must tell you "
        f"within one session, without a human asking."
    )
    got = [e.get("data", {}).get("component") for e in events]
    assert component in got, (
        f"WRONG REPORTER: {what}\n"
        f"    Degraded events exist, but none from `{component}` — got {got}. The probe would "
        f"have passed on another component's event, which proves the channel is alive, not that "
        f"the component we broke said anything."
    )


# NOTE on hiding a tool from a probe: build a bin dir of symlinks to the tools the hook
# legitimately needs and point PATH at it (see probe 5). Do NOT use `PATH=/nonexistent` —
# that makes even `sh` unresolvable, so the probe measures its own broken setup instead of
# the hook's behaviour. It did exactly that once, returning 127 from `env: bash: not found`.

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
    assert_reported(toy, "jq is unavailable, so gate-scan could not scan anything", "gate-scan")


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
    assert_reported(toy, "gate-scan's scan.py is missing; the Stop-hook backstop is a no-op", "gate-scan")


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
                    "mnemos is unreachable; the checkpoint took an unmanaged fallback path", "mnemos-checkpoint")


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
    assert_reported(toy, "a wired hook path is typo'd, so the hook has never run", "gate-scan")


# ─────────────────────────────────────────────────────────────────────────────────────
# COMPONENT 6/6: the SessionStart surfacers — "the reporter's own runner is gone"
#
# Added by the A5b audit (2026-07-27). The settings.json trailing branch reports a hook
# SCRIPT that is missing or unexecutable — it cannot report a hook that ran perfectly and
# whose RUNNER is gone. Probed by hand first, and all three were silent: SessionStart
# printed a completely normal handoff while the observatory watcher did not exist.
# ─────────────────────────────────────────────────────────────────────────────────────

def _tessera_like(toy: Path, runner: str, hook: str) -> Path:
    """Give the toy the piece a DOWNSTREAM never has: a framework runner + its surfacer.

    Found while writing these probes, and it is the finding, not a fixture detail: no
    downstream has `bin/tessera-watch` or `bin/tessera-findings`, and none wires the
    surfacers — they are tessera-only hooks. A probe that just deleted the runner from a
    scaffolded downstream would have been asserting on something that was never there,
    which is the shape that let a probe skip and hide a whole component in the first run
    of this suite. So the baseline is established explicitly: install a working runner,
    prove the surfacer is QUIET, then break it.
    """
    (toy / "bin").mkdir(exist_ok=True)
    r = toy / "bin" / runner
    r.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")   # rc 0 = nothing fired
    r.chmod(0o755)
    dst = toy / ".claude" / "scripts" / hook
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text((REPO / ".claude" / "scripts" / hook).read_text())
    dst.chmod(0o755)
    return dst


def test_probe_9_watch_surfacer_with_no_watcher_is_silent(toy):
    """`rm bin/tessera-watch → does anything say so?`

    The worst instance in the repo, because tessera-watch IS the reporting mechanism for
    P3, P4, P9, P11, P12, P13, P14 and P15. Delete it and every predicate goes quiet at
    once — and the silence is indistinguishable from a clean session. The thing that would
    tell you is the thing that broke: standing pattern #1, in the watcher itself.
    """
    hook = _tessera_like(toy, "tessera-watch", "tessera-watch-surface.sh")
    assert not degraded_events(toy), "baseline wrong — a WORKING watcher must be silent"
    run_hook(hook, hook_input(toy))
    assert not degraded_events(toy), "a quiet watcher must not report itself degraded"

    (toy / "bin" / "tessera-watch").unlink()
    r = run_hook(hook, hook_input(toy))
    assert r.returncode == 0, "setup wrong — expected the silent bail-out"
    assert_reported(toy, "the observatory watcher is gone and no predicate can fire",
                    "tessera-watch")


def test_probe_10_watch_surfacer_treats_a_crash_as_nothing_to_report(toy):
    """`bin/tessera-watch exits 2 → does anything say so?`

    Subtler than deletion and likelier: the surfacer tested `[ $? -eq 1 ] || exit 0`, so
    rc=0 (nothing fired, correct silence) and rc=2 (a predicate raised) took the SAME
    branch. A crashing watcher read as a healthy one.
    """
    hook = _tessera_like(toy, "tessera-watch", "tessera-watch-surface.sh")
    watcher = toy / "bin" / "tessera-watch"
    watcher.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(2)\n")
    watcher.chmod(0o755)
    r = run_hook(hook, hook_input(toy))
    assert r.returncode == 0, "setup wrong — expected the silent bail-out"
    assert_reported(toy, "a crashing watcher must not read as a quiet one", "tessera-watch")


def test_probe_11_findings_surfacer_with_no_runner_is_silent(toy):
    """`rm bin/tessera-findings → does anything say so?`

    This is the framework's channel for learning from its own downstreams. Gone, the
    backlog silently stops surfacing and every session reads as "nothing open" — which is
    also exactly what a healthy empty backlog looks like.
    """
    hook = _tessera_like(toy, "tessera-findings", "tessera-findings-surface.sh")
    run_hook(hook, hook_input(toy))
    assert not degraded_events(toy), "baseline wrong — a working runner must be silent"

    (toy / "bin" / "tessera-findings").unlink()
    r = run_hook(hook, hook_input(toy))
    assert r.returncode == 0, "setup wrong — expected the silent bail-out"
    assert_reported(toy, "the findings backlog cannot surface", "tessera-findings")
