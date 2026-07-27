# ADR-0018: One drift event per dimension — the composite event made three separate things ambiguous

- **Date:** 2026-07-27
- **Status:** Accepted
- **Executed:** 2026-07-27 — `scripts/icpg/drift.py`, `scripts/icpg/test_drift.py`. `check_symbol_drift` returns `list[DriftEvent]` (one per firing dimension) instead of an optional composite; `_build_event` takes one dimension and stores that dimension's real score. No storage change, no data migration — see "Scope" below.
- **Decision driver:** ADR-0017 retired `usage` and dismissed 165 drift events. The dismissal rollup then read `usage 165, changed 29` — `changed` credited with 29 detector errors it never made, because 29 of the events were `['changed','usage']` composites and the counter credits every dimension in an event.

---

## Decision

**A symbol that drifts on N dimensions produces N drift events, each carrying exactly one dimension and that dimension's own score.**

Previously one symbol produced at most one event, carrying a list of dimensions and the **mean** of their scores.

---

## What the composite made ambiguous

Three distinct defects, one cause. Each was found separately and none of them looked related until the shape was named.

**1. Severity described nothing.** `severity = round(sum(scores) / len(scores), 2)`. A `changed` at 0.8 beside a `decision` at 0.3 stored **0.55** — a number that is neither, attached to an event that is both. Standing pattern #3 (*name the pain, not the artifact that correlates with it*) aimed at a score: the composite severity is a proxy for two facts that should never have been averaged.

**2. Disposition could not be attributed — the defect that surfaced this.** `dismissals_by_dimension()` credits a dismissal to every dimension in the event. ADR-0016 §3 built that counter deliberately: *"a dimension accumulating dismissals is miscalibrated, and this is the only place that can be read… the one signal that can retire a dimension."* It worked — it is part of why `usage` was retired.

Then retiring `usage` required dismissing 29 composites, and the counter credited `changed` with all 29. **The signal built to retire a bad dimension was now accusing a good one**, and by its own logic `changed` looked like the next retirement candidate. A counter that cannot attribute is worse than no counter, because it is read as evidence.

**3. Suppression over-reached.** ADR-0016 §4 keys suppression on the dedup key, which includes `sorted(dimensions)`. Under composites, a symbol's `changed` and `decision` findings share one key and one disposal — so dismissing one silences the other. Two independent facts about a symbol, one off-switch. This was never observed in the wild only because `decision` has never fired; it was live the whole time.

The disposal ceremony ADR-0017 required is the clearest evidence the shape was wrong: dismissing the 29 composites was only safe after verifying, per symbol, that each one's `changed` half had re-raised as its own row (29 of 29, zero orphans). **That verification step exists only because the event bundled two findings.** Under this ADR the bundle never forms and the ceremony is unnecessary.

---

## Why this rather than recording which dimension a dismissal names

The considered alternative was a `dismissed_dimensions` column, required when the event is composite, so the dismisser states which half lied. It fixes defect 2 and nothing else, and it fixes it *by asking a human to disambiguate something that should never have been ambiguous*.

It is also **fully superseded by this ADR** — when every event carries one dimension, the event's own dimension *is* the attribution, and the column is dead weight. Doing it first would have been throwaway work. Rejected on that basis, not on cost.

---

## Scope, measured rather than estimated

The change looked larger than it was, and the initial estimate was a guess dressed as a scope. Measured:

| | |
|---|---|
| `scripts/icpg/store.py` | **no change.** The dedup key is already `json.dumps(sorted(event.drift_dimensions))` — a single-element list passes through unchanged. |
| `scripts/icpg/__main__.py` | **no change.** It calls `check_all_drift`/`check_file_drift`, which already returned lists. `_drift_scores` parses per-dimension scores out of the description and works on one. |
| `scripts/skill_lint/` | **no change.** Its `Severity` is its own enum; the name collision is not a coupling. |
| data migration | **none.** The backlog was fully disposed (0 open) when this landed, so every existing row is history. |
| `scripts/icpg/drift.py` | 3 functions. |
| `scripts/icpg/test_drift.py` | 6 call sites, plus a `_dims()` helper and one new test. |

**Only `check_symbol_drift` returned a scalar, and its only callers outside `drift.py` were tests.**

---

## Consequences

- **Event counts rise where a symbol drifts two ways.** That is honest — it was always two findings — and each is now independently resolvable, dismissable, and suppressible.
- **`severity` is a real score again**, not a mean. `_drift_scores` no longer has to reconstruct per-dimension values from the description.
- **Historical composite rows are NOT migrated.** They stay readable as evidence, the same posture retired dimension names get (`models.py`). One exception, applied here: the **29 dismissed composites were re-attributed to `['usage']`**, because their notes already record that the `usage` half was the detector error and the `changed` half was preserved as a separate resolved event. That corrects a false statement rather than rewriting history — the rollup now reads `usage 165` and `changed` is correctly absent.
- **No conflict with ADR-0016.** §4's suppression is still keyed on the dedup key; per-dimension events simply scope it correctly. §3's dismissal counter now attributes truthfully without changing its definition. Neither is superseded.
- Re-introducing composite events means superseding this ADR. `test_each_event_carries_exactly_one_dimension_with_its_own_score` asserts both halves — one dimension per event, and the averaged value explicitly absent.

## Biases named

- **Momentum.** This is the fourth cut to this subsystem in one session (6→3 dimensions, 3→2, the guard fix, this). Cutting begets cutting, and "the composite is the root cause" is exactly the kind of conclusion that feels good after three narrower fixes. The check applied: the scope was **measured** before committing to it, and the measurement is what made the call easy — had `store.py` and `__main__.py` needed real work, the incremental option would have won.
- **Cleaning up my own mess.** I created the 29 mis-attributed rows an hour earlier, which is a pull toward the option that erases them most completely. Flagged when the options were presented, and it argues for the cheap fix, not this one — this one won on measured scope and on fixing two defects the cheap fix could not see.

---

## References

- `docs/adr/0016-disposition-verbs.md` §3 (the dismissal counter), §4 (suppression key)
- `docs/adr/0017-retire-usage-drift.md` — the retirement whose disposal exposed this
- `docs/observatory.md` → "A disposition verb that did not move the headline" — the sibling counter bug found the same hour
- Standing pattern #3 (name the pain, not the proxy)
