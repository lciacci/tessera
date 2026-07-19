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

- **Model-emitted recorder** (the semantic producer): Claude appends an event at each gate moment
  via `scripts/gate/emit.py`. Captures the real *semantic* gate decision. `score`/`threshold`
  absent (no scorer); `should_fire` null (see below).
- **Stop-hook gate-scan backstop** (`scripts/gate/scan.py`, live 2026-07-11 in tessera, howler
  and conclave): **the recorder above is no longer trusted to remember.** It rode model recall
  and missed **~85%** of gates under real work; measured against downstream transcripts, howler
  had logged 4 of 43 gate-shaped turns and conclave 22 of 57. The Stop hook now counts
  gate-shaped turns in the session transcript, diffs against this log, and exits 2 on a gap, so
  the model must adjudicate before it can finish. **The trigger is the harness, not memory**
  (principle #17).
  - Detection is a deliberate **recall net, not an oracle** — it over-counts, and the model is
    the precision filter on the exit-2 turn. What it cannot do is *forget*, which was the whole
    failure mode.
  - **Known recall hole:** the detector is *question-shaped*. A gate surfaced declaratively
    ("here's what I'd do, proceeding unless you object") ends in a statement and is invisible to
    it. So the miss rates above are **floors, not ceilings**.
  - "Claude forgot to log a gate" **is now a bug, not just a finding** — the backstop exists to
    catch it.
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

**Dogfood resolution (2026-07-13, P7 first labeling pass):** labels are written **inline**, with
provenance riding along so a labeled value is never mistakable for an emit-time one:

- `should_fire` — the label (bool), or `null` when evidence is genuinely absent (a null is
  honest, not lazy — 4 of the first 44 stayed null).
- `should_fire_basis` — one line of evidence: the user's disposition quote from the session
  transcript, or the observable outcome. **Ground truth is the user's recorded disposition,
  never the labeler's opinion of the gate** (the labeler is usually the gate's author — the
  2026-07-12 lesson applies). Labels are adversary-sample-checked via `tessera-verify`.
  **Quotes are verbatim, typos included, one message per quote** — the first sample-check
  (2026-07-13) caught a basis that silently typo-corrected and composited two user messages;
  a "cleaned" quote is unfindable in the transcript and reads as fabricated to any verifier.
- `labeled_ts` — when the label was applied.

Inline is lossless (a join file could be generated from these fields mechanically), the logs are
gitignored per-machine runtime state, and a join would add a moving part to an apparatus
ADR-0006 already flags for pruning. The **production join question stays open**: if a live
outcome source ever ships (accept/dismiss captured at disposition time), that producer's shape
is decided then — and that is the point at which this earns an ADR.

### `labeled_by` provenance — `should_fire` passive extraction (BUILT 2026-07-19, producer side)

Manual labeling is a dead act (the P7 backlog: 52 unlabeled gates across 19 sessions nobody will
hand-label; P7 snoozed, not resolved). The fix — **passive extraction** — is now **built on the
producer side** (`scripts/gate/label.py`): it applies spec-13's classifier pattern to fill
`should_fire` from the user's DISPOSITION (the first human turn after the gate, timestamp-joined),
the same way friction Phase 3 (#31) did for corrections. It writes back in place, idempotent,
fail-open to null, and **never overwrites a human label**. **The metric definition does not change**
(`should_fire_ratio` stays mean over `fired` × `should_fire`) — only *how the label gets populated*.

**Backtest finding (n=3, this session):** the plumbing is correct, and precision is **~0.5 as
spec-13 predicted** — the classifier conflates a terse approval ("go ahead") with an unnecessary
pause, so it under-labels genuine gates the user simply agreed with quickly. **This is exactly why
`labeled_by` matters** — the two consequences below are load-bearing, not optional:

Two consequences the **dashboard (consumer side, still a pickup)** must handle:

1. **A new provenance field — `labeled_by: human | classifier`.** Auto-filled labels are ~0.5
   precision (the spec-13 classifier finding), so they must be **separable** from the trusted
   hand-labels, never silently pooled. The dashboard should slice/weight by `labeled_by`: human =
   the trusted anchor, classifier = coverage-filler. This is the same discipline as `tessera-watch`
   P10 gating the haze band re-tune behind a precision spot-check.
2. **The ratio will move — coverage un-blinds.** Today the matrix is computed over ~40 hand-labeled
   gates and excludes nulls; filling the nulls automatically recomputes it over *all* gates. Expect
   a shift on the number that is **not** a change in gating behavior — it is the denominator
   un-blinding (exactly like `correction_density` 0.00 → 0.219 when Phase-1 lifted its blindness).

Producer built (`scripts/gate/label.py --session <id>` / `--all`, backfill-first — the Stop-hook
auto-wire is a deliberate follow-on once a full `--all` backfill has generated a real precision
sample for the P10 spot-check). Consumer (dashboard `labeled_by` slice) is still the open pickup.

## Consumers

- `tess-dashboard` — gate calibration panel. Computes the confusion matrix / precision / recall
  over (`fired` × `should_fire`). That math is consumer-side and documented in the dashboard,
  not here.

## Status of the producer

Tessera **emits** `suggestion_gate` events via the model-emitted recorder (`scripts/gate/emit.py`),
written to `.tessera/logs/<session-id>.jsonl`. The dashboard reads them live (`source: logs`) and
falls back to the fixture only when no real events exist. `score`/`threshold` are absent (no scorer)
and `should_fire` is `null` at emit time. It is filled post-hoc — by a human (inline label, no
`labeled_by`) or by the passive classifier (`scripts/gate/label.py`, `labeled_by: "classifier"`,
~0.5 precision). Events still `null` (no disposition found, or Ollama down) are excluded from the
dashboard's calibration matrix rather than scored as misses.
