# ADR-0016: Disposition verbs — who may close a finding, and what stops that silencing a real one

- **Date:** 2026-07-27
- **Status:** Accepted
- **Decision driver:** The same gap surfaced twice in one session from opposite directions — the spend backstop re-firing on denials it invited the model to dispose in prose, and iCPG drift's deferred `--note`/`dismissed` state (ADR-0013, ordered last). Both are "who may mark a finding closed."
- **Executed:** 2026-07-27 — all five. Spend (1, 2, 5): `scripts/spend/guard.py`, `scripts/spend/authorize.py`, `scripts/spend/backstop.py`, `docs/contracts/spend-authorization.md`. Drift (3, 4): `scripts/icpg/store.py`, `scripts/icpg/__main__.py`, `scripts/icpg/test_drift_dedup.py`. Verified on the real hook (`grant`/`dismiss` rc=2, `show`/teardown rc=0, prose about the verb rc=0) and on the live graph (a dismissed drift stays closed across a re-scan while its `seen_count` climbs).

---

## The question

A detector fires. Something is wrong with the finding — it is a false positive, or it was
real and has been dealt with. **What can the agent do that the mechanism will hear?**

Tessera had three answers already, and they disagree in a way that turns out to be correct:

| mechanism | who emits | why |
|---|---|---|
| `gate emit --not-a-gate` | **model** | `scan.py` "over-counts **by design** and the model is the precision filter" |
| `tessera-escalate resolve --note` | **human** | `--note` is `required=True` — "the decision — this is the record" |
| override annotations | neither — **audit-only** | records exceptions, never grants them |

## Decision

**These are not one question, and a single disposition verb would have been wrong.**

The axis is not "is a disposition useful" — it is **what the detector's over-firing means**.
Where over-firing is *designed in*, the model filtering it is the intended architecture.
Where over-firing is a *defect*, a model-emitted exit is that defect's own bypass.

### 1. Spend — a guard-blocked `dismiss`, emittable only by a human

`bin/tessera-authorize dismiss --reason "<why>"` writes a `spend_dismissed` event that
`undispositioned()` honours, **and the command is added to the spend guard's deny list.**

The backstop's report already invites *"If the denial was a FALSE POSITIVE … say so plainly
and finish. That is a legitimate disposition"* — and `undispositioned()` clears on exactly
two things, a grant after the last denial or an escalation packet. **Saying it plainly clears
nothing**, so the hook re-fires every Stop. That is principle #17 inside the spend gate: a
disposition that rides prose is one the mechanism cannot hear. Both existing exits are wrong
for a false positive — a grant authorizes spend nobody requested, and a packet manufactures
the bogus escalation the contract itself calls worse than none.

**"Human-only" is enforced, not asked for.** PreToolUse hooks fire on the *agent's* Bash calls
only; a human in their own terminal never passes through one. So a deny-list entry makes the
verb structurally agent-unreachable while leaving the human path untouched — reusing machinery
that already intercepts every Bash call.

### 2. `tessera-authorize grant` gets the same treatment, and this is the bigger half

Checked rather than assumed while answering "what makes it human-only": **`grant` is
agent-callable today.** Driving the real hook with `bin/tessera-authorize grant --usd 5 …`
returns `rc=0`, allow. There is no TTY check, and `granted_by` is `os.environ["USER"]` — the
same value whichever party typed it. The deny-by-default control on external spend has an
authorization verb the agent can invoke on itself, held back **only** by a sentence in
`docs/contracts/spend-authorization.md`: *"Do not grant yourself a spend envelope you do not
need."*

That is the #17 shape on the highest-stakes gate in the repo. `grant` and `dismiss` are both
added to the deny list. `show` and `revoke` are **not**: `revoke` reduces authorization, and a
spend gate must never be able to block the exit.

**This needs a new policy branch, not a new pattern in `COMMITTING`.** A committing command is
*gated* — allowed when an envelope is live. Self-authorization must be refused
**unconditionally**, or a live envelope would let the agent extend its own.

### 3. Drift — `dismissed` means *the detector was wrong*

`resolved` = the drift was real and the code or intent was fixed.
`dismissed` = it was never real — a detector false positive.

The split is chosen for what it makes countable. `usage` currently fires on 168 of 816 symbols
with 64 saturated at 1.00, and its thresholds (`>2` files, `/10`) were never calibrated against
anything; the open question is whether that dimension is miscalibrated or merely noisy, and
**there is no way to say so today**. Dismissal counts per dimension are that evidence. Merging
"the detector lied" into "true but ignored" would throw away the one signal that can retire a
dimension — and this repo has retired three proxy predicates already.

Drift is instrumentation with no safety stake, so `dismissed` is **model-emittable**, matching
the gate precedent rather than the spend one.

### 4. A dismissed drift stays suppressed until the evidence changes

Suppression is keyed on `(symbol, reason, sorted(dimensions))` — the dedup key — and holds
while the evidence is unchanged. A severity move or a new dimension re-opens it.

Re-raising every scan would re-litigate a closed decision on every Stop, which is **conclave
F-001 exactly**, a bug this repo has already paid for once and fixed with the `gate_disposition`
ledger. A fixed expiry was rejected: it adds a time knob nobody has evidence to set, and the
observatory's calendar triggers were retired in favour of event-based ones for that reason.

### 5. `_escalated()` tightens to spend-shaped categories

It clears a spend denial on **any** escalation packet — its comment says "an agent that
escalated *something* while blocked has not silently routed around." The claim is defensible
but the effect is a bypass nobody chose: a session that raises an unrelated packet silences its
spend backstop by accident. Only a spend-categorised packet clears a spend denial.

## Consequences

- The agent can no longer authorize its own spend, which is what the contract already said and
  nothing enforced. **If an unsupervised run genuinely needs an envelope mid-run, it must
  escalate and wait** — that is spec 07's asynchronous gate working as designed, and it is the
  behaviour ADR-0005 assumed was already in force.
- A second exit exists on the spend backstop, but it costs a human keystroke and leaves a
  reasoned record, where the previous "exit" was prose nothing could read.
- Drift dismissals accumulate into a per-dimension count, which is the first evidence able to
  answer whether `usage` earns its place.

## Alternatives considered

- **One disposition verb for both subsystems.** Rejected on the over-firing axis above; it was
  the framing this gate started with and the contracts refuted it.
- **Convention-only `dismiss`** (as protected as `grant` is today). Rejected: it adds a second
  prose-guarded exit to a deny-by-default control, and a dismissal is *cheaper* to abuse than a
  grant because it carries no dollar figure and reads as bookkeeping.
- **Build nothing; delete the contract's "say so plainly" promise.** The most conservative
  option and genuinely tempting — but it forces every real false positive into a bogus packet.
- **TTY / `isatty()` enforcement.** Weaker than a deny-list entry and breaks legitimate
  non-interactive human paths (CI, the in-session `!` prefix).
- **Requiring the dismissal to come from a different session than the denial.** Breaks the
  normal case, which is a human disposing during the session.

## Re-evaluate triggers

- A spend `dismiss` is ever emitted by anything other than a human at a terminal.
- **`spend_dismissed` is still at n=0 after false positives have accumulated.** As of
  2026-07-27 the verb has **never run**, while 22 genuine false positives sit in one session's
  log. This repo's own not-vacuous rule applies to it exactly as it applies to T2: *a mechanism
  that has only ever produced silence has not been shown capable of speaking*, and until it
  runs, "the verb works" and "the verb is decorative" are indistinguishable. If false positives
  keep accruing and nobody reaches for it, the honest reading is that the prose exit was
  adequate and this ADR over-built — which is a legitimate outcome to discover, not a failure.
- **The human path has never been exercised end-to-end.** The deny-list entry was verified from
  the agent side (rc=2 through the real hook) and `undispositioned()` from unit tests, but
  **nobody has run `tessera-authorize dismiss` from a terminal and watched the backstop go
  quiet.** By construction the agent cannot test this — which is the enforcement working, and
  also a real hole in the verification. An untested path is the fail-open class.
- Drift dismissals cluster on one dimension — that is the calibration signal, and it should
  produce a decision about the dimension rather than accumulating.
- An unsupervised run is blocked by the `grant` deny-list entry with no human available. That
  is the case this ADR trades away, and if it bites, the trade needs re-examining.
- The spend guard's command-TEXT matching is replaced with something that sees resolved
  commands — the deny-list entry inherits that ceiling (a runtime-assembled invocation slips
  past, as it does for every other pattern).

## References

- `docs/contracts/spend-authorization.md` — the prose this ADR converts into a mechanism
- `docs/contracts/gate-event.md` — the model-emitted precedent (`--not-a-gate`, conclave F-001)
- ADR-0013 — deferred the drift `--note`/`dismissed` state to last; this is that decision
- ADR-0005 — the autonomy inflection; assumed spend authorization was human-gated
- `docs/observatory.md` → "The spend backstop's own cap became a permanent kill switch"
