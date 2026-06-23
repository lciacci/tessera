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
  "source": "suggestion-gate-recorder", // the emitter (see Producers below)
  "data": {
    "fired": true,                  // boolean — did the gate surface the suggestion?
    "suggestion_kind": "refactor",  // category of the withheld/shown suggestion
    "note": "make contract canonical", // optional free text — what was proposed
    "score": 0.82,                  // OPTIONAL — gate confidence 0..1; absent if no scorer
    "threshold": 0.70,              // OPTIONAL — gate threshold 0..1; absent if no scorer
    "should_fire": true             // GROUND TRUTH — see Open question below; null until labeled
  }
}
```

## Field semantics

- `fired` is a **boolean** by contract. Consumers should parse strictly; real producers must
  not emit truthy-but-non-boolean values.
- `suggestion_kind` is an open string set today (`refactor`, `compact`, …); promote to an enum
  if/when the kinds stabilize.
- `note` is **optional** free text: what the gate actually proposed at that moment. The
  recorder logs it so the event stream reads as a reviewable journal, not a bare counter. Not
  every producer need supply it.
- `score` / `threshold` are **optional**, in `0..1`. When present, the gate fired iff
  `score >= threshold` (decision recorded, not recomputed — both stored so calibration can
  detect threshold drift). A model-emitted recorder with no scoring heuristic **omits both**
  rather than inventing numbers; a future scored producer adds them.
- `should_fire` is the ground-truth label and is **nullable** — `null` at emit time for a
  model-emitted recorder (the outcome isn't known yet), filled post-hoc. See below.

## Producers

- **Model-emitted recorder** (current, the dogfood): Claude appends an event at each gate moment
  via `scripts/gate/emit.py`. Captures the real *semantic* gate decision. `score`/`threshold`
  absent (no scorer); `should_fire` null (labeled later in the dashboard). Reliability = the
  CLAUDE.md convention itself — "Claude forgot to log a gate" is a dogfood finding, not a bug.
- **Hook-detected / scored producer** (future, if wanted): a deterministic emitter that adds
  `score`/`threshold`. Not built — would answer a production-measurement question the dogfood
  doesn't yet pose.

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
