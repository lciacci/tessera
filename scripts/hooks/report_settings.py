#!/usr/bin/env python3
"""Make a wired hook that CANNOT RUN say so, instead of exiting 0 in silence (spec 11).

THE PROBLEM. The wired form is:

    if [ -x "P" ]; then exec "P"; fi; exit 0

so a hook script that is missing, typo'd in settings.json, or merely not executable is skipped
with exit 0 and no output — indistinguishable from a hook that ran and had nothing to say.
`[ -x ]` cannot tell "not there" from "not executable" from "wrong directory". tess-dashboard
carried a typo'd hook path, so that hook had NEVER once run, and nothing noticed for weeks.

**No code inside the hook can report this, because the hook never executes.** The branch has to
live in the command string itself. That is what this module writes:

    if [ -x "P" ]; then exec "P"; fi; for d in bin scripts; do r=".../tessera-degraded"; \
      [ -x "$r" ] && exec "$r" --component C --reason hook-unavailable --detail "..."; done; exit 0

Failing open is preserved — it just stops being silent.

WHY IT IS A MODULE AND NOT A ONE-OFF. It started as one: the spec-11 fleet rollout (2026-07-26)
found that `tessera-sync-harness` only ADDS files and `--patch-settings` was anchor-only, so
nothing could put this branch into five downstreams' command bodies. It went in BY HAND. A
hand-patch closes today's hole and guarantees the next one — the next repo scaffolded before the
next command-body change drifts exactly the same way, silently, which is the "ship both halves,
violated by TIME" pattern this fleet keeps paying for. So the rule became code.

Third sibling of the same shape, one rewrite per file: `patch_settings.py` adds the ADR-0004
global fallback, `anchor_settings.py` anchors cwd-relative paths, this one adds reporting.

CONSISTENCY GUARD. `needs_reporting` is THE SHARED PREDICATE — doccheck's detector
(`unrunnable-hooks-report-themselves`) imports and calls it, rather than mirroring a regex. The
sibling modules mirror-plus-test because their detector predates them; a new pair has no reason
to inherit that risk. A fixer and a detector that disagree is the failure this repo keeps
finding: one flags what the other cannot fix.

Stdlib-only on purpose (CLAUDE.md's interpreter split) so it runs under any python3.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ANCHOR = "${CLAUDE_PROJECT_DIR:-.}"
GLOBAL_FALLBACK = "$HOME/.claude/templates"
# BOTH wired-hook directories this project uses. The first version had only `.claude/scripts`,
# which silently excluded the two local-only hooks under `hooks/` (subagent-route-hook,
# tier-classify-hook) — they passed every other gate. Because doccheck IMPORTS this predicate,
# the fixer could not fix them and the detector could not flag them, so the check read green
# while two wired hooks stayed fail-silent. The alternation mirrors anchor_settings._QUOTED,
# which had it right all along; mirroring only half of a sibling's regex was the mistake.
_ANCHORED = re.compile(
    r'"\$\{CLAUDE_PROJECT_DIR:-\.\}/((?:\.claude/scripts|hooks)/[A-Za-z0-9._-]+)"')
_TRAILING_EXIT = re.compile(r";\s*exit 0\s*$")


def component_of(script: str) -> str:
    """`.claude/scripts/tessera-gate-scan.sh` -> `gate-scan`; `hooks/tier-classify-hook` -> same.

    Takes a path or a bare name: the match now carries its directory, because two different
    wired-hook directories are in scope. Derived, never a lookup table — an allowlist would be a
    second definition of "which hooks matter" and would drift the moment one was added, the same
    shape as the bugs this module exists to stop.
    """
    return script.rsplit("/", 1)[-1].removeprefix("tessera-").removesuffix(".sh")


def needs_reporting(cmd: str) -> str | None:
    """The hook script this command should report on, or None. THE SHARED PREDICATE.

    Scope is EVERY wired hook of the recognised shape — deliberately not a component list, and
    (since 2026-07-26) deliberately not "local-only" either.

    THE RETIRED RULE, and why it was wrong. This used to exclude any command carrying the
    ADR-0004 `$HOME/.claude/templates` fallback, reasoning that a missing local file still
    resolves through the global copy so the hook runs anyway. That inverts the real risk: under
    the DEFAULT `global` distribution **no local copy is ever shipped**, so the global branch is
    not a redundancy — it is the ONLY tier. A default-scaffolded downstream whose global
    templates are missing runs the wired mnemos command to rc=0 with empty stdout and stderr and
    zero degraded events. Measured on conclave: 7 two-tier mnemos commands, 0 local copies on
    disk, needs_reporting None for all 7. Because doccheck imports this predicate, the fixer and
    the detector were blind together — the consistency guard propagated the gap faithfully.
    Found by the criterion-5 independent re-read, not by us.

    The reporting branch is appended after the whole `if/elif/fi`, so it fires only when BOTH
    tiers have failed. That is precisely the unrecoverable case, and it leaves the global tier
    untouched.

    Requires an ANCHORED path: reporting on a path that still moves with the session cwd would
    name the wrong file. Anchoring is `anchor_settings.py`'s job and must run first.
    """
    if "tessera-degraded" in cmd:          # already reports — idempotent
        return None
    if not _TRAILING_EXIT.search(cmd):     # unrecognised shape — never guess, leave it alone
        return None
    # DEDUPED, not counted: the wired form names the same script TWICE — once in the `[ -x P ]`
    # test and once in the `exec P`. A raw len(findall) == 1 therefore never matched a real
    # command and the fixer silently did nothing. Caught by the not-vacuous test, which is the
    # entire reason it exists.
    found = set(_ANCHORED.findall(cmd))
    # Exactly one distinct script, or we cannot say which hook failed.
    return found.pop() if len(found) == 1 else None


def report_command(cmd: str) -> str | None:
    """The command with a reporting else-branch, or None if unchanged (idempotent)."""
    script = needs_reporting(cmd)
    if script is None:
        return None
    branch = (
        f'for d in bin scripts; do r="{ANCHOR}/$d/tessera-degraded"; '
        f'[ -x "$r" ] && exec "$r" --component {component_of(script)} '
        f'--reason hook-unavailable '
        f'--detail "wired hook {script} is missing or not executable; it has never run"; '
        f'done; exit 0'
    )
    return _TRAILING_EXIT.sub("; " + branch, cmd)


def add_reporting(settings: dict) -> tuple[dict, list[str]]:
    """Rewrite every in-scope hook command in place. Returns (settings, changed-event-labels).

    statusLine is out of scope: it is not a hook, a dead statusline is cosmetic rather than a
    lost safety check, and downstreams use an unquoted-path form this module does not match.
    """
    changed: list[str] = []
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                new = report_command(hook.get("command", ""))
                if new is not None:
                    hook["command"] = new
                    changed.append(event)
    return settings, changed


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    path = Path(args[0]) if args else Path(".claude/settings.json")
    try:
        settings = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2
    patched, changed = add_reporting(settings)
    if not changed:
        print(f"no change needed — {path} wired hooks already report")
        return 0
    if dry:
        print(f"would add reporting to {len(changed)} command(s): {', '.join(sorted(set(changed)))}")
        return 0
    path.write_text(json.dumps(patched, indent=2) + "\n")
    print(f"added reporting to {len(changed)} command(s): {', '.join(sorted(set(changed)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
