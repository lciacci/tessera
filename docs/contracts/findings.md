# Contract: downstream FINDINGS.md

**Status:** Canonical. Owned by Tessera. Downstream projects and consumers conform.

Closes the downstream→framework feedback disconnect. Findings surface while working in a
downstream repo (howler, conclave, tess-dashboard, …). Transfer back to Tessera used to be
manual and lossy — a finding could sit written-down-but-un-actioned indefinitely (howler F-004
did). This contract makes the backlog scannable so nothing rots.

Producer: each downstream project. Consumer: `bin/tessera-findings` (and later a tess-dashboard
panel). If this shape changes, it changes here.

## File

Every Tessera project (any dir with `.tessera/project.yml`) carries `docs/FINDINGS.md`. A project
with no framework friction yet still carries the file with zero findings — an empty channel, not
a missing one. The scanner distinguishes the two.

## Finding shape

One finding per `## F-NNN — Title` section. Directly under the header, a single Status line:

```markdown
## F-004 — Package rename left JNI C++ symbols stale → crash on open

**Status:** open
**Surfaced:** 2026-06-30, closed tester reported crash on open.

...prose: what happened, why it slipped, framework fix to transfer, when-to-fix...
```

## Status vocabulary

Parsed by `bin/tessera-findings`. Everything before the first `:` is the state.

| Status | Meaning |
|--------|---------|
| `open` | Surfaced, not yet transferred to the framework. Shows in the default backlog. |
| `transferred:<ref>` | Landed in Tessera. `<ref>` = ADR / observatory entry / commit. Hidden unless `--all`. |
| `rejected:<reason>` | Considered, deliberately not adopted. Hidden unless `--all`. |

A finding with **no** Status line is treated as `open` — unknown counts as needs-attention, never
silently dropped.

## Scanner

```
tessera-findings          # open backlog across all downstream projects (exit 1 if any open)
tessera-findings --all    # every finding, any status
tessera-findings --json   # machine output for tess-dashboard
```

Discovery is by convention, no registry to maintain: it globs `<root>/*/.tessera/project.yml`
(root defaults to Tessera's parent dir; override with `--root`).
