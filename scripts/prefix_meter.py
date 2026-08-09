#!/usr/bin/env python3
"""Measure Tessera's eager context prefix — what is in the window before any work happens.

ADR-0021's one adopted pattern. Deep Agents tracks *base input tokens* as a defined,
per-release metric ("tokens associated with the builtin prompt, tools, and middleware")
and cut it ~6k → ~2k. Tessera measured its equivalent ONCE — 2026-07-30, chars/4, ~15,600
— and froze the figure in a paragraph of `docs/observatory.md`. The standing-patterns
split and every CLAUDE.md edit since have moved it, and nothing said so.

**A one-shot number in prose that nothing recomputes is a doc claim**, which is the class
this repo has paid for repeatedly. So the number becomes a measurement, and doccheck's
`eager-prefix-figure-is-current` asserts the quoted figure still matches.

TWO THINGS THIS DELIBERATELY DOES NOT DO.

1. **It does not gate on a ceiling.** `docs/observatory.md` → "The eager prefix is ~15.6k
   tokens — and the size of it is NOT the argument" established that the token count is an
   *artifact*; the pain would be a miss attributable to dilution, which is unmeasured.
   Failing a build on a threshold would be principle #3's error aimed at the eager load.
   This reports drift against a recorded figure. It has no opinion on whether the figure
   should be smaller.

2. **It does not assert machine-local state.** The 2026-07-30 total folded in the Mnemos
   checkpoint (~2,600) for "~18k in practice". The checkpoint is per-machine, per-session,
   and gitignored — asserting it would make the check fail differently on every clone,
   which is how a check earns a `--no-verify` habit. Local components are MEASURED and
   REPORTED, never asserted. `tracked_total()` is the asserted figure.

Estimated at chars/4, the same method as the original measurement, so the figures are
comparable. That is an ESTIMATE and not a token count; use the API's `count_tokens` if a
decision ever rests on the exact number. The claim being checked is "~", not "=".

Stdlib only — `scripts/doccheck.py` imports this, and doccheck is kept stdlib-only so it
runs on bare `python3` from the pre-commit hook.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARS_PER_TOKEN = 4

# Claude Code imports `@path` ANYWHERE — start of line, mid-sentence, trailing space.
# The first version anchored `^@(\S+)$`, so `See @docs/design-principles.md for the
# reasoning.` was invisible: 31,346 tokens omitted, meter exit 0, doccheck GREEN. A
# >2x understatement reported as a confirmed measurement. Found by `bin/tessera-verify`
# 2026-08-09 — and flagged by it as a "caveat, not a refutation" one run EARLIER, where
# it was read as minor and not acted on. It was the same defect the whole time.
EAGER_IMPORT = re.compile(r"(?:^|(?<=\s))@([^\s`]+)", re.MULTILINE)
FENCE_BLOCK = re.compile(r"```.*?```", re.DOTALL)

# The gitignored mirror symlinks install.sh creates, and the tracked dirs they point at.
# Exactly the three named in .gitignore — see canonical_path on why this is not `.claude/`.
MIRROR_DIRS = {".claude/skills": "skills",
               ".claude/commands": "commands",
               ".claude/agents": "agents"}
PART_ARGS = re.compile(r"tessera-patterns-surface\.sh\"? --part (\d+) --of (\d+)")
HOOK_PATH = re.compile(r'exec "\$\{CLAUDE_PROJECT_DIR:-\.\}/([^"]+)"')


def tokens(text: str) -> int:
    """Estimate tokens at chars/4 — the method the 2026-07-30 measurement used."""
    return round(len(text) / CHARS_PER_TOKEN)


def eager_imports(root: Path) -> list[Path]:
    """The `@`-imported files CLAUDE.md pulls in eagerly.

    DERIVED, not hardcoded: de-eagering a skill (ADR-0008) or adding one must move the
    meter without anyone remembering to edit it. A hardcoded list would keep reporting the
    old corpus and read as stable — the exact failure this file exists to prevent.
    """
    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        return []
    body = FENCE_BLOCK.sub("", claude_md.read_text())     # fenced examples are not imports
    refs = [m.rstrip(".,;:)") for m in EAGER_IMPORT.findall(body)]
    return [canonical_path(root, r) for r in refs if "/" in r]  # a path, not an @handle


def canonical_path(root: Path, ref: str) -> Path:
    """Resolve a repo path to the location whose CONTENT is tracked.

    `.claude/{skills,commands,agents}` are **gitignored symlinks** to the top-level dirs,
    created by `install.sh`; `.gitignore` states the rule — "Canonical source is the
    top-level skills/, commands/, agents/ dirs" (ADR-0010: repo is truth, the mirror is a
    mirror). On a fresh clone, before install, those paths do not exist while their
    content is right there.

    FOUND BY `bin/tessera-verify` 2026-08-09, refuting this meter's own docstring. The
    first version took the literal path and skipped it when absent, so a clean worktree
    measured 9,689 instead of 15,497 — 37% low — and doccheck went red advising that the
    *wrong* figure be recorded. "Fails differently on every clone" is exactly what the
    check claimed to have avoided by excluding machine-local state, and it was doing it.

    **Only those three prefixes are rewritten, and the narrowness is load-bearing.** A
    blanket `.claude/` strip would resolve a wrong path like `.claude/scripts/doccheck.py`
    to its top-level namesake and report a phantom as present — turning a path checker
    into a path launderer. `.claude/scripts/` is tracked and must fail when it is wrong.
    """
    literal = root / ref
    if literal.exists():
        return literal
    for mirror, canonical in MIRROR_DIRS.items():
        if ref == mirror or ref == mirror + "/":
            return root / canonical
        if ref.startswith(mirror + "/"):
            return root / canonical / ref[len(mirror) + 1:]
    return literal


def _session_start_commands(root: Path) -> list[str]:
    """Registered SessionStart commands. Unreadable settings RAISE; unregistered is [].

    The distinction is the whole point: "nothing is registered" is a measurable state
    (the component is genuinely absent), while "settings.json will not parse" means the
    meter does not know what is registered. Swallowing the second into [] made an
    unparseable settings file look like a smaller prefix.
    """
    settings = root / ".claude" / "settings.json"
    if not settings.exists():
        return []
    try:
        hooks = json.loads(settings.read_text())
    except ValueError as exc:
        raise ValueError(f".claude/settings.json will not parse ({exc}) — the registered "
                         f"SessionStart output cannot be measured") from exc
    try:
        entries = hooks.get("hooks", {}).get("SessionStart", [])
        return [h.get("command", "") for entry in entries for h in entry.get("hooks", [])]
    except AttributeError as exc:
        # Valid JSON, wrong shape (`{"hooks": "oops"}`). Uncaught, this escaped doccheck's
        # handler and aborted all 41 checks with a traceback instead of one unverifiable.
        raise ValueError(f".claude/settings.json parses but is not hook-shaped ({exc}) — "
                         f"the registered SessionStart output cannot be measured") from exc


def patterns_parts(root: Path) -> list[str]:
    """Run each registered standing-patterns part and return its output.

    Run rather than read: the parts are chunked at emit time, so what reaches the model is
    the subprocess output and nothing else. `standing-patterns-fit-the-cap` set this
    precedent for the same reason — reading the source file measured a thing that was true
    while the delivered text was truncated.
    """
    registered = [m for m in (PART_ARGS.search(c) for c in _session_start_commands(root)) if m]
    if not registered:
        return []                      # nothing registered — a measurable absence
    emitter = root / ".claude" / "scripts" / "tessera-patterns-surface.sh"
    if not emitter.exists():
        raise OSError(f"{emitter.relative_to(root)} is registered on SessionStart but "
                      f"missing — the standing-patterns component cannot be measured")
    out = []
    for found in registered:
        result = subprocess.run(
            [str(emitter), "--part", found.group(1), "--of", found.group(2)],
            capture_output=True, text=True, cwd=root, timeout=30, check=True,
        )
        out.append(result.stdout)
    return out


def tracked_components(root: Path = ROOT) -> dict[str, int]:
    """Deterministic, git-tracked eager context. This is the asserted figure's basis."""
    components = {"CLAUDE.md": tokens((root / "CLAUDE.md").read_text())}
    for path in eager_imports(root):
        if not path.exists():
            raise OSError(f"CLAUDE.md eagerly imports {path.relative_to(root)}, which is "
                          f"not on disk — the prefix cannot be measured, only understated")
        components[str(path.relative_to(root))] = tokens(path.read_text())
    parts = patterns_parts(root)
    if parts:
        components["standing patterns (emitted)"] = sum(tokens(p) for p in parts)
    return components


def unasserted_components(root: Path = ROOT) -> dict[str, int]:
    """Real eager context that cannot be asserted, for two DIFFERENT reasons.

    The handoff surfacer varies with repo state — it prints fired observatory triggers, so
    its output is smaller on a quiet day than on a loud one. The Mnemos checkpoint is
    per-machine and gitignored. Both are genuinely in the window; neither can be pinned to
    a figure without the check failing for reasons unrelated to drift.

    They are here because omitting them silently would make the tracked total look like a
    complete measurement, and the 2026-07-30 figure it is compared against INCLUDED the
    handoff. Comparing two totals with different bases is how "roughly unchanged" gets
    concluded from numbers that were never measuring the same thing.
    """
    out = {}
    surfacer = root / ".claude" / "scripts" / "tessera-watch-surface.sh"
    if surfacer.exists():
        result = subprocess.run([str(surfacer)], capture_output=True, text=True,
                                cwd=root, timeout=60, check=False)
        out["handoff surfacer (varies with fired triggers)"] = tokens(result.stdout)
    checkpoint = root / ".mnemos" / "checkpoint-latest.json"
    if checkpoint.exists():
        out[".mnemos/checkpoint-latest.json (machine-local)"] = tokens(checkpoint.read_text())
    return out


def tracked_total(root: Path = ROOT) -> int:
    return sum(tracked_components(root).values())


def _render(title: str, components: dict[str, int]) -> None:
    if not components:
        return
    print(f"\n{title}")
    for name, count in sorted(components.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>7,}  {name}")


def main() -> int:
    tracked, rest = tracked_components(), unasserted_components()
    print("EAGER CONTEXT PREFIX — tokens present before any work happens")
    print("(chars/4 estimate, the 2026-07-30 method; not a token count)")
    _render("Tracked — reproducible from the repo, asserted by doccheck:", tracked)
    print(f"  {sum(tracked.values()):>7,}  TOTAL (tracked)")
    _render("Measured, reported, NEVER asserted — varying or machine-local:", rest)
    if rest:
        print(f"  {sum(tracked.values()) + sum(rest.values()):>7,}  TOTAL (in practice)")
    print("\nSize is not an argument for cutting — see docs/observatory.md,")
    print("'The eager prefix is ~15.6k tokens — and the size of it is NOT the argument'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
