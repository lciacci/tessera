# Contract: suggestion-gate event

**Status:** Canonical. Owned by Tessera (the producer). Defined here; consumers conform.

The dashboard (`tess-dashboard`) is the first consumer and builds against a fixture in this
shape until Tessera emits real events. The dashboard's copy is a pointer to this doc — not a
second source of truth. If this contract changes, the change happens here.

A concrete instance of the generic Tessera hook-event shape (design-principles.md line 591:
structured event log, `type` / `source` / structured `data`, one JSON object per line in
`.tessera/logs/<session-id>.jsonl`). Emitted by the suggestion-gate (principle #12: Claude
proposes, user disposes).

```jsonc
{
  "type": "suggestion_gate",        // discriminator; consumers filter on this
  "ts": "2026-06-23T18:25:00Z",     // ISO 8601
  "session_id": "uuid",
  "source": "suggestion-gate-hook", // emitting hook
  "data": {
    "fired": true,                  // boolean — did the gate surface the suggestion?
    "suggestion_kind": "compact",   // category of the withheld/shown suggestion
    "score": 0.82,                  // gate confidence at decision time, 0..1
    "threshold": 0.70,              // gate threshold at decision time, 0..1
    "should_fire": true             // GROUND TRUTH — see Open question below
  }
}
```

## Field semantics

- `fired` / `should_fire` are **booleans** by contract. Consumers should parse strictly; the
  fixture happens to be clean, real producers must not emit truthy-but-non-boolean values.
- `score` / `threshold` are in `0..1`. The gate fires when `score >= threshold` (the
  decision is recorded, not recomputed — store both so calibration can detect threshold drift).
- `suggestion_kind` is an open string set today (`compact`, …); promote to an enum if/when the
  kinds stabilize.

## Open question — `should_fire` (ground truth)

The calibration question is "did the gate fire when it should have?" — which needs a truth
signal independent of the gate's own decision. The gate does **not** know this at fire time;
it arrives post-hoc (user accepted/dismissed the suggestion, or a later annotation).

- In **fixtures**, `should_fire` is labeled inline so a consumer can be built against it.
- In **production**, `should_fire` likely moves **out of `data`** and becomes a separate
  outcome/annotation joined to the event by `session_id` + `ts`.

This is undecided. When real events flow and the outcome source exists, resolve it — and if the
resolution is a genuine fork (inline field vs. join), that is the point at which this earns an
ADR. Until then it lives here, next to the shape it qualifies.

## Consumers

- `tess-dashboard` — gate calibration panel. Computes the confusion matrix / precision / recall
  over (`fired` × `should_fire`). That math is consumer-side and documented in the dashboard,
  not here.

## Status of the producer

Tessera does **not** emit `suggestion_gate` events yet. The dashboard reads a fixture and falls
back to it (`src/server/gate.ts`). Flip to live `.tessera/logs/*.jsonl` when the gate hook
emits — see `tess-dashboard/docs/DEFERRED.md` (blocked-on-external row).
