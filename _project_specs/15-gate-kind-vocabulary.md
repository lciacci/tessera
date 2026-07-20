# 15 — suggestion_kind controlled vocabulary

**Status:** BUILT (2026-07-20, same day — D15-1/2/3 adjudicated as proposed). `emit.py` enforces
`KINDS` fail-closed (exit 2); `scripts/gate/remap_kind.py` remapped the live logs — 50 events
rewritten to the 7 kinds, originals kept in `suggestion_kind_raw`, 0 unknown; post-remap
distribution: design 58 / finding 11 / process 10 / scope 7 / sequencing 7 / outward 7 / doc 4.
Contract table + CLAUDE.md gate bullet + scan.py adjudication message all carry the enum.
**Motivation:** probe (2026-07-20): 102 gate events carry **33 distinct `suggestion_kind` values**,
mostly singletons — `design`, `design-decision`, `design_choice`, `design-approach`,
`design-direction` all coexist. Free-text kind = every by-kind rollup (tess-dashboard, any
calibration slice) is noise. The contract itself planned for this: "open string set today; promote
to an enum if/when the kinds stabilize" (`docs/contracts/gate-event.md`). They didn't stabilize —
they diverged. Promote now, before more data accrues.

---

## The vocabulary (proposal — [Decision D15-1])

Seven kinds, partitioning all 33 observed values:

| kind | meaning | absorbs (observed → count) |
|---|---|---|
| `design` | how to build/shape a thing | design 28, design-decision 7, design-approach 3, approach 3, design-direction 2, structural 5, design_choice 1, decision 5, feature 1, implementation 1, spec-fold 1 |
| `scope` | what's in/out of the work | scope 5, prune 1, cleanup 1 |
| `sequencing` | what next, what order | next-work 3, sequencing 3, priority 1 |
| `process` | conventions, protocols, checks | process 5, trial-protocol 1, trial-verdict 1, check-add 1, curation-policy 1, provenance 1 |
| `finding` | surfacing a discovered problem | finding 9, bug 1 |
| `doc` | doc changes/fixes | doc 2, doc-fix 1, doc-scope 1 |
| `outward` | irreversible or externally-visible acts (commits, releases, global writes) | commit 2, action 2, outward-action 1, release 1, global-layer-refresh 1 |

Design bias: few enough that the model picks the same one twice; `outward` split out because
irreversibility is the axis the surfacing convention actually cares about.

## Enforcement — emit-time reject ([Decision D15-2])

`emit.py` validates `--kind` against the enum; unknown → exit 2 listing the valid set.
Fail-closed is safe *here specifically*: emit is model-interactive (the model re-runs with a
valid kind in the same turn), unlike ingest paths which must fail open. No alias
auto-normalization — aliases are how 33 kinds happened.

- Enum lives in `scripts/gate/emit.py` (single source; stdlib-only constraint holds).
- Contract updated: `suggestion_kind` promoted from "open string set" to the enum, table above
  copied in. tess-dashboard consumes the same seven.
- CLAUDE.md gate bullet gains the kind list (one line) so the model sees valid kinds at
  emit time without reading the contract.
- Tests: valid-kind passes, unknown-kind exits 2 naming the set (in `test_gate_emit.py`).

## Backfill — one-shot remap ([Decision D15-3])

Logs are gitignored runtime state — no git history to preserve the raw value. So the remap
keeps it: rewrite each gate event's `suggestion_kind` per the table, storing the original in
`suggestion_kind_raw` (only when it differs). Stdlib one-shot (same in-place line-rewrite shape
as `label.py`), idempotent (`_raw` present → skip). Run once, tally printed, script stays in
`scripts/gate/` as `remap_kind.py` with the mapping table — it IS the executable record of the
merge.

## Out of scope

- No doccheck check: the enum is enforced at emit (the only writer) and unit-tested; a doc
  assertion would duplicate the test.
- No re-typing of kinds by a classifier — the note field carries the semantics; kind is a
  coarse slice, not ground truth.

## Sizing

One short session: enum + reject (30 min), remap script + run (30 min), contract + CLAUDE.md
sync (30 min).
