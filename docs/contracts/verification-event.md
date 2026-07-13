# Contract: verification event

**Status:** Canonical. Owned by Tessera (the producer). Defined here; consumers conform.

A concrete instance of the generic Tessera hook-event shape (design-principles.md: structured
event log, `type` / `source` / structured `data`, one JSON object per line in
`.tessera/logs/<session-id>.jsonl`). Emitted by `bin/tessera-verify` (spec 12: adversarial
verification — make the falsifier a channel; ADR-0006 decision 4).

```jsonc
{
  "type": "verification",           // discriminator; consumers filter on this
  "ts": "2026-07-13T18:25:00Z",     // ISO 8601
  "session_id": "uuid",             // CLAUDE_CODE_SESSION_ID, or "manual" outside a session
  "source": "tessera-verify",
  "data": {
    "claims": [                     // empty array when skipped
      {
        "text": "the guard blocks unauthorized boots",  // the claim, verbatim, as the author stated it
        "verdict": "REFUTED",       // CONFIRMED | REFUTED | PARTIAL | NO_VERDICT
        "evidence": "ran scripts/spend/guard.py under /usr/bin/python3; boot proceeded"
      }
    ],
    "self_test": false,             // true: the claim was a planted landmine (criterion 5)
    "skipped": false,               // true: auditable opt-out (`tessera-verify skip`)
    "reason": "…",                  // present iff skipped — why no verification was needed
    "model": "opus"                 // verifier model
  }
}
```

## Field semantics

- `verdict` values: `CONFIRMED` — the verifier tried to break the claim and could not.
  `REFUTED` — the claim is false, with the command/output that proves it. `PARTIAL` — true in
  part; treat as not-green. `NO_VERDICT` — the verifier's output was unparseable; **treated as
  failure everywhere**, because a verifier that returns nothing usable must never read as green.
- `evidence` is the exact command and output summary the verifier reports. A verdict without
  evidence is suspect; consumers may render it as such.
- A `skipped` event is a **recorded decision, not silence**: the Stop-hook backstop
  (`scripts/verify/scan.py`) accepts any `verification` event — including a skip — as "this
  session dispositioned verification". Skips are surfaced by `tessera-verify stats`; a rising
  skip count is a finding.
- `self_test: true` events are excluded from nothing today; consumers computing author-error
  rates SHOULD exclude them (`tessera-verify stats` counts them like any judged claim — known
  simplification, revisit if self-tests become frequent).

## The number this exists to collect

**Author error rate on "it's fixed"** = (REFUTED + PARTIAL) / (CONFIRMED + REFUTED + PARTIAL).
On 2026-07-12 it was 100% (n=3). `tessera-verify stats` computes it; the handoff should quote
it. It is the honest prior on any future "done" claim.

## Producers

- `bin/tessera-verify` (run / skip) — the only producer today.

## Consumers

- `scripts/verify/scan.py` — Stop-hook backstop; checks existence for the session.
- `tessera-verify stats` — author-error rate.
- `tess-dashboard` — prospective; builds against this shape.

## Trigger contract (the part that matters)

Invocable-but-forgotten is a sentence. The Stop hook (`.claude/scripts/tessera-verify-scan.sh`
→ `scripts/verify/scan.py`) fires when a session touched a safety path
(`scripts/spend/`, `.claude/scripts/`, `hooks/`, `install.sh`, `scripts/doccheck.py`,
`scripts/verify/`) AND an assistant turn claimed done/fixed/closed AND no `verification`
event exists for the session. Detection is a recall net; the model is the precision filter,
and `skip --reason` is the auditable escape hatch.

**This hook fails LOUD, not open** — the only Tessera hook that does. Every "cannot run" path
exits 2 with `VERIFY-SCAN BROKEN`, bounded by a per-session fire cap
(`.tessera/logs/.verify-scan-fires-<session>`). An unverified safety change passing quietly is
the failure class spec 12 exists to end.
