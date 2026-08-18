# ADR-0027: P13 gains an acknowledgment — a watermark, because a snooze blinds the predicate

- **Date:** 2026-08-18
- **Status:** Accepted
- **Decision driver:** ADR-0025 named it: *"P13's noise is unresolved and is the practical blocker.
  14 of 16 events are one detector, and the missing acknowledgment state means correct-but-spent
  fires cannot be cleared."* It is one of that ADR's own re-evaluate triggers. Human disposition:
  Lorenzo picked the model-emittable option from three offered.
- **Executed:** 2026-08-18 — `scripts/degraded_ack.py`, `bin/tessera-watch`
  (`_event_time`, `p13_degraded`), `scripts/test_degraded_ack.py`,
  `scripts/test_tessera_watch.py`, `docs/contracts/degraded-event.md`, `CLAUDE.md`.

---

## The contradiction this resolves

`docs/contracts/degraded-event.md` argued, correctly and in writing, that **P13 needs no
disposition verb**: it is windowed, so nothing can accumulate the way iCPG's drift backlog reached
700 undisposed rows, and *a counter that only increments is indistinguishable from a broken
detector.* That argument is sound and is not overturned here.

What the window cannot do is separate two facts it collapses:

| | |
|---|---|
| "the guard is missing **now**" | the alarm |
| "the guard was missing **on Sunday**, and I fixed it on Sunday" | true, spent, and still firing until Sunday + 7 |

ADR-0025 measured the cost of that collapse: 14 of the 16 degraded events ever written come from
one detector, `G-a` graduated on the streak, and the two available responses were both wrong —
**waiting it out trains the reader to ignore the channel, and snoozing blinds P13 to new events.**
A channel that trains its reader to ignore it cannot carry an autonomy precondition.

## Decision

### 1. The disposition is a **watermark**, not a suppression

`scripts/degraded_ack.py` writes a `degraded_ack` event carrying a `(component, reason)` pair and
a timestamp. P13 honours it **only for degraded events recorded before that timestamp.**

This is the rule the spend contract already applies to grants and dismissals — *honoured when
recorded after the last denial; a disposition logged earlier says nothing about a later failure*
— and it is the entire safety argument for §2. **An ack cannot suppress a break that has not
happened yet.** A snooze can, which is why this is not one.

It also preserves the contract's original reasoning rather than trading it away: acks are
watermarks, one per pair, not an open set. **Nothing accumulates, so the iCPG backlog failure mode
cannot recur through this verb.**

Keyed on the pair, not the channel: acknowledging the noisy detector must not silence a genuine
`spend-guard` failure sitting in the same window.

### 2. The **model** may emit it, and the watermark is why that is admissible

ADR-0016's axis is *what does the detector's over-firing mean*. This is a third answer, and the
reason that ADR was right that one verb would have been wrong:

| mechanism | over-firing means | emitter |
|---|---|---|
| `gate --not-a-gate` | over-counts **by design** | model |
| drift `dismissed` | **the detector was wrong** | model |
| spend `dismiss` | a false positive on a **safety** control | human, deny-list enforced |
| **`degraded_ack`** | **real, and now resolved** | **model** |

The party that resolved the condition is the session that did the fixing. Requiring a human
keystroke to clear noise a human did not create is precisely the friction ADR-0025 objects to.

The admissibility argument is structural, not trust: this verb authorizes nothing, expires
nothing, has no dollar figure, and **cannot hide a future failure**. It is the opposite of
`grant`, whose whole risk was that it commits something irreversible.

### 3. It cannot silence anything invisibly

The degraded events stay in the log verbatim; nothing is deleted, and the `degraded_ack` event
carries its required `--note` in the same session log — so the reasoning for every suppression is
durable and readable next to the thing it suppressed. When P13 fires with a *partial* ack it names
the count: `"1 degraded event(s) in 7d, 1 acknowledged (…)"`.

**Known ceiling, measured while writing this ADR and stated rather than fixed.** An earlier draft
of this section claimed P13 reports the acknowledged count on **both** paths, citing the quiet
string `"8 degraded event(s) in 7d, all acknowledged"` — deliberately distinct from `"no degraded
events in 7d"`, because those are two different facts a bare `fired: False` collapses into one.
**That string reaches nobody.** `append_log()` records only predicate *names* for fired and
crashed runs, and `render()` emits only crashed, fired and snoozed sections, so a non-fired
predicate's detail is computed and discarded. The claim was standing pattern #9 — a mechanism that
runs having been mistaken for one that arrives — written into the ADR *for* the check that exists
to stop exactly that.

Not fixed here, on the same reasoning ADR-0026 used for its extraction ceiling. The available
cheap fix is to have `append_log` select non-fired predicates by matching the word "acknowledged"
in their detail string, which is a guard keyed on prose — principle #3's corollary, and the shape
that made two candidate handoff checks fail measurement in the A6 audit. Surfacing it properly
needs the predicate contract to carry the fact structurally rather than in a sentence, and that is
a change to all sixteen predicates, not to this one. **The residual risk is bounded by what does
survive: the ack event and its note.** A suppression is always reconstructable; it is just not
announced.

### 4. An ack naming nothing is refused

`--note` is required (≥25 chars), on `restore/emit.py`'s reasoning: a bare verdict is the failure
mode, and the cheapest path must not be the empty one. An ack for a `(component, reason)` that has
**never** written a degraded event is rejected outright — otherwise a typo leaves a watermark that
suppresses nothing today and is indistinguishable from a deliberate disposition later. That is a
fail-open of the quietest kind, inside the verb built to reduce noise.

## Verification

Re-planted **in** the code under test, both halves, and the measurement corrected a claim:

| Probe | Result |
|---|---|
| Unacked event, correct filter | fires ✓ |
| **Inverted default re-planted** (`when > acked_through.get(key, when)`) | **4 tests fail, 3 pass** |
| Ack recorded *after* the event | quiet ✓ |
| Ack recorded *before* the event | still fires ✓ |
| Ack on one pair, live event on another | fires, names only the live pair ✓ |
| Typo guard disabled (`if False:`) | 2 tests fail ✓ |
| `scripts/degraded_ack.py` under `/usr/bin/python3` (3.9.6) | parses ✓ |
| `bin/tessera-test` | green |

**The inverted default is worth recording, because this feature shipped with it.** The filter was
first written `when > acked_through.get(key, when)`; with no ack the default equals the value it
is compared against, so `when > when` is False and **every unacknowledged event read as
acknowledged — P13 goes silent altogether.** That is the fail-open class spec 11 exists to detect,
introduced into spec 11's own predicate, by the change meant to make it more trustworthy.

**And the re-plant falsified something I had already written about it.** The test's docstring
claimed the other ack tests "all still PASSED against it, because they each plant an ack."
Measured, that is false: the scoping and acknowledged-count tests fail too, and so does the
*pre-existing* naive-timestamp test, which plants no ack at all and was the widest net of the four.
Corrected in place. A plausible claim about which guard catches what, written without running it,
is the thing this repo keeps paying for — and it recurred here inside the verification section.

## Review round 1 — 7 findings, and the two that mattered were in the mechanism itself

Run before committing. Two were live bugs in this decision's own implementation, three in the
`handoff-items-name-their-records` check shipped alongside it, two were unguarded claims.

**1. A blank-`ts` event could never be acknowledged, and the CLI said it had been.** A missing
`date` (chaos probe 5) leaves `ts` empty and `_event_time` falls back to the log file's mtime —
but the ack is appended to *that same file*, pushing its mtime past the ack's own second-precision
stamp. The event compared as newer than its own acknowledgement and stayed live forever; any later
gate/spend/restore append moved it again. **Reproduced independently before fixing.** Blank-`ts`
events are now ordered by POSITION within their own file — the one ordering a missing clock cannot
take away — and stay live across files, where no causal order exists. Erring toward firing.

**2. The strict `>` broke §2's load-bearing invariant inside one second.** Both `_utc_now_iso()`
and `tessera-degraded`'s `date` truncate to the second, so a failure occurring *after* an ack but
within the same second compared equal and was silently acknowledged. That is precisely the "an ack
cannot suppress a break that has not happened yet" property the model-emittable argument rests on.
Now `>=` on the live side: an ack takes a second to settle, which is the safe direction.

**3–5. The new doccheck check had three defects, all latent, all in the direction of looking
correct.** It located the queue by the first `### Next —` *anywhere* in the file, so a heading
rename — a form the surfacer accepts, and one that has drifted before — made it validate frozen
history while the live queue went unchecked. It treated any backticked token containing `/` as a
repo path, so `` `origin/main..HEAD` `` would have blocked a commit. And it slurped every token
after the `**Governs:**` marker to the end of the item, so the first item to add a note underneath
would have gone red for prose that was never an anchor.

**6–7. Two claims with nothing keeping them true.** `scripts/degraded_ack.py` promised a 3.9
guarantee that only a one-time manual parse supported — the exact state `decision_surface.py` was
in before its hook died silently; it is now in `SAFETY_SCRIPTS`. And a code comment on the
all-acknowledged branch asserted the detail "reaches the watch log", which §3 above had already
established is false — **the correction landed in the ADR and the contract two hours before the
comment beside it still said the opposite.** A doc claim does not stop being one because it is
written in Python.

**One re-plant was invalid and the test passed against it.** Reverting only the `start =` line of
finding 3's fix left the new `section_end` in place, so the block came back empty and the check
returned clean for a reason unrelated to the defect. Restoring the whole original anchoring block
reproduces the reviewer's symptom exactly. Beside the failure, not in it — #10's 2026-08-15
sharpening, scored again in the round that was checking for it.

## Alternatives considered

- **Do nothing; let the window expire.** The status quo ADR-0025 rejected. It is not neutral: it
  spends seven days of a channel's credibility per incident.
- **Snooze P13.** Available today and explicitly rejected by ADR-0025 — it suppresses the
  predicate, so a *new* degraded event during the snooze is lost. Strictly worse than the noise.
- **Human-only, via the spend-guard deny list.** Matches `tessera-authorize dismiss`. Rejected on
  the axis above: the safety stake that justifies the deny list for `grant`/`dismiss` is absent
  here, and the friction falls on the wrong party.
- **A health signal — age an event out once its component reports OK.** The cleanest form, and it
  is the tier-1/tier-2 shape ADR-0006 asks for. Rejected on cost, not merit: components only report
  *failure* today, so this means building a liveness protocol for every hook first. Recorded as the
  better answer if this verb proves insufficient.
- **Whole-channel watermark instead of per-pair.** Rejected: it would let acking the noisy detector
  silence a real `spend-guard` failure in the same window.

## Re-evaluate when

- **An ack is ever emitted for a condition that was not actually resolved.** That is the failure
  this bets against, and it will look like a reasonable one-line note.
- **`degraded_ack` is still at n=0 after more correct-but-spent fires accumulate.** ADR-0016's own
  trigger, applied here: a mechanism that has only ever produced silence has not been shown capable
  of speaking, and "the verb works" and "the verb is decorative" stay indistinguishable until it
  runs.
- **Acks cluster on one `(component, reason)`.** That is not a disposition problem, it is a
  detector calibration signal, and it should produce a decision about the detector — the same rule
  ADR-0016 set for drift dismissals.
- **A component gains a liveness signal** → revisit the health-signal alternative, which needs no
  disposition verb at all.
- Next cadence review: 2026-11-16 (90 days).

---

## References

- ADR-0025 — named this as the practical blocker and deferred it on sequencing
- ADR-0016 — the disposition-verb axis; why one verb for all subsystems would have been wrong
- ADR-0006 — the tier ranking that makes the health-signal alternative the better long-run shape
- `docs/contracts/degraded-event.md` — the contract whose "needs no disposition verb" line this amends
- `docs/contracts/spend-authorization.md` — the after-the-last-denial rule this reuses
