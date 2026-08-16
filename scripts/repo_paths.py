#!/usr/bin/env python3
"""Paths named in this repo's docs that are NOT this repo's to govern.

WHY THIS FILE EXISTS, AND WHY IT IS NOT `doccheck.PATH_ALLOWLIST`.

`decision_surface.py` indexes every backticked repo-shaped path in the ADRs and the
observatory, and treats it as a path those records GOVERN. A Switchyard evaluation that
backticks Switchyard's own `docs/architecture.md` therefore made an NVIDIA-proxy ADR fire
as a governing decision for any Tessera file that ever took that name (found 2026-08-15).

The first fix reused `doccheck.PATH_ALLOWLIST` on the reasoning that a human had already
written down which paths are not ours. **That reasoning was wrong and it broke something.**
`PATH_ALLOWLIST` means "not required to exist on disk", which is a different question with
several unrelated answers stacked in one set:

  - other repos' files            <- genuinely not ours
  - downstream projects' files    <- genuinely not ours
  - OUR OWN gitignored runtime state (`.mnemos`, `.claude/settings.local.json`, ...)
  - OUR OWN planned-but-unbuilt paths (`PLANNED_PATHS`)

The last two are Tessera's. Treating them as foreign silenced the decision surface on
`.claude/settings.local.json` — a live, 16KB, agent-editable file — dropping ADR-0009 and
the observatory entry "A Tessera skill silently shadowed a built-in command". A change made
to stop the hook firing WRONGLY instead stopped it firing AT ALL, on a real file. Planned
paths are the same error latent: an ADR that designs a file is exactly what you want to see
the day someone creates it.

So this set is defined by ONE question — "does this path belong to another repo or to a
downstream project?" — and nothing else. It is imported BY `doccheck` into
`PATH_ALLOWLIST`, so there is still a single definition of the data and
`referenced-paths-exist` is unchanged.

WHAT THIS FILE DELIBERATELY DOES **NOT** CONTAIN: the comparison. `decision_surface`
filters with its own inline prefix match and `doccheck`'s guard re-implements that match
independently, on purpose. The first version of that guard called the filter's own
predicate, so stubbing `_is_exempt` restored the whole defect (index 140 -> 148 keys) while
the check returned clean. **A guard must not share its predicate with the thing it guards**
— sharing the DATA is fine, sharing the COMPARISON makes the check an echo.

Stdlib-only and import-free by design: `decision_surface` imports this at module scope and
runs under a bare `python3` (possibly macOS 3.9) inside a PreToolUse hook, and it must work
in a scaffolded downstream where `doccheck.py` is not installed. `bin/tessera-new-project`
copies it alongside `decision_surface.py` and `decision_amendments.py` for that reason;
doccheck's `decision-surface-deps-ship-downstream` asserts it stays in that copy set.
"""

# Other repos' files. The observatory *evaluates* Open GSD; it does not claim to contain it.
_OTHER_REPOS = {
    "bin/lib/state.cjs",
    "bin/lib/capability-registry.cjs",
    "bin/lib/capability-loader.cjs",
    "docs/ARCHITECTURE.md",
    ".claude/rules",
}

# Claims about DOWNSTREAM projects, not about Tessera. Tessera is the framework: it consumes
# downstreams' FINDINGS.md (see bin/tessera-findings) and does not carry one, and
# _project_specs/session/ is the layout the base skill prescribes downstream.
# scripts/tessera-escalate is a PATH-fallback bridge copy living in downstream repos
# (conclave, howler); Tessera reaches its own binaries through bin/.
_DOWNSTREAM = {
    "docs/FINDINGS.md",
    "_project_specs/session",
    "scripts/tessera-escalate",
}

FOREIGN_PATHS = _OTHER_REPOS | _DOWNSTREAM

# Template shapes, never files: `.claude/scripts/X`, `docs/adr/NNNN-*.md`. Kept here rather
# than in doccheck so the two consumers agree on what a placeholder looks like; as with
# FOREIGN_PATHS, only the DATA is shared and each side applies it itself.
PLACEHOLDER_PATTERN = r"[{}]|/X$|NNNN|YYYY|TITLE|\.\.\."
