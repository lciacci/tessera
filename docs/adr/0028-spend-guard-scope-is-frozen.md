# ADR-0028: The spend guard's evasion enumeration is frozen — and its tokenisation was fixed, measured, and reverted

- **Date:** 2026-08-18
- **Status:** Superseded by ADR-0029
- **Superseded because:** one day later the mechanism itself was retired. This ADR froze the
  scope of a control ADR-0029 removed entirely — its diagnosis (tier 4, unbounded input space,
  buy safety at layer 3) was right and became the argument for retirement rather than for a
  freeze.
- **Decision driver:** Human disposition. Lorenzo, on queue item 1: *"do 1 and 2"* — fix the
  tokenisation, then declare layer 1 finished at "stops the honest mistake" and stop growing the
  pattern list. After three review rounds measured the fix as a net safety regression, the
  recommendation to revert §1 and keep §2 was put to him and accepted: *"go with the rec."*
- **Executed:** 2026-08-18 — `scripts/spend/test_segments_known_ceilings.py` (the pinned
  ceilings), `docs/contracts/spend-authorization.md`. **`scripts/spend/guard.py` is deliberately
  UNCHANGED** — that is the decision, not an omission.

> **This ADR was drafted, measured against, and rewritten before it was ever committed.** The
> immutability rule protects decisions in the record; this one had not entered it. Its first
> draft asserted the tokenisation was fixed. Recording that here rather than quietly shipping the
> second draft, because the gap between the two is the finding.

---

## 1. The tokenisation defect: real, and NOT fixed

`_segments()` splits on shell separators **before** `_classify_one` strips quoted spans. A quoted
span containing a separator is torn into fragments carrying **unbalanced quotes**, which `QUOTED`
can no longer match, so text sitting safely inside quotes reaches `COMMITTING`:

```
grep -E "terraform apply|aws ec2 run-instances" notes.txt
  ->  ['grep -E "terraform apply',  'aws ec2 run-instances" notes.txt']
                                     ^ unbalanced, unstrippable, DENIED
```

Five denials in one session, **every one a false positive**, and one open blocking escalation
(`esc-20260816-025221`) whose whole subject is that the agent could not disposition them.

### The fix was attempted over three review rounds and produced two fail-opens

| round | change | what it broke |
|---|---|---|
| 1 | quote-aware split | a wrapper *after* a separator stopped being caught — the naive tear had been catching it **by accident** (`make build && eval "terraform apply; ls"`: committing → neutral, **ALLOW**) |
| 2 | test `WRAPPER` per segment | three new false positives, including denying a heredoc that merely *documents* the guard |
| 3 | — | an ordinary **apostrophe** plus a teardown token classifies the whole command `reducing`, which is allowed **unconditionally** |

Round 3's finding is the one that decided it:

```
echo don't run terraform destroy || terraform apply     committing -> reducing   ALLOWED
echo it's done; terraform destroy; terraform apply      committing -> reducing   ALLOWED
```

A quote-aware splitter will not split while a quote is open, so an apostrophe swallows the rest of
the command; `_classify_one` checks `REDUCING` **first**, so any teardown token in the swallowed
span shadows the real boot after the separator. **`echo "don't forget to terraform destroy";
terraform apply` is not adversarial input. It is Tuesday.**

### Why revert rather than patch again

1. **The defect is the SAFE direction.** A false positive denies read-only work. It never allows
   spend, and a human `dismiss` verb now exists for it (ADR-0016, first real run 2026-07-27).
2. **Every fix was the UNSAFE direction** — two distinct block→allow regressions on the one
   control ADR-0005 calls a precondition for unsupervised operation.
3. **A green suite proved nothing, three times.** All four in-repo suites passed through both
   fail-opens. Each was found only by an independent reviewer diffing classifications against the
   original — the tier-3 mechanism ADR-0006 rates highest, doing the job no test did.
4. **Correct tokenisation needs a real shell parser.** The contract had already measured
   `shlex.split` raising `No closing quotation` on a live file. Three rounds of a hand-rolled
   state machine inside a deny-by-default control is the wrong instrument for a known-hard
   parsing problem.
5. **Reverting is what §2 says to do.** This is a tier-4 detector; §2 concludes safety should be
   bought at layer 3, not by lengthening a regex. Continuing to patch would contradict the freeze
   written in the same document.

Three genuine improvements are given up with it (`echo … | sh`, `cd /x && eval "…"`, and the
wrapper-after-separator case all became *caught*). Each was an accident of the rewrite rather than
its goal, and each is a **new pattern**, which §2 declines.

### What ships instead: the ceilings are pinned

`scripts/spend/test_segments_known_ceilings.py` asserts what the guard gets **wrong**, on purpose
— three false-positive classes (quoted alternation, wrapper-led heredoc, and *invoked-script
contents*, catalogued this session when a probe file was denied for the strings it merely listed)
and two known holes. Plus one forward-facing guard, `test_an_apostrophe_must_never_turn_a_boot_
into_a_teardown`, so the regression that ended this attempt cannot arrive unnoticed in the next.

**Harvest before you cut** (ADR-0007): the reasoning survives as executable assertions rather than
as a deleted branch. If one of those tests starts failing, somebody has changed tokenisation, and
this section is what they must read first.

## 2. The posture: what stops growing, and what does not

ADR-0006 ranks mechanisms 1–5 and requires each to declare its tier. Command-text matching is
**tier 4** — a channel that works until it doesn't and then manufactures false confidence. The
contract has already measured that its evasion enumeration cannot terminate: five launcher forms
were closed on 2026-07-27 and **seven more passed immediately** (`script`, `stdbuf`, `nohup`,
`time`, `nice`, `xargs`, `script … python3 …`).

**Layer 1's scope is declared closed at: *stop an agent that commits spend by mistake or without
authorization.*** It is not, and will not become, a control that defeats an agent trying to evade
it — that agent has easier routes, and **layer 3 (the out-of-band cloud budget → SNS → hardstop)
is the only mechanism in this framework that has never failed.**

| | frozen? | why |
|---|---|---|
| **The launcher / evasion enumeration** | **FROZEN** | Measured unbounded. Each addition buys one form and implies coverage of a class that cannot be covered. New forms are recorded as ceilings. |
| **The `COMMITTING` boot verbs** | **NOT frozen** | The covered class must stay *enumerable* — the condition under which "does not cover X" is a ceiling rather than a hole. A new provisioning verb is a member of the claimed class, and still a bug. |
| **Tokenisation** | **FROZEN as of this ADR** | Not for lack of a defect, but because three attempts made it less safe. Reopens only with a real parser (§3). |

That distinction is the contract's own rule turned on itself: *a ceiling is a class you decided not
to catch; a hole is a member of the class you claimed to catch, and a hedge phrased broadly enough
launders the second into the first.*

## 3. What this does NOT decide

**Whether a tier-1 or tier-2 form exists**, which ADR-0006 says to ask before investing further in
a tier-4 detector. Nobody has found one; `isatty()` was tried and defeated (`script -q /dev/null`,
`pty.spawn`). Layer 1 is a useful, bounded, **known-incomplete** authorization check and the real
bound lives elsewhere.

**And a datum for that question arrived while writing this.** Five denials this session, a **100%
false-positive rate**, and every one produced by *maintaining or verifying the guard itself* —
including two hit by the independent reviewer. The population paying layer 1's false-positive cost
is almost entirely the people auditing layer 1. A control whose friction lands mainly on its own
auditors is one arguing for its ceiling to be respected rather than raised.

## Verification

| Probe | Result |
|---|---|
| `git checkout scripts/spend/guard.py` | old vs new classification identical on all 8 probe cases — clean revert ✓ |
| Apostrophe + teardown token | `committing` — the fail-open is gone with the fix that caused it ✓ |
| The original false positive | `committing` — still denied; this is the accepted ceiling ✓ |
| `scripts/spend` suite | 136 passed (11 of them now pinning ceilings) ✓ |
| `bin/tessera-test` | green |

The measurement that produced the revert is itself worth recording: **the first old-vs-new probe
was wrong.** It substituted only `_segments`, leaving round 2's per-segment `WRAPPER` widening in
place, so its "before" column was not the before — and it under-reported two of the three findings.
Beside the change, not in it: the same error the re-plant discipline exists to catch, committed
while measuring whether to trust a reviewer.

## Alternatives considered

- **Keep patching (round 4).** Rejected on the trend: three rounds, two fail-opens, severity not
  falling. ADR-0026's stop signal is a round that catches nothing live; this was the opposite.
- **Ship the fix and accept the apostrophe case.** Rejected outright — it is trivially reachable by
  accident and silently disables the gate.
- **A real shell parser (`shlex`, `bashlex`).** The only correct fix. Deferred, not rejected:
  `shlex.split` already raises on a live file here, and `bashlex` is a third-party import inside a
  stdlib-only safety script that must run on macOS 3.9. Reopen with §3's trigger.
- **Narrowly special-case the `grep -E "a|b"` shape.** One more pattern, which §2 declines, and it
  would not have caught the other two false-positive classes.
- **Remove layer 1 and rely on layer 3.** Tempting under ADR-0006's ranking; rejected because layer
  3 is a *monthly* cap that bounds damage without deciding whether a specific boot is authorized.

## Re-evaluate triggers

- **A real shell parser becomes available** to a stdlib-only script on 3.9 → tokenisation reopens,
  and the pinned ceilings become its acceptance tests.
- **A false positive blocks work that is NOT guard maintenance.** Today's population is the
  auditors; if ordinary work starts paying, the trade changes.
- **Any pinned ceiling test starts failing** → tokenisation changed; this ADR is the prerequisite
  reading.
- **A spend-committing command runs that this guard should plausibly have caught, by mistake
  rather than evasion** → a hole in the claimed class, and §2 reopens.
- **A new provisioning verb enters use** → add to `COMMITTING` with a regression test; the freeze
  does not cover that.
- Next cadence review: 2026-11-16 (90 days).

---

## References

- `docs/contracts/spend-authorization.md` — the three layers, and the enumeration measured as a treadmill
- ADR-0006 — the tier ranking, and "before building a detector, ask what would make the state unrepresentable"
- ADR-0016 — self-authorization refused, and the human `dismiss` that disposes these false positives
- ADR-0005 — spend promoted to Tier 1; why layer 1 exists at all
- ADR-0026 — the review-round stop signal this decision applied
- `docs/observatory.md` → "The spend guard blocks the command that would audit it" · "The spend guard matches command TEXT"
