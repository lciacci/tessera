# ADR-0029: The in-band spend guard is retired — a failed experiment, and what it cost to learn that

- **Date:** 2026-08-18
- **Status:** Accepted
- **Supersedes:** ADR-0028 (scope freeze on a mechanism now being removed). **Amends** ADR-0005's
  promotion of spec 06 to Tier 1, and retires the *spend* half of ADR-0016 while leaving its drift
  half and its reasoning intact.
- **Decision driver:** Lorenzo, after a session that spent most of its length inside this
  mechanism: *"I'm struggling to understand the value, and this hasn't been the only session mired
  in it... maybe there's a better design to audit autonomy, and this is just the wrong shape for
  this framework and Claude."* And then: *"note it as what it is, a failed approach and experiment,
  what worked and more importantly what didn't, then unwind it."*
- **Executed:** 2026-08-18 — removed: `scripts/spend`, `bin/tessera-authorize`,
  `.claude/scripts/tessera-spend-guard.sh`, `.claude/scripts/tessera-spend-backstop.sh`. Also
  unwired from `.claude/settings.json` (PreToolUse + Stop), dropped from
  `bin/tessera-new-project`, and removed from `bin/tessera-watch` (P15), `chaos/test_chaos.py`
  (probes 1–4) and `scripts/doccheck.py` (two wiring checks, four `SAFETY_SCRIPTS` entries).
  `docs/contracts/spend-authorization.md` is KEPT as a retired design record.

---

## The verdict

**The in-band, pre-execution, text-matching spend guard was the wrong shape, and it was wrong for
a structural reason rather than a quality one.** No amount of further work converges it. It is
retired rather than fixed.

This is written as a failed experiment on purpose. The framework's stated product is *findings, not
automation* (ADR-0006), and a mechanism that ran for five weeks and produced no prevention but
several sharp lessons is exactly that — provided the lessons are recorded before the code goes.

## What it was

Three layers, each in a different trust domain — and **the taxonomy was right and survives this
decision**:

| Layer | Where | Bounds |
|---|---|---|
| 1. the guard | in-band, PreToolUse | *authorization* — may this run commit spend at all |
| 2. `tessera-escalate` | async human gate | what a blocked agent does instead of routing around |
| 3. cloud budget | out-of-band (conclave `budget.tf` → SNS → hardstop lambda) | *blast radius* |

Only layer 1 is retired here. Layers 2 and 3 are untouched, and layer 3 was always the real bound.

## What worked — recorded because it is the part worth carrying forward

1. **Reading one level into invoked scripts caught a genuine hole.** conclave's
   `sweep-gpu-capacity.sh` runs `terraform apply -auto-approve` on line 23; a name-only classifier
   waves it straight through. The generalisable form: **a classifier that reads the command but not
   what the command runs is checking the wrong text.** That lesson outlives the guard.
2. **The invariant `a spend gate must never be able to block the exit`.** Spec 06 as first written
   hard-stopped by rejecting further Bash on overrun — which would freeze an agent holding a live
   GPU and block its own teardown, *causing the runaway it existed to prevent.* Any replacement
   must preserve this. It is the single most important design constraint in the whole area.
3. **The disposition-verb axis (ADR-0016).** *What does the detector's over-firing mean?* Where
   over-firing is designed in, the model filtering it is the architecture; where it is a defect, a
   model-emitted exit is that defect's own bypass. That reasoning is general, was reused by
   ADR-0027 for P13 four weeks later, and survives entirely.
4. **`a test must never become evidence about the thing it tests`.** Twice: 26 manufactured
   `spend_denied` events, then 31 manufactured `spend_dismissed` ones. The second is the sharper
   instance — the containment set an environment variable *nothing reads*, so it ran and reached
   nobody.
5. **Auditing it found real defects in it** — `grant` was agent-callable behind nothing but a
   sentence; five plain-literal launcher bypasses; the backstop's counter at 47. Genuine finds.
   **But note what that sentence actually says: the measured value of this mechanism is that
   inspecting it produced bugs in itself.** That is not the thing it was built for.

## What did not work — the substance of the verdict

1. **It never prevented a real unauthorized spend.** Not once, in five weeks. Every denial for
   which evidence exists was a false positive. The three real holes it is credited with were all
   found by *inspection while testing or auditing it*, never by it firing in anger.
2. **It is a classifier over an unbounded input space that must be correct at the token level.**
   ADR-0028 already conceded this for one sub-case — "the launcher set is every exec-wrapper on the
   system; it cannot be enumerated." That concession generalises to quoting, escaping, heredocs,
   runtime assembly and cloud SDKs. **Shell parsing inside a safety control is a hard problem being
   solved with regexes, and the edge cases do not run out.**
3. **Three review rounds in one day produced two block→allow regressions**, both in fixes for a
   false positive, both invisible to a fully green suite, both found only by an independent
   reviewer diffing classifications. The last was an ordinary **apostrophe** turning a real boot
   into an allowed teardown.
4. **Its false positives land almost entirely on the people maintaining it.** Five in one session,
   a 100% false-positive rate, every one produced by working on or verifying the guard — including
   two hit by the independent reviewer, the tier-3 mechanism ADR-0006 rates highest. **A control
   whose friction falls mainly on its own auditors is obstructing its own verification.** With
   Claude specifically this is not fixable: an agent that writes documentation, tests and ADRs
   *about* infrastructure will trip a text classifier aimed at infrastructure.
5. **It failed OPEN in the way that matters.** On a `/usr/bin`-first PATH it did not parse, exited
   1, and the wrapper passed that through as ALLOW. The guard was itself the vulnerability.
6. **Its backstop shipped disabled to every clone**, silently, for weeks — a global counter at 47
   against a cap of 3.
7. **It needed a detector, which needed a detector.** guard → backstop (does the agent obey the
   denial's prose?) → P15 (is the backstop still alive?). Three layers of watching for a control
   that has never fired in anger, each with its own noise and its own failure modes.
8. **It contradicted the framework's own charter, and nobody re-examined it.** ADR-0006 retargeted
   Tessera to *instrumentation, not control*, ranked "make the bad state unrepresentable" tier 1
   and out-of-band bounds tier 2, put text-matching at tier 4, and warned that every in-band
   mechanism is subject to the same silent failure as the agent it guards. **The spend guard is a
   pre-execution deny gate — control, in-band, tier 4 — and it went on being the flagship safety
   mechanism for five weeks after the charter said to stop building exactly that.** Every failure
   above is one ADR-0006 predicted in the abstract.

## The deeper mistake, stated once

**Layer 1 is a precondition for unsupervised operation, and unsupervised operation never
happened.** ADR-0006 demoted the autonomy roadmap from goal to hypothesis; ADR-0025 declined to
restore the readiness claim. So the mechanism was built, maintained, debugged and defended for a
condition that has not arrived — while imposing real cost every week on the condition that had.

**Build the control when the run that needs it is real, and build it at the tier the charter
already names.**

## What replaces it

**Nothing, here.** Tessera's job under ADR-0006 §3 is *"to ensure they exist, not to be them."*

- **Tier 1, in conclave (where the credentials and GPUs actually are): remove the capability.** An
  agent without provisioning credentials cannot boot a GPU — not "is denied", *cannot*. The
  envelope becomes a **scoped credential with a TTL** issued by a human (STS assume-role), rather
  than permission to pass a regex. Nearly identical UX to `tessera-authorize grant --ttl 4h`;
  entirely different enforcement; no parsing and no false positives.
- **Tier 2, detection: observe effects, not commands.** A GPU either exists or it does not — a
  bounded, enumerable space, unlike the set of strings that might create one. CloudTrail plus the
  existing budget hardstop already covers it.

Neither is built by this ADR, and **that is a real gap, stated rather than implied**: between the
unwind and conclave adopting scoped credentials, there is no per-run authorization layer at all.
The honest weighing is that layer 1's *measured* prevention is zero, so what is lost is nominal
coverage rather than actual — but a reader in six months should not have to infer that.

## Consequences

- **Nominal safety coverage is reduced; measured coverage is unchanged.** Say it in that order.
- **The chaos suite drops from 11 probes to 7.** Probes **1–4** used spend as their vehicle: 1–3 the
  guard, 4 the backstop. Coverage accounting, because "four probes deleted" is not the same claim as
  "four probes' worth of coverage lost": probe 3 asserted the guard parsed under Python 3.9, which
  `safety-scripts-run-on-the-system-python` asserts directly for every member; probe 4 exercised
  `settings.json`'s never-ran branch, which probe 8 covers with a generic, non-spend vehicle. Probes
  1 and 2 are genuinely retired with their subject. ADR-0025 cites "11 of 11" as the evidence that
  spec 11's bar is met — that figure moves, and its *reasoning* is unaffected because the retired
  probes tested a mechanism that no longer exists.

  > **CORRECTED BEFORE THIS COMMIT LANDED, and the error is worth more than the fix.** The first
  > draft of this bullet read "drops from 11 probes to 9 (probes 1 and 2)". Both numbers were wrong,
  > and they contradicted this ADR's own `Executed:` line ("probes 1–4") six paragraphs above and the
  > measured suite result (7 passed) — **in the decision record whose entire subject is honest
  > accounting of what a mechanism cost.** Caught by an independent reviewer, not by re-reading and
  > not by any check: `chaos-probe-count-is-current` compares `bin/tessera-chaos` against
  > `chaos/test_chaos.py` and cannot see a third copy of the figure in prose.
  >
  > Sharper still: the published snapshot of this ADR carried the corrected "11 → 7" while this file
  > carried "11 → 9", so **the off-repo copy was more accurate than the source** — the exact drift
  > that copy was flagged for, arriving within the hour and pointing the other way.
- **P15 goes with it**, which removes one of G-a's two remaining legs.
- **ADR-0016's spend half is retired; its drift half and its central argument stand**, and its
  argument is now load-bearing for ADR-0027 rather than for anything here.
- **conclave keeps layer 3, which is the layer that never failed.**

## Alternatives considered

- **Keep it and stop investing** (ADR-0028's position, one day old). Rejected on re-examination:
  a frozen tier-4 control still costs false positives every session, still needs its two detectors,
  and still contradicts the charter. Freezing reduces the bleeding without addressing the diagnosis.
- **Fix the tokenisation properly with a real shell parser.** Rejected: `shlex.split` already raises
  on a live file here, `bashlex` is a third-party import inside a stdlib-only safety script that
  must run on macOS 3.9 — and it would still be a tier-4 control fighting an unbounded space.
- **Keep the guard, drop only P15.** The cheapest option and genuinely tempting. Rejected because it
  treats the noisiest symptom while leaving the mechanism the charter argues against.
- **Delete layers 2 and 3 as well.** Firmly rejected. Layer 3 is the only mechanism in this
  framework that has never failed, and layer 2 (escalation) is general infrastructure that has
  nothing to do with this diagnosis.

## Re-evaluate triggers

- **A downstream actually runs unsupervised against real infrastructure** → build layer 1 at tier 1
  (scoped credentials), not tier 4. This is the trigger that should have gated the original build.
- **conclave adopts scoped credentials** → the gap named above closes; record it.
- **An unauthorized provisioning event occurs** that a text-matching guard would plausibly have
  caught by mistake rather than evasion → this decision is wrong and should be superseded on that
  evidence.
- Next cadence review: 2026-11-16 (90 days).

---

## References

- ADR-0006 — the charter this mechanism contradicted; tiers 1–5 and "instrumentation, not control"
- ADR-0028 — the scope freeze this supersedes, written one day earlier on the same mechanism
- ADR-0016 — the disposition-verb axis, retired here for spend and reused by ADR-0027
- ADR-0005 — promoted spec 06 to Tier 1; that promotion is amended, not the Tier-1 reordering
- ADR-0025 — cites the 11-probe figure this changes
- `docs/contracts/spend-authorization.md` — the full design, harvested above before removal
- `_project_specs/06-cost-budget-awareness.md` — the originating spec
