# Active Focus

Declared current priority for Tessera framework dev. One focus at a time.

**Read this top section, run `tessera-watch`, and you are caught up.**

---

## Handoff — pick up here (2026-07-27 FULL SESSION: four safety mechanisms were silently dead — the spend backstop at 47 against a cap of 3, `tessera-authorize grant` callable by the agent, the SessionStart reporters unable to report their own runner dying, and iCPG's detector scoring the emptiness of its own graph. All four fixed and guarded. ADR-0016 and ADR-0014 decided; review is now Claude-only by decision, not by drift)

*(Load-bearing heading — `.claude/scripts/tessera-watch-surface.sh` greps it at SessionStart.
Newest section carries it; doccheck `handoff-heading-is-current` guards the ordering.)*

### THE ONE THING TO KNOW

> ### ⚠ FOUR SAFETY MECHANISMS WERE DEAD AT ONCE, AND EVERY ONE LOOKED HEALTHY.
> Not a theme imposed afterwards — each was found separately, by *running* something:
>
> 1. **The spend backstop had been dead for weeks.** `.spend-backstop-fires` was a global
>    integer nothing reset; `main()` returns 0 past `MAX_FIRES` (3). Found at **47**. The cap
>    was not wrong, its SCOPE was — written for one session, stored for all time, it became a
>    kill switch. **The test suite is what killed it:** every `tessera-test` wrote four real
>    `spend_denied` events (a test drove the guard hook as a subprocess, which inherits
>    `CLAUDE_CODE_SESSION_ID`), each bumping the counter at the next Stop.
> 2. **`tessera-authorize grant` was callable by the agent.** Driving the real hook returned
>    **rc=0**. No tty check; `granted_by` is `$USER` whichever party typed it. The
>    deny-by-default control on external spend had a self-authorization path held back only by
>    a sentence in its own contract. **Now refused unconditionally** (ADR-0016) — PreToolUse
>    fires only on the agent's Bash calls, so a deny-list entry is real enforcement.
> 3. **The SessionStart reporters could not report their own runner dying.** `rm
>    bin/tessera-watch` → a completely normal handoff printed, while P3/P4/P9/P11–P15 all went
>    quiet at once. The `settings.json` trailing branch reports a hook SCRIPT missing; it cannot
>    report a hook that ran perfectly with its RUNNER gone.
> 4. **iCPG's detector scored the absence of edge types nothing writes** — `test(0.30)` constant
>    on 712 of 712 events. Shrunk 6 dimensions → 3.
>
> **THE COMMON SHAPE, and it is the thing to carry: none of these produced an error. They
> produced ordinary-looking success.** A dead backend reads as an unused one; a crashed watcher
> reads as a quiet one; a constant reads as a measurement; an uncapped counter reads as a
> disabled-for-good-reason one.
>
> **AND THE METHOD THAT FOUND THEM ALL: running something, never re-reading it.** Four findings
> today were in code written earlier the *same day* — the falsifier's PARTIAL on my own guard,
> the chaos probes' wrong first draft, the A5b probes, and a malformed-row crash found in
> review. **Counting would have found none of them:** all three surfacers had ZERO
> `tessera-degraded` calls, the exact signal the 07-26 audit misread three times.

**START HERE — read "Next — in priority order" below; it is the live list.** Most of the
2026-07-26 backlog closed today.

> ### ▶ NEXT SESSION: two instructions, both deliberate
>
> **1. Run `/compact` EARLY, before the work — not at the end.** Requested 2026-07-27. Layer 3 of
> the compaction-recovery path has **n=0 and carries two unexercised fixes** (the 07-24
> `additionalContext` channel fix and the 07-26 TTL fix); all 5 logged events predate both.
> Compacting into a wrap-up tests the plumbing and teaches nothing about sufficiency — do it with
> real work still ahead, and watch for the `CONTEXT RESTORED AFTER COMPACTION` block **actually
> arriving**, which has never once been observed. Full reasoning further down under "WORTH DOING
> EARLY".
>
> **1b. P13 will be red, and it is CORRECT — do not snooze it.** Two `degraded` events from
> 2026-07-27 (`spend-guard/deny-list-bypassable`, `.../self-authorizing-deny-list-bypassable`)
> record a real degradation: the deny list ADR-0016 called unconditional was bypassable by five
> plain literals. The remedy shipped the same day and is *partial by design* (the launcher tail is
> open and documented in the contract). The events are true, the fix is real, and they age out on
> their own in 7 days. **Snoozing a true signal because it is inconvenient is the one thing the
> predicate exists to prevent.** G-a will clear with it — P14 was the other half and is already
> fixed (`./install.sh` shipped `icpg-inject-context.sh` to the global tier).
>
> **2. Item 1 is the iCPG extractor, and it has a BINDING STOPPING RULE.** Read item 1 before
> touching it. The question has been re-scoped three times and decided zero; the rule is one
> bounded change, one re-measurement, then a decision either way — explicitly including
> retirement. **There is no step 3.** If the extractor work surfaces another cause, that is a new
> observatory entry, not a fourth re-scope of item 1.

**Afternoon of 2026-07-27 (same session, continued):** the spend guard's deny list was found
**bypassable by five plain literals** (`python3 bin/tessera-authorize grant` and friends) one day
after ADR-0016 declared it unconditional — fixed, and the launcher enumeration measured as a
treadmill (7 more forms pass). `tessera-authorize dismiss` **ran for the first time**, closing all
three of ADR-0016's open triggers. Effort-vs-cache **measured**: effort invalidates like `/model`,
refuting the inference that it was the cheap knob. The `CLAUDE_EFFORT` statusline flag was
proposed and **declined** — recorded as declined, not unbuilt. `verdict_channel` shipped in
`tessera-verify stats` (4 file / 16 unrecorded / 0 message). And the first non-bootstrap iCPG
ReasonNode was authored, which is what surfaced item 1's real cause.

  - **CLOSED 2026-07-27:** **A6** (one check shipped, two rejected on measurement), **A5b** (the
    reporters could not report themselves), **C** (iCPG — shrink, dedup, evidence, and the
    `usage` question answered), **D** (ADR-0014 — review is Claude-only, the stack cut).
  - **STILL OPEN:** **B2** (blocked on unbiased labels — the block is the finding), **E /
    item 2 Part B** (the pending-record channel, needs its 3-decision design gate), and iCPG
    **scope quality**, which is what the `usage` question turned into.
  - **A-live/T2 has its first receipt, and it is `insufficient`** — and the defect it named is
    already fixed (`detect_git_commit` parsed the shell instead of asking git). **Watch whether
    later receipts stop naming `progress`**: that would be the first finding → fix →
    instrument-goes-quiet loop this repo has closed.
  - ~~usage thresholds are uncalibrated~~ — **ANSWERED, and it was not a threshold question.**
    Measured: 46% score zero, 34% below the cut, 19% fire — the threshold discriminates. The
    real defect was definitional (a symbol's own file counted as usage outside its scope; fixed)
    and what it exposed was **scope quality**: only 42% of tracked files sit in any reason's
    scope. See **C** and priority item 1, which is pre-scoped into three options.

*(This block contradicted the priority list until it was re-read at session end on 2026-07-27 —
the fourth instance of index-vs-body drift in this file in two days, and the exact reason A6
concluded that shape needs a human re-read rather than a check.)*

### Standing patterns

*(Load-bearing heading — `.claude/scripts/tessera-watch-surface.sh` prints this block at
SessionStart; doccheck `standing-patterns-are-surfaced` guards it. These are the lessons this
repo has paid for MORE THAN ONCE. They are cross-cutting, so no ADR owns them and no
file-anchored surfacer can find them — that is exactly why they are printed verbatim.
Add a line only when a lesson recurs; the value is that the list is short enough to read.)*

1. **A component ships, and the thing that would tell you it is broken is also broken.**
   Instances: F-001's interpreter, the dead ingest pipe, the falsifier's swallowed spawn
   failure, P4 counting projects not bytes, `tessera-hooks status` advertising a drift check
   it never ran, the fleet on a retired gate vocabulary, twelve hooks silently no-op'ing on a
   wrong cwd, the anchor fix that would have cd'd the global tier to `$HOME`, and the
   decision-surface hook — built to defeat this exact pattern — shipped silent by it (2026-07-24),
   and the spend backstop, whose own global fire-counter sat at 47 against a cap of 3 so it had
   returned "nothing to report" on every session for weeks (2026-07-27).
   **Before shipping a check, ask what would tell you the check itself died.**
   **Sharpened 2026-07-27:** a guard written for a bug and tested against that same bug is
   verified against ONE example. `drift-dimensions-have-producers` passed its own tests while
   blind to two of the three dimensions that motivated it; only `bin/tessera-verify`, given the
   claim explicitly, found it. **Test a new check against the failures you did NOT just fix.**
   **And its purest instance to date, A5b (2026-07-27): `rm bin/tessera-watch` and SessionStart
   printed a completely normal handoff.** Every predicate — P3, P4, P9, P11–P15 — went quiet at
   once, because the reporter for all of them WAS the thing deleted. The `settings.json` trailing
   branch could not cover it: that reports a hook SCRIPT missing, never a hook that ran perfectly
   with its RUNNER gone. Fixed in three surfacers, guarded by chaos probes 9–11.
2. **It did not break — it produced something plausible.** The fail-open class. A mechanism
   that fails open needs a paired signal that fails LOUD. Proven again 2026-07-24: a
   *wrong* error message was the only reason a session-wide cwd bug surfaced, while twelve
   correct-looking `exit 0`s said nothing. Spec 11 is the systematic answer. Again 2026-07-26:
   `gate/ratio.py` from a foreign cwd printed a clean, well-formatted report of ZERO gates over
   ZERO sessions — the anchored run reports 27/142/1039. A read path that fails open does not
   look broken, it looks like good news.
3. **Name the pain, not the artifact that correlates with it.** Three retired proxy
   predicates so far: retired-P2 (verb count), old-P4 (project count), the sqlfluff trigger
   (file existence). If a predicate measures a stand-in, it will fire correctly and mean
   nothing. **Now scored against the auditor twice** — the `grep -c degraded` count that
   produced three wrong spec-11 findings (2026-07-26), and "the chaos suite lacks a conftest"
   (2026-07-27), which was confidently proposed, was WRONG (chaos measured clean), and was
   refuted only by probing each suite and watching which one wrote to the journal.
   **When auditing, measure the property. Counting the artifact is the same error you are
   auditing for, aimed at yourself.**
   **Corollary, from A6 (2026-07-27): a mechanical check needs a mechanical SUBJECT.** Two of
   three candidate handoff checks were rejected on measurement — "a closed entry must name an
   existing path" scored 12 false positives in 13, and "an item closed in the index must be
   struck through in its body" FAILED OPEN, because the prose format it keyed on was invented one
   day and the next section did not use it. Retired figures are a closed list of exact strings and
   shipped; "is this status consistent" is a judgement wearing a regex. **When the subject is
   authored prose in an unenforced format, the honest answer is a human re-read, not a check.**
4. **An interpreter is a path, not a name** (F-001). Generalises past interpreters: any
   NAME resolved through a mutable, ordered lookup — `python3`, a `tessera-*` binary on
   PATH, a bare relative hook path against an inherited cwd — is a landmine.
5. **Ship both halves or neither** — and note that this is violated by TIME as often as by a
   missing `cp`. The fleet went stale with every component correctly installed.
6. **Green is only meaningful if failing it actually stops something.** P8 alone let a red
   commit through; the pre-commit hook is what made doccheck load-bearing.
7. **A test is never evidence about the thing it tests.** Manual `/compact` cannot validate
   the compaction-recovery layer; P3 counts only non-manual events.
8. **Never subtract from a knowledge artifact you have not read. Harvest before you cut**
   (ADR-0007). Code has grep and tests as safeguards; prose has neither.
9. **A mechanism that RUNS has not necessarily REACHED its audience.** Verify the delivery
   channel, not just that the code produced output. A PreToolUse hook's stdout goes to the
   debug log, not the model — `decision-surface`, `mnemos-pre-edit`, and Layer-3 compaction
   recovery all "ran" while silent to the model. Self-testing proved they *produced* text;
   only review and the docs proved the harness *delivered* none of it. Test the real path to
   the real audience, and let an independent reviewer check what you didn't think to.
   **Now proven against the falsifier itself (2026-07-26):** `bin/tessera-verify` did the whole
   job — planted landmines, executed, reverted — and then its OWN `verify-scan` Stop hook fired,
   and that skip acknowledgment became its final message, which is what `parse_verdicts` reads.
   0 usable verdicts in 3 real attempts. The channel was eaten by the backstop the tool belongs
   to. **Corollary worth its own sentence: a verdict returned as a MESSAGE can be overwritten;
   a verdict written to a FILE cannot.** Acted on same day — the verifier now writes
   `tessera-verdicts.json` and a live self-test came back `verdict_channel: "file"`. Note the
   fix's own near-miss, which is the pattern one layer down: the worktree builder copies
   untracked files IN, so a stale verdict file would have been read as this run's answer —
   a false CONFIRMED from a verifier that wrote nothing. **When you move a channel, ask what
   else can write to the new one.**

### Next — in priority order

**CLOSED 2026-07-27:** items 1–5 of the earlier list, item 8's design gate (ADR-0016), item C,
item D (ADR-0014), A5b, A6 — and the `usage` calibration question, which turned out not to be a
threshold question at all (see **C** above: the defect was definitional, the exposed problem is
scope quality, and the re-stated question is recorded there). What is actually next:

1. ~~**iCPG corpus coverage — item 1's THIRD scope.**~~ **CLOSED 2026-07-27 — ADR-0017.** The
   stopping rule was followed and its *retire* branch fired. Step 1: extractor extended to `.sh`
   and shebang-based extensionless files, corpus **84 → 261 of 261** code files. Step 2: over
   6468 CREATES-linked symbols `usage` fired 986× and the top firers were `ok`/`run`/`err`/`ev`/
   `read`/`check` — `git grep --fixed-strings` matches **substrings**, so `ok` hits "hook". It
   scored name commonness, not usage. The word-boundary rescue was tested *before* retiring and
   failed. **No step 3 was taken**: the two side-findings (46 of 78 shell files have zero symbols;
   `icpg create` cannot hand-author contracts) went to their own observatory entry, "Is the SYMBOL
   the right unit for a shell-heavy repo?". Drift is now `changed` + `decision`.

   **One loose end, deliberately not swept — needs a call.** 205 drift events are still open and
   165 involve the retired dimension. ADR-0016 §3 makes drift `dismissed` model-emittable, so the
   **136 `["usage"]`-only rows** can be dismissed citing ADR-0017. The **29 `["changed","usage"]`
   composites must not be** — dismissing those silences a live `changed` finding. Correct order:
   re-scan first (the dedup key includes `sorted(dimensions)`, so the `changed` half re-raises as
   its own row), *then* dispose the stale composites. The 40 `["changed"]` rows are untouched and
   still valid.

   *Original entry, kept for the trail:*

   **The (a)/(b)/(c) options below are RETIRED. Do not score them.** They asked how to handle
   scopes whose symbols don't match, and on 2026-07-27 the cause turned out to be one level down:
   **`symbols.py` dispatches on file extension, `.sh` and extensionless files are not in
   `LANG_MAP`, and iCPG therefore sees 84 of 260 code files — 32% of the repo.** 46 of 56 scope
   entries point at files it cannot parse; three point at files it can. The "46% incoherent"
   figure follows mechanically from scopes naming files that can never hold a symbol. See
   `docs/observatory.md` → "iCPG cannot see 68% of this repo".

   **THE STOPPING RULE — binding, because this question has been re-scoped three times
   (thresholds → scope quality → corpus coverage) and decided zero times.** Each deferral was
   evidence-driven and correct; collectively they are a regress that will otherwise produce a
   fourth.

   - **Step 1 — ONE bounded change.** Extend `LANG_MAP`/`detect_language` to cover `.sh` and
     shebang-based extensionless files, re-bootstrap or re-record, re-run drift. Bounded: extractor
     only. Do **not** widen it into "and also fix scopes / contracts / the CREATES edge set."
   - **Step 2 — DECIDE, on that one measurement.** Does `usage` discriminate over a corpus that
     includes the framework's own code? If **yes**, keep it and close item 1. If **no**, RETIRE it
     — `design-principles.md:459`'s kill test ("does drift detection catch things grep wouldn't?")
     has then been asked against a fair corpus and answered.
   - **No step 3.** If step 1 surfaces a further cause, that is a *separate observatory entry*,
     not a re-scope of item 1. **A dimension that has consumed three investigation cycles without
     producing a signal has had a fair hearing; the honest close is retirement, not a fourth
     look.** Retiring leaves `changed` + `decision`, and `decision` fires zero — read that as the
     real cost before choosing, but do not let it buy another cycle.

   **This IS the decision ADR-0013 deferred, and that matters twice over.** ADR-0013 logged
   *"retiring iCPG's dimensions is a bigger decision than this ADR should make"* and *"Retiring it
   is a separate decision needing its own evidence"* — so the rule above is not a new question, it
   is the staged close of an already-open one, with the evidence ADR-0013 said it needed.
   **It also removes the main objection to retiring:** ADR-0013 already records the candidate
   replacement — scryer's two deterministic predicates ("this file changed since we last
   reconciled it"), marked *idea-only, open*. So the retire branch does not leave a hole; it leaves
   `changed` + `decision` **plus a documented alternative to evaluate**. Standing pattern #3 is the
   reason to prefer it: a weighted composite is a proxy, "this file changed" is the pain.

   **Second finding from the same run, tracked separately (do NOT fold into the rule above):**
   `icpg create` has no flag to hand-author contracts. `--infer-contracts` needs an LLM key and
   otherwise degrades to scope-restated-as-`file_exists()`; `preconditions`/`postconditions` come
   back empty. `design-principles.md` names hand-authoring as the first of three tiers and it is
   unreachable. Small, self-contained, and independent of the `usage` decision.
2. **Item 2 Part B — the pending-record channel (framework→downstream).** Needs its 3-decision
   design gate before any code: where the record lives, idempotent-update semantics, the
   committed staleness marker.
3. **B2 — correction recall.** BLOCKED on labels from a judgement that did not propose the
   hypothesis. The block is the finding, not an obstacle to route around.
4. **`tessera-authorize dismiss` has NEVER RUN — it needs both PERFORMING and INTERROGATING,
   and they are different tasks.** ADR-0016 built it 2026-07-27; `spend_dismissed` is at
   **n=0**, while **22 genuine false positives** sit in that session's log (16 pytest fixtures,
   6 probes of the new guard).
   - **PERFORM.** A human runs it — the agent structurally cannot, which is the enforcement
     working as designed:
     `tessera-authorize dismiss --reason "test fixtures and guard probes; no spend attempted"`.
     That clears the journal *and* exercises the verb for the first time.
   - **INTERROGATE — the human path has never been tested end to end.** The deny-list was
     verified from the agent side (rc=2 through the real hook) and `undispositioned()` from unit
     tests, but **nobody has run it from a terminal and watched the backstop go quiet.** An
     untested path is the fail-open class, and by construction the agent cannot close this gap.
     When it runs, check three things: does the backstop actually go silent afterwards; does the
     event carry `dismissed_by`; did blocking the agent break the human?
   - **THE NOT-VACUOUS QUESTION, the same shape as T2's.** If false positives keep accruing and
     nobody reaches for the verb, *"it works"* and *"it is decorative"* stay indistinguishable,
     and the honest reading becomes that the prose exit was adequate and ADR-0016 over-built on
     this half. **That is a legitimate thing to discover, not a failure.**
5. **Minors:** `tessera-verify stats` does not break out `verdict_channel` (now 2-for-2 on the
   file channel, so the number is worth surfacing); a drift that STOPS drifting is never closed
   (recorded in C — needs a disposition decision, not a patch); concept-tags for the decision
   surface; historical `--reclassify --all`. *(`rm -rf scripts/.tessera` — already gone,
   verified 2026-07-27.)*

**Passive, needs no action:** T2 restore receipts accrue at ~0.8/day. Watch whether later
receipts stop naming `progress` now that `detect_git_commit` asks git instead of parsing the
shell — that would be the first finding → fix → instrument-goes-quiet loop this repo has closed.

**WORTH DOING EARLY IN A SUBSTANTIVE SESSION — a hand-run `/compact`, for ONE reason.**
Asked at the end of 2026-07-27 and deliberately NOT done then; the answer is timing, not no.
- **It buys nothing for the trial.** ADR-0015 established the restore path is not
  compaction-specific (it runs on every session start, ~121 times vs ~3 compactions), T1 is
  guarded by P3 and green, T3 is blocked by the empty PreCompact payload, and **a hand-run
  compact is a TEST of the layer, never evidence about it** (standing pattern #7).
- **It buys exactly one thing: Layer 3 has n=0 and carries TWO unexercised fixes** — the
  2026-07-24 `additionalContext` channel fix and the 2026-07-26 TTL fix (its 300s staleness gate
  used to delete the marker and emit nothing). The log shows 4 `restore_injected` and 1
  `restore_missed_stale`, **all of them from before those fixes**. Nothing has tested them.
- **Do it EARLY in a session with real work ahead**, not at the end: compacting into a wrap-up
  restores into nothing to resume, so it tests the plumbing and teaches nothing about
  sufficiency. Watch for the `CONTEXT RESTORED AFTER COMPACTION` block actually arriving —
  that text has never been observed reaching the model, once.

**A LATE-SESSION CATCH, and it is the lesson more than the fix.** The fleet was rolled at
`c405645`, then **A5b landed three commits later (`e0054a7`) and was not re-rolled** — so all
five downstreams sat on a `tessera-decision-surface.sh` that could not report its own crash,
for the rest of the session. Found by *diffing the fleet*, not by remembering. **Standing
pattern #5: ship both halves or neither, violated by TIME as often as by a missing `cp`** —
and the window here was three commits, not three weeks. Rolled and pushed (conclave `500af03`,
heaviside `c989bc2`, settempo `c4c3c96`, tess-dashboard `488a0fc`, howler `5e57c16`).
**The durable question this raises and does NOT answer: nothing tells you the fleet is behind
except a human running `tessera-sync-harness` by hand.** P4 measures downstream against the
GLOBAL tier, not against this repo — so it reads "in sync" while the fleet is behind tessera
itself. That is the same reference-validation hole P14 was built to close one tier up, still
open one tier down.

**Standing caution for whoever picks this up:** five of today's findings were in code written
earlier the same day, and every one came from RUNNING something rather than re-reading it — the
falsifier's PARTIAL, the chaos probes' wrong first draft, the A5b probes, the malformed-row crash,
and the `usage` own-file bug. **Self-review that executes nothing is the weakest instrument here.**

### T2's first real receipt: `insufficient` — and the checkpoint has a concrete bug

The backstop fired on a genuine Stop (165 turns, 23 edits). Verdict `insufficient`, missing
`progress`. Three defects, one of them mechanical and fixable:

1. **`progress` is CORRUPTED, not thin.** "Progress So Far" listed `$(cat <<` eleven times and
   `$MSG` three times where commit subjects belong — `write_checkpoint`'s progress extractor is
   capturing heredoc and variable fragments out of shell command text. **That is a real bug with
   a real address**, and it is exactly what T2 was built to surface.
2. **`goal` was stale and actively misleading** — it named a prior session's objective ("Spec 11,
   success criterion 5") plus `+90 older goal(s) omitted`. A wrong goal is worse than none.
3. **`key files`** named `restore-receipt.md` and `mnemos/SKILL.md`; the session touched
   `scripts/icpg/`.

**The receipt is evidence FOR the selection bias the 07-26 handoff flagged.** Orientation came
from THIS FILE and the standing-patterns block, not from the checkpoint — the checkpoint was
bypassed, not used. A downstream app has no such file. Do not read tessera receipts as a general
verdict on Mnemos.

### `bin/tessera-verify` is now 2-for-2 on the file channel, and it refuted me

Three claims went to the falsifier: **CONFIRMED / PARTIAL / CONFIRMED**, `verdict_channel: "file"`.
The PARTIAL was correct and cost a follow-up commit (`fd47631`):

- The new runtime guards catch a re-added `test` dimension but **not `dependency`** — a dimension
  scoring the **absence** of an edge fires on every symbol and is caught by observation, while one
  scoring the **presence** of a never-written edge returns `None` forever and never reaches the
  output. Testing emitted dimensions cannot see the second kind.
- **`ownership` was caught by NEITHER guard** — it read edges **untyped**, so it named no edge
  type and the producer scan saw it consuming nothing. A hole in the check shipped one commit
  earlier.

**The shape: I wrote a guard, tested it against the failure I had just removed, and it passed
while blind to two of the three dimensions that motivated the work.** Caught within the hour only
because the claim was stated explicitly enough to falsify. *A check verified against the bug you
remember is verified against one example.*

Suite green (362 top-level, 101 spend, 32 icpg, **11 chaos**), doccheck **34/34**, `tessera-watch`
fires zero (P7 snoozed), findings backlog empty, no escalations. **Five commits, NOT PUSHED.**

---

## ═══ SESSION 2026-07-26 (FULL SESSION: the Mnemos trial was watching the wrong event — re-scoped in ADR-0015, P3 rewritten, T2 BUILT with zero receipts; SIX fail-opens found and fixed incl. a spend gate a `cd` could switch off; ADRs now record whether they were ever BUILT; correction-recall premise was a bad denominator)

*(Load-bearing heading — `.claude/scripts/tessera-watch-surface.sh` greps it at SessionStart.
Newest section carries it; doccheck `handoff-heading-is-current` guards the ordering.)*

### THE ONE THING TO KNOW

> ### ✅ COMPACTION TEST RAN (2026-07-26). The trial was watching the WRONG EVENT — ADR-0015.
> The `/compact` was run. Both layers failed, for two independent reasons, both now fixed
> (`6577f7c`). Then the diagnosis invalidated the trial's premise, which is the bigger result.
>
> **WHAT THE TEST FOUND**
> 1. **Layer 2 delivered, then truncated.** All 13 sections were produced (18,248b), but the
>    harness spilled it to a file and handed the model a **2KB preview** — the goal blob arrived,
>    Constraints / Progress / Key Files / Git State did not. Cause: `checkpoint.py` joined every
>    active GoalNode unbounded (goals are never-evict AND one is minted per ingested session) →
>    **98 nodes / 11,119 chars, 60% of the checkpoint.** The restore blob outgrew its own delivery
>    channel. Capped to 8 most recent: **11,119 → 872 chars, −92%.**
> 2. **Layer 3 never injected. Still n=0, ever.** Its 300s staleness gate tripped at 33 min,
>    **deleted the marker, and emitted nothing** — the restore destroyed by its own freshness
>    check. The gate also guarded the wrong thing (injected text is read live from
>    `checkpoint-latest.json`, so marker age never implied stale content). TTL now 24h, and the
>    stale path now speaks instead of exiting silent.
> 3. **The global hook tier was two days stale and missing a hook entirely** — `~/.claude/templates/`
>    had **zero** `additionalContext` in all three PreToolUse hooks, so the whole fleet ran Layer 3,
>    fatigue/intent, and decision-surface into the debug log. `./install.sh` fixed it; **nothing
>    detects it** (item 4).
>
> **THE RESULT THAT MATTERS — the premise was false.** `mnemos-session-start.sh` gates on nothing
> but the checkpoint file existing, so the restore path runs identically on `startup`, `resume`,
> and `compact`: **541 checkpoints, 121 sessions, ~3 compactions.** The mechanism did not run 3
> times — **it ran ~121.** P3 counted the rarest trigger (~2%) and called the mechanism untested
> for 37 days. The goal-blob defect was degrading **all ~121 restores**; compaction found it by
> accident. Standing pattern #3, worse than usual — a proxy normally *correlates* with the pain.
>
> **DO NOT re-litigate this as a compaction question.** ADR-0015 splits it three ways:
> **T1** deliverability (P3 now guards it, mechanical, green) · **T2** sufficiency — *does the
> agent resume without re-deriving?* — **the real question, instrument UNBUILT** · **T3**
> frequency (blocked by the empty PreCompact payload, demoted to informational).
> **No verdict on Mnemos is available until T2 exists** — not keep, not kill.
>
> **The deepest finding, which the re-scope does NOT solve:** `restore_injected` is **a log line
> the hook writes about itself.** The log shows four; the model received nothing on all four.
> Going from 3 events to 121 gives 121 self-reports. **Volume does not fix provenance.**


**START HERE (rewritten 2026-07-26 — most of A–F closed that day).** In "Open, in priority
order" below, **CLOSED: A (ADR-0015), A2, A3, A4, A5, B1, F.** What is actually open:
  - **A-live — T2 needs DATA, and it arrives only as a BYPRODUCT of substantive work.** Not a
    task you can sit and watch. Do the real next job; the receipt is owed at its Stop.
  - **B2 — correction recall.** BLOCKED on labels from a judgement that did not propose the
    hypothesis (see B; I proposed it, retracted it, then produced supporting labels).
  - **A6 — a doccheck for the handoff itself** (it drifted 4 ways on 2026-07-26 and
    nothing could see it; two candidate checks scoped, plus the version NOT to build).
  - **A5b — the per-bail-out spec-11 audit. DO NOT re-open it with a `grep -c degraded` count**;
    that measure produced three wrong findings on 2026-07-26.
  - **C (iCPG), D (ADR-0014 — Lorenzo's decision), E (smaller known items).**
The numbered items 1–7 beneath them are the durable backlog. **CLOSED: 1, 3, 4, 5.** **MIXED —
read the body, not this line: 2** (Part A shipped, Part B needs a design gate) and **6** (the
scryer evaluation is done; the iCPG work it uncovered is item C and is the live one). **7** is
the minors bag and is never "closed".

**`bin/tessera-verify` was 0-for-3 on real attempts; it is now fixed and proven at n=1.** The
tool had done the work every time — planted landmines, executed, reverted — and then **its own
`verify-scan` Stop hook fired and that skip acknowledgment became its final message**, which is
exactly what `parse_verdicts` reads. The verification happened; the answer was overwritten.
Standing pattern #9, scored against the falsifier itself.

Fixed by moving the verdict onto a channel hooks cannot touch: the verifier writes
`tessera-verdicts.json` in its worktree, and the event records `verdict_channel` so a silent
drift back to message-scraping is visible. A live `--self-test` returned
`verdict_channel: "file"` + `REFUTED` — landmine caught, **first usable verdict in four
attempts.** Two caveats worth carrying: it is **n=1**, and writing the file is still an
*instruction to a model* — what changed structurally is that a file cannot be overwritten
after the fact, not that it cannot be skipped. **Watch `verdict_channel` on the next few real
runs.** This matters for spec 11 step 2, where criterion 5's "independent session" is this tool.

Also shipped: item 3 closed (session-keyed logs anchored to the repo — the sweep found **12
sites, not the 1 the todo named**) and **spec 11 step 1 done — the chaos suite exists and its
RED baseline is watched** (8 probes, all 5 components, 7 RED / 1 green). Deliberately no
mechanism: criterion 5 again.

**Then spec 11 STEP 2 shipped (second session, same day) and all 8 probes went GREEN — spec 11's
bar is met for this repo.** `bin/tessera-degraded` (POSIX sh, builtins only — it reports on
broken infrastructure so it cannot assume working infrastructure) + `tessera-watch` **P13**
(7-day window: a degraded event is an incident, not a standing state) + ~31 bail-outs classified
loud/quiet. Chaos is now folded into `run-tests.sh`, so a red there means the framework has
stopped reporting its own failure. **Probes 4 and 8 needed the PROBE fixed first** — `run_wired`
synthesized its own command string with the fail-open `exit 0` hardcoded, so it tested a replica
and no shipped change could ever turn it green. Corrected to read the real `settings.json`, and
**confirmed still-RED before the fix landed** so the detector was not edited into accepting it.

**LATE-SESSION ADDENDUM — spec 11 fully closed, and three things found after it.**

- **Criterion 5 confirmed by a third session**, and it found a **second scope hole**: two-tier
  ADR-0004 commands were excluded from reporting, so under the DEFAULT `global` distribution —
  where no local copy ever ships — all 7 mnemos hooks were fail-silent in every downstream.
  Fixed, rolled, pushed. The scope-completeness test had inherited the same exclusion it was
  meant to police, which is why it could not see the hole either.
- **`decision_surface` gained the AMENDMENT EDGE** (`scripts/decision_amendments.py`). It now
  lists which LATER records revisit each surfaced ADR. Built because this session read ADR-0008's
  verdict, acted on it, and missed a later observatory entry deferring the whole question — the
  hook fired, showed the ADR, and had no edge that could say it had been revisited. Every one of
  the 14 ADRs is referenced later in the observatory, so amendment is the norm. **`REVISITED`
  means "a later record mentions this", NOT "this is void"** — deciding which needs reading.
- **`code-review` skill renamed `tessera-code-review`** — it was SHADOWING the native
  `/code-review`, silently: typing `/code-review ultra` loaded the local skill instead of
  launching the cloud reviewer. Renamed as an INTERIM; its fate belongs to **ADR-0014 / D1**.

**MNEMOS, reframed — read this before judging it.** Diffing our history against the Maggy import
(`ad19913`): **we never broke it.** `checkpoint.py`, `fatigue.py`, `signals.py`, `consolidation.py`,
`models.py`, `redact.py`, `auto_nodes.py` are all UNCHANGED; every line we added is the analysis
layer. **Maggy shipped it half-wired** — its own CHANGELOG calls compact-recovery "the PRIMARY
re-injection point" and no hook entry in Maggy's settings.json ever referenced it. All four Mnemos
failures were INTEGRATION (F-001's interpreter, the dead ingest, the PreToolUse channel, the
two-tier silence) — **zero in `scripts/mnemos/`.** It IS producing: 517 checkpoints, 645 nodes,
haziness across 8+ sessions. Only compaction recovery is untested.

**And the finding that matters most for self-evaluation** — ⚠ **NUMBERS CORRECTED 2026-07-26,
see B.** haziness scored that session `clear` (0.01) despite five confident-wrong assertions,
each corrected. **The per-turn counts below divided by TOOL-RESULT rows** (`role='user'` carries
them in Claude Code transcripts): "408 user turns" and "2010 across 8 sessions" are ~19x the real
human-turn counts, and on eligible turns the detector runs at **17–20%, not ~0**. So "detection
recall" was **not** established as the cause, and "corrections arrive as QUESTIONS" remains an
unverified hypothesis — one I proposed, retracted, then found self-labelled support for.
What survives, and is the real point: **haziness measures *did the tools error*, not *was the
reasoning wrong*.** A session can be `clear` and still be full of confidently wrong claims. Also
still true: the bands were re-anchored on a distribution that includes budget-exhausted sessions
(now known to report FLOORS), so band work re-opens P10.

Suite green, doccheck **31/31**, **chaos 8/8**, **`tessera-watch` fires ZERO** (P3 + P7 snoozed),
findings backlog empty, no escalations. **All six repos pushed and level with origin.**

### Open, in priority order

**NEXT-SESSION PRIORITIES (2026-07-26 late). Items 1 and 3 below are CLOSED; the live work is:**

**A. ~~P3 / the Mnemos compaction trial~~ — RESOLVED 2026-07-26 by ADR-0015. The trial was
   watching the wrong event.** Re-scope, rewritten predicate, and both fixes shipped
   (`6577f7c` + this session). Read `docs/adr/0015-restore-trial-rescope.md`, not the superseded
   reasoning below. **What is LEFT of A is exactly one thing:**

   **A-live. ~~Build T2's instrument~~ — BUILT 2026-07-26. Now it needs DATA, which only time
   gives it.** `scripts/restore/` (offer + emit + scan), Stop hook `tessera-restore-scan.sh`,
   contract `docs/contracts/restore-receipt.md`, 15 tests incl. the end-to-end loop.
   Two parties: the harness logs `restore_offered` (bytes/fields — **never delivery**), the
   model logs `restore_receipt` (sufficient/insufficient **+ mandatory evidence**), the Stop
   scan diffs them and exits 2 on an unanswered offer. Only fires on substantive sessions
   (≥1 edit or ≥20 turns) so `--sufficient` does not become a reflex.
   **ROLL-TO-FLEET TRIGGER — both conditions, and (2) is the one that matters:**
   1. The backstop has fired on a **real** Stop (not hand-driven), and
   2. **at least one `insufficient` receipt exists.**
   (2) applies this repo's own not-vacuous rule to the instrument: a mechanism that has only
   ever produced `sufficient` has not been *shown capable* of the other answer, and until then
   "all sufficient" and "the receipt is decorative" are indistinguishable. Rolling is two halves
   via `tessera-sync-harness` — `scripts/restore/` **and** the Stop wiring in each downstream
   `settings.json`. Both or neither (pattern #5).
   **Rate, so "wait" has a size:** tessera runs ~1.1 sessions/day (16 in the last 14d), 72% of
   them substantive → **~0.8 receipts/day**. First backstop fire: next session. ~5–6 receipts in
   a week. Enough for "does it fire" and "is it reflexive"; NOT enough for `--missing` clustering
   (~15–20).
   **SELECTION BIAS, and it flatters T2 — do not read tessera receipts as a general verdict.**
   This repo has `_project_specs/todos/active.md`, a hand-maintained handoff the SessionStart
   surfacer prints verbatim, plus standing patterns and the decision-surface hook. Restore is
   *easy* here because a second, human-curated channel does much of the checkpoint's job. A
   downstream app has none of that. **Tessera data can validate the MECHANISM; it cannot answer
   whether checkpoints suffice in general** — a week of green receipts here partly means "the
   handoff works", not "Mnemos works".
   **HOW T2 GETS DATA — it is a BYPRODUCT of work, never a task.** The backstop fires only on a
   SUBSTANTIVE session (**≥1 file edit OR ≥20 assistant turns**), so "sit and watch whether T2
   fires" is incoherent: a session that does nothing produces nothing. **Do whatever the real
   next job is; the receipt is owed at that session's Stop.** Any of B2 / C / D generates it.
   **VERIFIED 2026-07-26, and it is why n is still 0:** the session that BUILT T2 was itself
   substantive (1,574 assistant turns, 143 edits) but has **no `restore_offered`** — it started
   before `offer.py` existed, so SessionStart never wrote one. `restore/scan.py` correctly
   returned silent: no offer means nothing owed. That is the "nothing to do" branch confirmed on
   real data, and it means **the next session is n=1**, not this one.
   **NEXT SESSION: this ships with ZERO receipts.** Its first evidence is your own Stop. Three
   things to watch, and they are the ways it fails rather than the ways it works:
   1. **Does the backstop actually fire?** It has never run against a real Stop — every check so
      far was hand-driven. **If the session does ≥1 edit and the Stop hook stays silent, THAT is
      the finding**: pattern #1 landing inside the instrument built to answer for pattern #1.
      Diagnose in this order — (a) is there a `restore_offered` in
      `.tessera/logs/<session>.jsonl`? if not, SessionStart's offer call did not run; (b) does
      `python3 scripts/restore/scan.py <transcript> <session>` exit 1 by hand? if yes, the
      wrapper or the settings wiring is the break, not the scanner.
   2. **Is the receipt honest, or reflexive?** If every session says `sufficient` with thin
      evidence, the instrument is decorative and the length floor did not hold.
   3. **Do `--missing` values cluster?** A run of `progress` is an instruction to change what
      `write_checkpoint` captures — not a reason to kill Mnemos.
   *(Superseded by execution, kept for the trail:)*
   *Does the agent resume, after a discontinuity, without re-deriving what it was doing?* Only
   the model can answer, so it takes the **gate-event shape**: model-emitted, audited, backstopped
   by a Stop hook that diffs claimed against detected. **Until it exists no verdict is available
   — not keep, not kill**, and reading P3's green as "restore works" repeats the category error
   the old P3 encoded (P3 answers T1, deliverability, only).
   **The trap to design against:** `restore_injected` is a log line the hook writes about itself.
   The log shows 4; the model received nothing on all 4. **A receipt written by the sender is not
   a receipt.** T2 must be reported by the receiver.

   *(Superseded framing, kept for the trail — it was RIGHT that the trial was unfalsifiable and
   WRONG about why. It blamed pattern #7 plus the empty PreCompact payload closing the last path
   to evidence, and proposed relocating the venue. The actual cause: the restore path is not
   compaction-specific at all — it runs on every session start, ~121 times vs ~3 compactions. The
   evidence was never scarce, it was counted in the wrong place. Relocating would have preserved
   the category error and gathered auto-compaction events, the question that matters least.)*

**A5. ~~Item 5 — re-judge fatigue/intent~~ — CLOSED 2026-07-26. Feature is LIVE; silence is honest.**
   `mnemos-pre-edit.sh` was silenced for the WHOLE trial by the bare-stdout channel bug; post-fix
   it works, verified live (the `Mnemos + iCPG Context` block landed while editing
   `scripts/mnemos/checkpoint.py`). Fatigue half live — 0.25 FLOW, real dimensions; warnings fire
   only at 0.60+, so FLOW silence is correct, not breakage. Intent half fires when iCPG has
   intents for the file. **The one-file-in-many firing is expected behaviour.**
   **Real gap found + fixed: nothing watched `icpg`.** It resolves through a NAME on a mutable
   PATH exactly as mnemos did, and no predicate mentioned it. If it broke, the intent half would
   read as "this file has no intents" rather than "the tool is gone" — **F-001's confound
   verbatim.** P9 extended (declare-then-check on `.icpg/reason.db`).

**A6. NEW — the handoff has NO mechanical consistency check, and it drifted four ways today.**
   Asked "handoff updated?" at the end of 2026-07-26 and it was not: item **F** still read
   "nothing detects it" twenty lines from **A4** recording it FIXED that morning; **START HERE**
   still pointed at a resolved A; and **two passages asserted retracted numbers as fact**
   ("2010 user turns / 5 detections", "corrections arrive as QUESTIONS"). I had edited this file
   four times that day and never re-read it end to end — the artifact-not-property error again.
   **`doccheck` cannot see it, and that exclusion is CORRECT**: `_project_specs/` is out of scope
   because specs describe work NOT YET BUILT, so naming an absent file is the point (doccheck.py's
   own header says so). The consequence is that the one document whose entire job is *being true
   on arrival* has zero automated guard.
   **Two tractable checks — and note NEITHER requires reading prose, which is why they are worth
   trying where a general "is this consistent?" check is not:**
   1. **Retired-figure sentinel.** A small list of numbers/claims formally retracted (`2010 user
      turns`, `5 detections`, `≥3 non-manual compaction_fired`, `COMPACTION_MIN`) that must not
      appear in the handoff *unqualified* — i.e. not within N lines of RETRACTED / SUPERSEDED /
      Original text. Cheap, precise, and it is the `adr-execution-recorded` pattern reused. Today
      it would have caught 3 of the 4.
   2. **Closed-item artifact check.** An entry containing `FIXED`/`CLOSED`/`DONE` + a date must
      name a backticked path that exists — same rule as ADRs' `Executed:`. Catches "closed" items
      whose machinery was never built.
   **DO NOT build the obvious version**: a check that greps `open`/`closed` keywords will misfire
   on ordinary prose and become the ignored-checker this repo keeps warning about. If neither of
   the two above survives contact, the honest answer may be that the handoff needs a human re-read
   at session end, not a check — say so rather than shipping a noisy one.

   **RESOLVED 2026-07-27 — ONE of the three shipped, and the other two were rejected on
   MEASUREMENT rather than taste.** All three were prototyped against the live file first,
   which is the only reason the answer is trustworthy.

   ✅ **SHIPPED: doccheck `handoff-retires-its-own-figures`** (34 checks). A hand-curated list of
   formally retracted figures — `2010 user turns`, `5 detections`, `COMPACTION_MIN`,
   `≥3 non-manual` — each of which must carry a retraction marker within 4 lines. Zero false
   positives across the whole file, and **it caught a real one on its first run**: the 07-12
   backlog still stated *"Fires at ≥3 non-manual `compaction_fired`"* as a **live trigger, 15
   days after ADR-0015 retired it**. A reader landing there would have believed P3 still counts
   to three. Whole-file scope on purpose — an archived criterion stated as live is exactly the
   trap. Watched RED against the pre-fix file, and guarded against vacuity two ways (an empty
   figure list is itself a violation; a missing handoff is a violation, not a pass).

   ❌ **REJECTED — "a closed entry must name an existing path": 12 false positives in 13
   entries.** Closed handoff items legitimately cite commits (`cb0e267`), ADRs, and watcher
   predicates — not paths. The ADR `Executed:` line works *only* because it is a **structured
   field with a stated contract**; handoff prose has none, and demanding one would push authors
   to fabricate paths to appease the checker.

   ❌ **REJECTED — "an item closed in START HERE must be struck through in its body": it FAILS
   OPEN, and I proved it against my own file.** Scoped to the newest section it found no
   closed-list at all, because the `CLOSED: 1, 3, 4` phrasing it keys on was invented on 07-26
   and **the very next section (07-27, mine) did not use it**. It would have caught the
   historical case and nothing after it. A check over unenforced prose format goes quietly
   green — the fail-open class, in the check written to stop drift.

   **So A6's own fallback is the answer for those two shapes: they need a human re-read at
   session end, not a check.** The durable lesson is narrower than "check the handoff":
   **a mechanical check needs a mechanical subject.** Retired figures are a closed list of exact
   strings; "is this item's status consistent" is a judgement wearing a regex.

**A5b. ~~The per-bail-out audit~~ — DONE 2026-07-27. One real gap, a CLASS with three
   instances, found by reading and confirmed by probing.**

   **The answer to "is any bail-out covered by NOTHING?" is YES, and it was the reporters
   themselves.** The `settings.json` trailing branch reports a hook SCRIPT that is missing or
   unexecutable. It cannot report a hook that ran perfectly and whose **RUNNER** is gone or
   crashed. Probed by hand before fixing anything, and all three were silent:
   - `rm bin/tessera-watch` → SessionStart printed a completely normal handoff. **Every
     predicate — P3, P4, P9, P11, P12, P13, P14, P15 — goes quiet at once, and the silence is
     indistinguishable from a clean session.** The worst instance in the repo: the thing that
     would tell you is the thing that broke.
   - `bin/tessera-watch` exiting 2 → identical. `[ $? -eq 1 ] || exit 0` put "nothing fired"
     and "a predicate raised" on the same branch, so a crashing watcher read as a healthy one.
   - `bin/tessera-findings` deleted, and `decision_surface.py` crashing → both silent. The
     decision-surface hook has now been able to ship silent in **two different ways**.
   All three fixed, and guarded by **chaos probes 9, 10 and 11** — watched RED against the
   unfixed hooks first, which is this suite's founding discipline.

   **A finding about the probes, which is the more transferable half:** the first version
   deleted the runner from a scaffolded downstream — and **no downstream has `bin/tessera-watch`
   or `bin/tessera-findings`, nor wires the surfacers at all.** They are tessera-only hooks. The
   probe would have asserted on something that was never there, which is exactly how a probe
   skipped and hid a whole component on this suite's first run. They now install a working
   runner, prove the surfacer is QUIET, and only then break it.

   **The method held: reading found the candidates, probing confirmed them, and counting would
   have found none of it** — all three hooks had *zero* `tessera-degraded` calls, which is the
   signal the 07-26 audit misread as "missing coverage" and got wrong three times. Absence of a
   call means nothing on its own; only "break it and see" answers the question.

*(Original entry, kept for the trail:)*
**A5b. OPEN — the per-bail-out audit, and DO NOT re-open it with a count.**
   I counted `grep -c degraded` per hook (5 of 16), called it a spec-11 hole, and was **wrong
   three times over**: coverage is DISTRIBUTED — toolchain bail-outs → P9, never-ran → the
   `settings.json` trailing branch, `tessera-verify-scan` → `exit 2` + stderr (stronger, which is
   why `report_settings.needs_reporting()` skips it). **That was standing pattern #3 aimed at the
   auditor: I named the artifact that correlates with the pain instead of the pain.**
   The honest question is narrower and still unanswered: **is any bail-out covered by NOTHING?**
   It needs per-hook reading to separate "nothing to do" from "could not run" — a session's work,
   and doing it fast is how a wrong classification gets baked into a check.

**A4. ~~Decided-but-not-built is undetectable (item F)~~ — FIXED 2026-07-26.** ADRs now carry an
   append-only `- **Executed:**` line: `not yet` / `n/a — <why>` / `<date> — \`artifacts\``.
   **The immutability rule was conflating two facts** — *what was decided* (immutable; rewriting
   it is revisionism, and ADR-0007 is legible precisely because nobody did) and *whether it was
   ever built* (a fact that does not exist when the ADR is written). CLAUDE.md now carves that
   one exception explicitly.
   doccheck `adr-execution-recorded` **verifies the named paths exist** — the load-bearing half,
   since without it the line is just another doc claim, which is this checker's whole subject.
   `decision_surface.py` prints `⏳ NOT EXECUTED` / `⏳ PARTIALLY EXECUTED` before you edit a
   governed file, and is deliberately SILENT on shipped ADRs (noise on every hit is how a real
   warning gets skipped).
   **Backfilled all 11 accepted ADRs from verified artifacts, and it immediately paid:**
   **ADR-0008 is `partially` — the review-skill cut is still not done and is deferred to
   ADR-0014/D1.** That is the exact decision a session acted on while missing the deferral.
   *Detector note: the first version flagged `hook_distro` and `skillOverrides` — backticked
   IDENTIFIERS, not paths. Fixed in the detector, not by stripping backticks from real prose.*

**A2. ~~The spend guard fails OPEN on a cwd shift~~ — FIXED 2026-07-26.** `cd scripts` made
   `tessera-spend-guard.sh` resolve `scripts/scripts/spend/guard.py` → absent → **spend-committing
   commands ALLOWED**. Standing pattern #4 inside the deny-by-default gate on external spend.
   **It was a class, not one bug: SIX hooks** took `PROJECT_DIR` from the session cwd
   (`spend-guard`, `spend-backstop`, `gate-scan`, `verify-scan`, `mnemos-stop-ingest`,
   `mnemos-stop-checkpoint` — that last one silently wrote NO CHECKPOINT from a subdirectory
   while reporting "nothing to do", the exact confusion spec 11 exists to forbid).
   All six now walk up to the project root, as does `tessera-degraded` — **the half that mattered
   more**, since its report had been landing in `scripts/.tessera/logs/` where P13 never reads.
   Guarded by `scripts/test_hook_cwd_anchoring.py` (a regex catching any new hook that
   reintroduces the idiom, plus behavioural tests), falsified against the pre-fix hook: it
   allowed from `scripts/` and `scripts/spend/`, denied only from the root.
   **THREE things worth keeping from how this went wrong:**
   1. `CLAUDE_PROJECT_DIR` is **empty** in some invocations, so `${CLAUDE_PROJECT_DIR:-$CWD}`
      would have been a *vacuous fix* that looked right. Walking up to a real marker is required.
   2. **The first marker choice failed because the bug forged its own.** `.tessera/` was the
      marker — but this very bug creates stray `.tessera/logs/` dirs in whatever cwd was current,
      and the one under `scripts/` was found first. Marker is now `.git` (`-e`, not `-d` — a git
      worktree's is a FILE) or a `.tessera/` that actually holds `project.yml`.
   3. The resolver first returned via `printf`, and doccheck's `pretooluse-hooks-reach-the-model`
      flagged it — it cannot tell a function's stdout from the hook's. Fixed by returning via a
      variable. **The detector was right; the code was ambiguous.**
   *(Leftover: an untracked `scripts/.tessera/` is still on disk — harmless now that the marker
   requires `project.yml`, but `rm -rf scripts/.tessera` when convenient.)*

**A3. ~~Nothing detects global-tier staleness~~ — FIXED 2026-07-26, `tessera-watch` P14.**
   `~/.claude/templates/` had held **7 stale hooks and was missing `tessera-decision-surface.sh`
   entirely**; all three PreToolUse hooks had **zero** `additionalContext`, so the 07-24 channel
   fix had reached no downstream at all. Three tiers, two edges, and only the runtime edge was
   unguarded: `.claude/scripts/` → `templates/` (P1 + doccheck, commit-blocking) →
   `~/.claude/templates/` (**what downstream actually runs**, previously nothing).
   P14 byte-diffs it, separates MISSING from STALE, and is gated on `.bootstrap-dir` naming this
   repo — silent when another checkout owns the tier rather than telling it to clobber someone
   else's install. Falsified against the real tier, not just fixtures.
   **The durable finding is about P4, not the tier.** P4 reported "all in sync" the whole time
   and was correct by its own definition — it measures downstream copies *against*
   `~/.claude/templates/`, the very thing that was stale. **Uniform staleness reads as
   agreement.** Standing pattern #1 aimed at a checker. P4's docstring now says so, and its green
   still does not mean "downstream is current". **When a checker takes a reference, ask what
   validates the reference.**

**B. RE-FRAMED 2026-07-26 — the "5 / 2010" premise was a bad denominator; the real defect is
   budget-exhaustion.** `role='user'` carries TOOL RESULTS in Claude Code transcripts, so the raw
   count was ~19x the human turns. On eligible turns the detector runs at **17-20%**, not ~0.
   **Do not repeat the old figure.** Any recall claim must state its denominator.
   **B1 — DONE 2026-07-26.** `mnemos haze` now marks these `\u2265N.NN band?` in the table and prints a FLOOR banner in `--session` detail; `unmeasured_reason()` in haziness.py is the single predicate, self-checked in `test_haziness.py`. **Real blast radius was 13 sessions, not 24** — 11 of the 24 are synthetic `tessera-verify` worktrees. **STILL OPEN: the 07-20 band re-anchoring used a distribution containing them, so the bands themselves are uncalibrated against this.** Original finding:  budget-exhausted sessions report
   unmeasured turns as non-corrections.** `CorrectionDetector` has a 180s wall-clock budget; past
   it every remaining turn returns False. 24 sessions affected, detecting at 2.94% vs 17.1%.
   Haziness then scores them as if real, with `correction_density` at weight 0.30. **This is P3's
   `unknown` lesson in another organ — a verdict must not rest on what the instrument could not
   read.** Fix is NOT the knob (raising 180s moves the cliff): a budget-exhausted session must
   mark or withhold its composite, as P3 excludes unclassifiable events from both counts.
   **Also check: the 07-20 band re-anchoring used a distribution containing these 24 sessions.**
   **B2 (blocked on unbiased labels): recall on the interrogative register.** Eval baseline
   n=114, **precision 0.32 / recall 0.53** — precision is the weaker half. This session
   hand-labels ~6 corrections against 1 detection, including the turn that overturned the trial
   framing. **I did not act on it: I proposed that hypothesis, retracted it, then produced the
   labels supporting it. Self-labelling into the silver set would corrupt the one instrument that
   could refute me.** Needs labels from a judgement that did not propose the hypothesis, then
   re-run `eval_correction.py` and re-open bands AND weight per P10.

**B-old. SUPERSEDED BY B — every number below is RETRACTED. Kept only for the trail.**
   ⚠ **"2010 user turns / 5 detections" divided by TOOL-RESULT ROWS** (`role='user'` carries them
   in Claude Code transcripts). On eligible turns the detector runs at **17–20%**. The claim that
   "corrections arrive interrogatively" is an UNVERIFIED hypothesis I proposed, retracted, then
   found self-labelled support for — do not treat it as a finding. **Quote nothing from here.**
   *Original text:* 2010 user
   turns across 8 sessions, 5 detections. Corrections arrive interrogatively; the detector is
   tuned for the declarative register. `scripts/mnemos/eval_correction.py` is the existing
   silver-label harness and THIS session is a labelled example (5 known confident-wrong episodes,
   each corrected). **P10 gate applies: any detector change must re-run the eval and re-open bands
   and weight on the new numbers** — and note the bands were anchored under the dead signal, so
   they are suspect independently.

**C. ~~iCPG — diagnosed, untouched.~~ SHRINK EXECUTED 2026-07-27.** Six dimensions → three, each
   with a named producer (`changed` / `decision` / `usage`); `ownership` + `dependency` deleted;
   `test(0.30)` moved to `scripts/icpg/coverage.py` and reported by `icpg status` as a count;
   usage bounded to git-tracked files; **746 events purged, not deduplicated** (725 carried the
   constant). `scripts/icpg/` has its **first tests ever** (13, own process line) and doccheck
   gained **`drift-dimensions-have-producers`** (33 checks).
   **A fourth root cause, found by reading the rows:** decision-drift gated on `postconditions`
   (0/10 reasons) while `contracts.py` writes **53 invariants across 10 reasons** that the
   evaluator already understood — a live producer and a live evaluator pointed at different
   fields. Fresh baseline: 217 events (`usage` 140, `changed` 49, both 28); `decision` fires zero
   because all 53 invariants currently hold — **live-and-silent, which is a different fact from
   dead.**
   **WHAT IS LEFT, and it is not cosmetic:**
   1. **The re-insertion defect is live and refills the backlog.** `mnemos-pre-edit.sh` runs
      `icpg drift file` on every Edit/Write and `cmd_drift` persists with a fresh UUID and no
      natural key — the count grew 712 → 746 during the session that diagnosed it. Purging
      buys one clean reading, not a clean counter. Dedup-on-insert + event IDs + `drift list` +
      evidence on the report (the ADR-0013 list) is now the entire remainder.
   2. **`usage`'s thresholds are uncalibrated** — 168 of 816 symbols fire, 64 saturated at 1.00,
      and bootstrap scopes are one commit-cluster wide so "outside scope" is nearly the repo.
      **Do not tune `>2` and `/10` by eye**; that is how three proxy predicates were born.
   3. **The authoring half of the trial is untouched and is the bigger question** — see below.

**D. ~~ADR-0014 / decision D1~~ — DECIDED 2026-07-27: option D, review is Claude-only,
   deliberately.** Chosen on evidence from the ADR's own re-evaluate trigger #4 ("exercise
   bin/review's backends"): `kimi` execs a phantom path and had been **broken 15 days
   unnoticed**, `codex` is absent, `deepseek` is sound but unkeyed (dormant, not dead), and
   **`bin/review` had never run** — 0 commits since creation. The repo had not degraded its
   portability; it never had any. Nobody noticed because *a dead backend is indistinguishable
   from an unused one*.
   **Executed, not just recorded:** cut `bin/review`, `bin/kimi`, `bin/research` and
   `skills/tessera-code-review/` (978 lines) — which also closes **ADR-0008's thirteen-day-old
   `partially`**, the exact entry the `Executed:` field was invented to be able to close.
   Harvested first per ADR-0007: the ADR gate was already `skills/adr-gate/`, the frameworks
   were already in design-principles §4.3, and the one unrecorded idea (review's position in the
   TDD loop) went to design-principles before the delete.
   **SCOPE LIMIT — the prune stops at review.** `bin/deepseek`, `bin/validate-plan`,
   `council-review` and `scripts/test_council.py` are KEPT: plan validation is a different
   capability that merely shares backends, it degrades honestly (exit 2, no verdict), and
   **ADR-0007 says "do not cut the multi-model stack… do not re-litigate without the design
   session."** This ADR was scoped to review and does not overrule that.
   **The fact that will matter at the re-evaluate:** LiteLLM is not hypothetical — conclave
   already carries `litellm/config.yaml` with a model_list and three api_base entries. If that
   gateway becomes routine, option **B** is the cheap re-entry, not C.
   **A checker gap found while executing:** `adr-execution-recorded` assumed execution always
   CREATES artifacts, so a decision whose execution is a PRUNE could not record itself honestly.
   It now supports `removed:` and asserts those paths are ABSENT — the stronger half, since it
   verifies a cut was made rather than merely recorded.

**F. ~~THE DECIDED-BUT-NOT-BUILT GAP~~ — CLOSED 2026-07-26, see A4.** ADRs now carry an append-only `- **Executed:**` line, doccheck `adr-execution-recorded` verifies the named paths exist, and `decision_surface.py` prints `NOT EXECUTED` / `PARTIALLY EXECUTED` before you edit a governed file. **The backfill immediately caught ADR-0008 as `partially` — the review-skill cut is still not done.** The two instances below are kept as the evidence that motivated the fix, not as open work.
**F-original (the trail): two instances in one day, and nothing detected it.**
   An accepted decision that was never carried into the machinery is **indistinguishable from one
   that was**. Both of today's worst bugs are this:
   - **ADR-0008** ruled CUT-the-bulk on the `code-review` skill (2026-07-14). The prep step ran
     (`adr-gate` was split out); the cut never did. Twelve days later the leftover skill was found
     **shadowing the native `/code-review`** — the very command ADR-0008 cited as its replacement.
   - **P3**: the observatory recorded, in Lorenzo's name (2026-07-16), that the compaction verdict
     is *"structurally un-completable here"* and moves to a real CLI venue. **P3 was left counting
     toward ≥3 for ten more days**, behaving as though the trial could still conclude.
   Neither was detectable. `decision_surface`'s new amendment edge surfaces *"this decision was
   revisited"*; it does NOT surface *"this decision was never executed."* doccheck asserts what
   docs claim about the repo, not whether a decision's action happened. **This is the gap behind
   Lorenzo's ADR question (2026-07-26) — and it is NOT ADR strictness. There is no state for
   "decided, not yet built", and no signal when a decision and its machinery drift apart.**
   Candidate shapes, none chosen (avoid a 4th proxy predicate — pattern #3):
   (i) an explicit `Status: Accepted — UNEXECUTED` until something marks it done;
   (ii) an ADR field naming the artifact its decision produces, checked for existence;
   (iii) a watcher predicate over Accepted ADRs whose named action has no commit.
   **Do not build (iii) reflexively** — "has this been done?" is judgement, and judgement is where
   the retired proxies came from. (i) is exact and nearly free; start there.

**E. Smaller, known:** item 2 Part B (pending-record channel — needs its 3-decision design gate)
   is the only one left here. **Items 4 and 5 were listed as open in this line while their own
   closures sat twenty lines above** (A3/P14 and A5 respectively) — corrected 2026-07-27, and it
   is the third drift shape A6 has now seen: not a stale figure and not a phantom path, but a
   *status contradicted between the index and the body*. The mechanical form of it: an item
   declared closed in START HERE must have a struck-through title in its own body. Items 1/3/6
   did; 4/5 did not, which is exactly why the contradiction survived four edits.


1. ~~**Spec 11 — fail-open sweep.**~~ **CLOSED 2026-07-26.** Both open items resolved same day: the command-body tooling gap (`scripts/hooks/report_settings.py`) and the criterion-5 re-read, which a third session ran and **confirmed the run_wired correction legitimate** — with better evidence than the original (AST comparison of probes 4/8 docstring-stripped is byte-identical; the OLD test against the NEW template still fails 2, proving insensitivity in both directions). **It also found a second scope hole, now fixed:** two-tier ADR-0004 commands were excluded from reporting, so under the default `global` distribution — where no local copy ever ships — all 7 mnemos hooks were fail-silent in every downstream. Fleet rolled and pushed. Kept below as the reference record, not as open work.
   *(Step 1)* `chaos/test_chaos.py` + `bin/tessera-chaos` (top-level `chaos/`, not
   `scripts/chaos/` — `pytest scripts/` would collect these red-by-design probes into the main
   suite, and `--ignore`ing them would collide with `ignored-test-suites-are-run`; outside
   `tessera-test` on purpose — the probes are legitimately red, and a permanently-red main
   suite is one people learn to ignore; doccheck `chaos-suite-is-reachable` stops it rotting).
   8 probes, all 5 components, each scaffolding a REAL downstream and driving the hook through
   its actual stdin/exit-code contract. **7 RED, 1 green** — output pasted into the spec.
   **Three findings that change step 2:** (i) **criterion 4's case is already FIXED** — on the
   real `/usr/bin/python3` (3.9.6) the guard denies correctly; probe 3 is retained as its
   regression guard; (ii) **the live spend fail-opens are the other bail-outs, and two are worse
   than the original** — a corrupt guard exits 1, a *deleted* guard exits 0 with empty stderr,
   and since only rc=2 blocks, **both ALLOW the spend**; (iii) **a probe silently skipped and hid
   a whole component** — the default `global` distribution ships no local mnemos hooks, so the
   mnemos probe skipped and component 4/5 was uncovered while the run read as fine (fixed with
   `--frozen`). *The fail-open suite's first fail-open was its own.*
   **STEP 2 DONE 2026-07-26 (different session, criterion 5 satisfied) — ALL 8 PROBES GREEN.**
   Shipped `bin/tessera-degraded` (POSIX sh, shell builtins only — no jq/sed/grep/awk/python,
   because it reports on broken infrastructure and may not assume working infrastructure; `date`
   and `mkdir` optional, since probe 5 hides both), `tessera-watch` **P13** (7-day window — a
   degraded event is an *incident*, not a standing state, so it needs no disposition verb; the
   anti-pattern is item 6's iCPG counter), ~31 bail-outs classified, and the chaos suite folded
   into `run-tests.sh`. Contract: `docs/contracts/degraded-event.md`.
   **The finding worth keeping:** probes 4 and 8 could not be fixed from the Tessera side —
   `run_wired` *synthesized* the command under test with the fail-open `exit 0` hardcoded, so
   both asserted against a replica and probe 8 edited `settings.json` without ever reading it
   back. Pattern #9 violated one layer inside the suite built to enforce it. Corrected to read
   the real settings, **then confirmed STILL RED before any settings change** — the detector was
   not edited into accepting the fix.
   **STILL OPEN, and both are recorded in the spec but were NOT in this list until now — the
   spec is not a surfaced channel, this file is (principle #17):**
   - ~~**(a) Downstream rollout (§4 of the spec).**~~ **DONE 2026-07-26 — all 5 downstreams.**
     `tessera-sync-harness --update-stale` back-filled `scripts/tessera-degraded`, the
     decision-surface hook, `gate/paths.py`, and refreshed the gate/spend hooks to their
     spec-11 versions. **howler excluded `--exclude spend`** — its guard is a documented
     deliberate defer closable only from a howler session, and bundling it into a sync once
     already installed it by accident; `scripts/spend/` confirmed still absent after. Gate
     suite green (29) in all five. **Verified on the real path, not asserted:** conclave's
     actual hook driven with `jq` hidden wrote a real `degraded` event into conclave's own
     `.tessera/logs/`. Commits `bdc531f` / `6610ba1` / `5fbeffc` / `47a11a8` / `ca2f447`,
     then `d27caee` / `9277c62` / `d9e2d90` / `bbec874` / `847e3f7`. **NOT PUSHED — local
     only in all five, awaiting a deliberate call** (same status the Part A anchoring rollout
     carried; see item 2).
   - ~~**(a2) tooling gap — no tool updates a wired command BODY.**~~ **CLOSED 2026-07-26.**
     `scripts/hooks/report_settings.py` — third sibling of the same shape, one rewrite per
     file (`patch_settings.py` = ADR-0004 fallback, `anchor_settings.py` = cwd anchoring,
     this = reporting). Wired into `--patch-settings`, which stays **settings-only and
     installs nothing** — the invariant the howler accident actually violated, so a second
     pure-settings rewrite does not re-open it. Order enforced: anchor first, or reporting
     names a path that still moves with cwd. Detector `unrunnable-hooks-report-themselves`
     **imports** the fixer's predicate instead of mirroring a regex. Fleet + tessera +
     template all patched and pushed; tool output verified **byte-identical** to the earlier
     hand patch. **Scope is every local-only wired hook, no allowlist** — which is why it
     immediately found the one the hand pass missed (`tessera-decision-surface`, the hook
     that already shipped silent once) and correctly left the fleet's mnemos hooks alone.
     **Two findings from building it, both worth carrying:** (i) the predicate counted
     `findall()` hits and required exactly one, but the wired form names its script **twice**
     (`[ -x P ]` and `exec P`), so it never matched a real command and the fixer silently did
     nothing; (ii) because of (i) the new doccheck check **passed on its first run while
     incapable of flagging anything** — a vacuously green check, inside the check written to
     stop vacuous greens. Only the not-vacuous test caught it. **Every new doccheck check
     needs a not-vacuous test that feeds the REAL artifact back through the predicate**; a
     green from a fresh check is not evidence until something has been seen to make it red.
   - **(b) Criterion 5 is now partially self-referential.** Steps 1 and 2 were different
     sessions, but the step-2 session also corrected `run_wired`, so for probes 4 and 8 the
     probe author and the mechanism author are the same. Mitigated by the RED-before-GREEN
     check above, but **a third session re-reading that correction is worth more than the
     note** — it is the cheapest remaining check on the whole spec.
2. **Push mechanism (framework→downstream).** Split into two, Part A DONE:
   - **Part A — `tessera-sync-harness --patch-settings` (SHIPPED + APPLIED TO ALL 5).** Anchors
     *existing* cwd-relative hook commands in a downstream `settings.json`.
     `scripts/hooks/anchor_settings.py`; output kept clean under doccheck's own detector so
     fixer/detector can't drift. **Applied + committed in all 5** (conclave `9333e19`, heaviside
     `c2dbf00`, settempo `ccd41e3`, tess-dashboard `684df86`, howler `5d25036`) — pure anchoring,
     settings.json only. **PUSH STATUS: local only** — heaviside/tess-dashboard also carry
     pre-existing unpushed commits, so pushing was left for a deliberate call.
     Two bugs the apply exposed, both fixed: **(1)** `--patch-settings --apply` bundled the full
     back-fill and installed howler's DEFERRED spend guard mid-ship — reverted, refactored to
     **anchor-only** (`6af5246`, regression-tested); **(2)** B was half-shipped into the scaffold
     this session (wired in the template, file not copied) — `tessera-new-project` now ships both
     halves (`efb7649`). **The wire-without-file class is now GUARDED** (`10c18ac`):
     `test_new_project_wires_ship_files` asserts every local-only wired hook ships its file,
     using the fallback-presence rule (no allowlist, zero false positives — the special-casing
     I'd flagged as the blocker turned out unnecessary once the rule keyed on the ADR-0004
     fallback). Lives in the suite, not doccheck, because it scaffolds a project.
     **Severity of the original anchoring gap was mostly LATENT:** the 7 mnemos hooks have the
     ADR-0004 global fallback that masks it; only the 3 local-only Tessera hooks (gate-scan,
     spend-guard, spend-backstop) were live-vulnerable, and only in a cross-repo session.
   - **Part B — the pending-record channel (framework→downstream). NEEDS A DESIGN GATE first**
     (its observatory entry says "design settled in argument, nothing built"). When sync finds a
     gap it should *write* a record into the downstream's own docs (automating the howler
     CLAUDE.md section). Open decisions to gate before any code: **(1) where the record lives** —
     a `## Pending` block in `CLAUDE.md` (rides the always-loaded file, but must update
     idempotently without clobbering hand edits) vs a dedicated `docs/PENDING.md` vs `.tessera/`;
     **(2) idempotent-update semantics** — how re-running sync refreshes the record without
     duplicating or overwriting human notes; **(3) the committed staleness marker** (portability
     consideration #6) — cross-machine "is it stale" has no answer without a marker committed in
     the downstream, because the reference differs per machine. Resolve these three, then build.
3. ~~**`emit.py` still writes `.tessera/logs/` relative to cwd.**~~ — DONE 2026-07-26. The scoping
   sweep found the item was **under-specified: 12 relative-path sites, not 1.** Sorted by the rule
   **the anchor must match the key** — `.tessera/logs/<session>.jsonl` is keyed by
   CLAUDE_CODE_SESSION_ID, so it belongs to the SESSION and cwd-resolution is wrong by
   construction; `bin/tessera-*` and `tessera_config.py` are **repo**-keyed, so their cwd-relative
   paths are CORRECT and were deliberately left (`tessera-watch` inside a downstream *should*
   evaluate that downstream). Fixed the 6 hand-invoked session-keyed tools
   (`gate/{emit,label,ratio,remap_kind}.py`, `override/emit.py`, `mnemos/eval_correction.py`) via
   `scripts/gate/paths.py` — anchored on `__file__`, **not** `CLAUDE_PROJECT_DIR`, which is set for
   hook processes but **UNSET in the Bash tool env**, so the `${CLAUDE_PROJECT_DIR:-.}` form the
   hook *commands* use collapses to `.` here. `TESSERA_ROOT` overrides. Check:
   doccheck `session-logs-are-repo-anchored` (+4 regression tests incl. an anti-vacuity one).
   **The read side was the worse half and is the item-1 evidence:** `ratio.py` from a foreign cwd
   printed a clean report of ZERO gates over ZERO sessions; anchored, the same command reports
   27 sessions / 142 gates / 1039 edits. It did not break — it produced something plausible.
   **The 5 hook-invoked siblings (`gate/scan.py`, `verify/scan.py`, `spend/{backstop,guard,event}.py`)
   are LATENT, not fixed** — safe only because the wrapper does `cd "$(dirname "$0")/../.."`, i.e.
   one shell line is the sole guarantee for the spend-authorization lookup. That is a pattern-#1
   shape and belongs to item 1's sweep. Shipping also exposed a **pattern-#5 half-ship**: the new
   `paths.py` was not in `tessera-new-project`'s copy set, so every scaffolded project's gate
   recorder would `ModuleNotFoundError` — caught by `test_new_project_gate_copies`, fixed.
4. ~~**Third hook layer still unchecked**~~ — **CLOSED 2026-07-26 by `tessera-watch` P14, see A3.**
   The seam is guarded, and by something stronger than this item asked for: P14 byte-diffs
   `.claude/scripts/` (framework truth) against `~/.claude/templates/` directly, rather than
   `templates/` ↔ global as worded here — so it cannot be fooled by both copies being equally
   stale. `bin/tessera-watch:686`. The other two edges keep their existing guards (P1 + doccheck
   `hooks-match-templates`). Gated on `.bootstrap-dir` naming this repo, so it is silent rather
   than wrong when another checkout owns the tier.
5. ~~**Re-judge Mnemos compaction recovery AND the fatigue/intent feature.**~~ **CLOSED
   2026-07-26 — both halves, in different places.** Fatigue/intent: **A5** — live, verified with
   its output actually landing, and FLOW-silence is honest (warnings fire at 0.60+). Compaction
   recovery: **ADR-0015** dissolved the question rather than answering it — the restore path is
   not compaction-specific, so it splits into T1 (deliverability, P3, green), T2 (sufficiency,
   the real question, instrument built and awaiting data — see **A-live**), T3 (frequency,
   informational, blocked by the empty PreCompact payload). **Do not re-open this as "re-judge
   compaction"**; that framing is the category error ADR-0015 retired.
   See observatory → "PreToolUse hooks' bare stdout never reached the model".
6. ~~**Evaluate scryer**~~ — DONE 2026-07-25, ADR-0013: **Watching**, no dependency (Tauri GUI,
   FSL license, near-total overlap with iCPG). Two patterns adopted idea-only. **The eval's real
   output was about iCPG:** the drift backlog is **700 rows that are only 154 distinct drifts**
   (102 symbols, 31 scans; one pair duplicated 21×), with no symbol/file/diff in the report.
   Standing pattern #2; a fail-open instance for item 1's sweep. **ROOT CAUSE CORRECTED same day —
   the first write-up of this item was wrong.** It claimed iCPG "has no verb to close one";
   `icpg drift resolve` has existed all along (`scripts/icpg/__main__.py:112`). The two real
   defects: (i) `cmd_drift` re-INSERTs a fresh row for the same drift on every scan (`__main__.py:384`,
   no natural-key check); (ii) no command prints `event.id` and there is no `drift list`, so the
   existing verb is unreachable without raw SQLite. See ADR-0013's CORRECTION block.
   **CORRECTED AGAIN 2026-07-26 — third pass found the dedup framing too shallow.** The real defect:
   **the detector scores the absence of edge types nothing writes.** `CREATES 879`, and
   `MODIFIES / REQUIRES / DUPLICATES / VALIDATED_BY / DRIFTS_FROM` all **0** — the last four have no
   writer anywhere in the codebase (enum in `models.py:45`, read-only use at `store.py:303,315,337`),
   and `MODIFIES`'s only writer, `icpg record`, is wired to **no hook**. So: `_check_test_drift` does
   `if not test_edges: return 0.3`, which fires for every symbol forever — **701/701 events carry a
   constant `test(0.30)`**; `spec` drift ("checksum changed *without a MODIFIES edge*") degenerates to
   `git diff`; and `_check_usage_drift` is **literal `grep -rl <name> .`** over an unfiltered tree
   including `.venv/`. Decision, ownership, and dependency drift have never fired once.
   **This answers `design-principles.md:440`'s kill/keep criterion — "does drift detection catch things
   grep wouldn't?" — with: no, the dominant dimension IS grep, in a subprocess.**
   **The open work, in order — (a), (b), (c), (e), (f) DONE 2026-07-27; only (d) remains:**
   ~~(a) decide what the detector is for~~ — decided with Lorenzo: **shrink to what can be fed**,
   do not build writers speculatively (ADR-0006 ranks prevention over detection, and deleted
   machinery cannot fail silently). ~~(b) bound `usage`~~ — `git grep` over tracked files.
   ~~(c) stop reporting `test(0.30)` as drift~~ — moved to `coverage.py`, printed by
   `icpg status` as `Intents w/o tests: N/M`.
   **(d) STILL OPEN and now the entire remainder:** dedup on insert, surface event IDs +
   `drift list`, evidence on the report, `--note`/`dismissed`. **Do it first** — the re-insertion
   defect is live (`mnemos-pre-edit.sh` → `drift file` persists on every edit; the count grew
   712 → 746 during the session that diagnosed it), so the purge bought one clean reading, not a
   clean counter.
   ~~(e) zero tests~~ — 13 now, own process line, registered under `ignored-test-suites-are-run`;
   three were watched RED against a re-added unfed dimension before being accepted.
   ~~(f) leave the check~~ — doccheck **`drift-dimensions-have-producers`**, with `drift.py`
   excluded from the producer scan so it cannot vouch for itself, and an empty read set treated
   as a violation rather than a pass. See observatory → "iCPG's drift detector measures the
   emptiness of its own graph".
   **The kill/keep verdict is still unavailable, and the reason has changed.** Two of the three
   confounds are cleared (dimensions no longer score absence; the pre-edit channel was fixed
   07-24). The third is untouched and is the one that matters: **all 10 reasons are
   `owner='git-history'`, `agent=NULL`, `source='inferred'`** — no agent has ever authored one,
   because nothing records intent. Per FOCUS-004's rule that absence is **not evidence**, in
   either direction; the recording half must be wired before `design-principles.md:459` can be
   answered. Same shape as F-001, one layer up.
7. Minors: **concept-tags for B** (it only surfaces file-keyed decisions; Alternatives-Considered
   and cross-cutting lessons are blind — the observatory "harness-staleness" entry is a live
   example B could not have surfaced). *Still open — but note B gained the **amendment edge**
   2026-07-26 (`scripts/decision_amendments.py`): it now lists the later records that REVISIT
   each surfaced ADR, which is a different axis from concept-tags. File-keying is unchanged.*
   ~~uuid prefix-resolve~~ **DONE 2026-07-26** — and it was not cosmetic: `mnemos haze --session`
   and `divergence --session` **failed OPEN**, scoring an unknown or truncated id as
   `0.00 CLEAR (0 turns)`, the best possible result, for a session that does not exist. Both now
   resolve an unambiguous prefix and refuse otherwise (rc=2), sharing one resolver. **auto-guard for E** (the standing-patterns block is
   hand-maintained — a doccheck could assert every phrase appearing 3+ times has a line);
   **B vs `adr-gate`** (decide if B replaces that skill's intent or if it wires as a Stop hook
   too — avoid two mechanisms for one job); sqlfluff blocking flip (settempo not there); **G-a
   fires correctly** (reads the fire-log tail, self-clears after 3 runs — do NOT "fix"); trim
   backlog (ADR-0008); historical `--reclassify --all`;
   **`tessera-verify stats` does not break out `verdict_channel`** (the field exists and is the
   number that says whether the file fix is holding — right now you have to read the log by
   hand); **spend-guard matching needs a design gate** (observatory 2026-07-26 — it matches
   command TEXT, so it over-denies prose and, more seriously, under-denies anything assembled at
   runtime; naive tightening worsens one half and naive loosening is unavailable because a
   PreToolUse hook never sees the expanded command).

### What happened (2026-07-26)

- **`tessera-verify` fixed — verdicts now travel by FILE** (`a73d529`). It was 0-for-3 on real
  attempts, and the cause was not that it failed: it did the work every time, then its own
  `verify-scan` Stop hook fired in the spawned session and that skip acknowledgment *became* the
  final message `VERDICT_RE` reads. The verifier now writes `tessera-verdicts.json` in its
  worktree (authoritative), message-scraping stays as a fallback, and `verdict_channel` is
  recorded on **every** judged run so a drift back to the fragile channel is visible rather than
  inferred from rising NO_VERDICT. **Proven, not just shipped:** a live `--self-test` returned
  `verdict_channel: "file"` + `REFUTED`. **The fix nearly reintroduced its own bug** —
  `make_worktree` copies untracked files IN, so a stale verdict file in the repo root would have
  been read as this run's answer (a false CONFIRMED from a verifier that wrote nothing); guarded
  by an unlink before every spawn, and the regression test removes the guard and watches the
  false CONFIRMED appear. Also fixed a dangling-worktree-record leak the self-test exposed.
  **Still only n=1, and writing the file is an instruction to a model** — what changed
  structurally is that a file cannot be overwritten after the fact, not that it cannot be
  skipped.
- **Item 3 closed — session-keyed logs anchored to the repo** (`5de7924`). The todo named
  `emit.py`; the sweep found **12 relative-path sites**. Sorted by a rule worth keeping: **the
  anchor must match the key.** `.tessera/logs/<session>.jsonl` is keyed by
  CLAUDE_CODE_SESSION_ID, so it belongs to the SESSION and cwd-resolution is wrong by
  construction — while `bin/tessera-*` and `tessera_config.py` are **repo**-keyed and their
  cwd-relative paths are CORRECT (`tessera-watch` inside a downstream *should* evaluate that
  downstream). Fixed the 6 hand-invoked session-keyed tools via `scripts/gate/paths.py`.
  **Anchored on `__file__`, NOT `CLAUDE_PROJECT_DIR`** — that var is set for hook processes but
  is **UNSET in the Bash tool env**, so the `${CLAUDE_PROJECT_DIR:-.}` form the hook *commands*
  use collapses to `.` for anything you run by hand. `TESSERA_ROOT` overrides. Check: doccheck
  `session-logs-are-repo-anchored` + 4 regression tests.
- **Spec 11 step 1 — chaos suite built, RED baseline WATCHED** (`98c5240`). `chaos/test_chaos.py`
  + `bin/tessera-chaos`. 8 probes, all 5 components, each scaffolding a real downstream and
  driving hooks through their actual stdin/exit-code contract. **7 RED, 1 green.** Placement
  matters and cost a rework: under `scripts/` the probes got collected by `pytest scripts/` and
  failed the main suite, and `--ignore`ing them would have collided with
  `ignored-test-suites-are-run` — top-level `chaos/` needs no exclusion, so neither check is
  weakened. Kept reachable by doccheck `chaos-suite-is-reachable`.
- **Three findings, and they matter more than the two items:**
  1. **`tessera-verify` is 0-for-3** — see THE ONE THING TO KNOW. Observatory entry filed
     (`0a95e5b`) with three candidate fixes. **Fixed same day:** verdicts now travel by file
     (`tessera-verdicts.json` in the worktree), `verdict_channel` records which channel was
     used, and a live `--self-test` came back `verdict_channel: "file"` + `REFUTED`.
  2. **The spend guard matches command TEXT.** It denied a log-cleanup script and the verifier's
     own meta-command for merely *containing* a spend command as a string. The over-denial is
     loud and safe; **the under-denial is unexamined and is the serious half** — a command
     assembled at runtime reaches the PreToolUse hook without the trigger and passes, so *the
     workaround for the false positive is the bypass for the control*. `decide()` only ever sees
     pre-expansion text, and a PreToolUse hook has no resolved form to inspect — needs a design
     gate, not a patch. Observatory entry, no code change.
  3. **I got a classification wrong and it bit within the hour** (`c5fca17`). Item 3 filed
     `scripts/spend/event.py` as "latent — hook-invoked, the wrapper cds." False: the site is
     live for *any* caller reaching the guard without the wrapper, and chaos probe 3 is such a
     caller. Seven synthetic `spend_denied` fixtures landed in the real session log before it
     was caught. **The cwd-relative class is broader than "is it wired to a hook."** The 4
     remaining hook-invoked siblings should be re-read with that in mind during step 2.
- **The chaos suite's first fail-open was its own.** A probe targeting a mnemos hook `skip`ped,
  because the default `global` distribution ships no local mnemos copies — component 4 of 5 went
  uncovered while the run still read as fine. Fixed by scaffolding `--frozen`.
- **Spec 11 criterion 4 no longer reproduces:** on the real `/usr/bin/python3` (3.9.6, not a
  stub) the spend guard denies correctly — `from __future__ import annotations` held. Probe 3
  retained as the regression guard for a bug that already cost real spend.

### What happened (2026-07-24)

- **cwd anchoring shipped, both tiers** (`1b2d6c7`). A `cd ~/Claude/howler` persisted (the Bash
  tool keeps cwd across calls) and retargeted every relative hook path: the gate log split 4/2,
  the Stop hook misdiagnosed a wrong-cwd as "not executable", and an adversarial probe showed
  12 of 13 hooks silently no-op from a foreign cwd. Fixed: 16 settings commands →
  `${CLAUDE_PROJECT_DIR:-.}`, 11 scripts self-anchor from `$0` (GUARDED so the global-tier copy
  does not cd to `$HOME`), both scaffold templates, global tier synced via `install.sh`. Checks:
  doccheck `hook-commands-are-anchored` (both halves + guard + templates).
- **decision-surface (B) + standing-patterns (E) shipped** (`07f4689`) to make #17 land on the
  design record itself — B surfaces governing ADRs before an edit (it fired correctly on this
  session's own edits), E prints the cross-cutting lessons at SessionStart.
- **Multi-agent code review** (3 lenses + a docs verification) on the session diff. Found and
  fixed a CRITICAL: B was wired PreToolUse and emitted bare stdout, which reaches only the debug
  log — silent to its whole audience. Plus 2 mediums (doccheck vacuity) and 3 lows (all fixed or
  consciously left). My own testing had certified B green. See standing pattern #9.
- **PreToolUse channel bug found to be a CLASS** (`[HEAD-1]`). `mnemos-pre-edit.sh` (fatigue/
  intent) and `mnemos-post-compact-inject.sh` (Layer 3) had the same bare-stdout defect — silent
  to the model the whole trial. This EXPLAINS the skill's standing "Layer 3 injection never seen"
  note. Both fixed; check `pretooluse-hooks-reach-the-model` added. Observatory entry filed.
- **L3 review nit closed** (`b4178b9`) — anchor check missed the `./`-prefixed path form; fixed,
  scoped away from the string-mention false positive the maggy template exposed.
- **neon + neon-postgres absorbed into `skills/`** (`18c6578`) — P12 was firing on Claude-shipped
  global-only skills; content was already byte-identical, the drift was provenance.
- **Part A push mechanism built + applied to the fleet.** `--patch-settings` (anchor-only after
  a bug — see item 2) anchored all 5 downstreams (`9333e19`/`c2dbf00`/`ccd41e3`/`684df86`/
  `5d25036`, all pushed). Two bugs the apply exposed: it once bundled the back-fill and installed
  howler's deferred spend guard (reverted, refactored `6af5246`); and B was half-shipped into the
  scaffold (fixed `efb7649`, guard `10c18ac`).
- **Second multi-agent review** (`81f5579`) of the whole post-surfacer diff. Found 2 mediums —
  BOTH the signature bug applied to the guards built this session: `pretooluse-hooks-reach-the-
  model` cleared on a channel named in a *comment* (M1), and `anchor_settings` skipped statusLine
  while the detector flagged it (M2). Both fixed + regression-tested. **The session's sharpest
  meta-lesson: every check I built to catch the silent-failure class had itself a silent-failure
  bug. Independent review caught what my testing certified green — twice.** (standing patterns #1, #9.)
- Doccheck grew 20 → **27 checks** across the session.

### Not Tessera's to execute (2026-07-24 reclassification)

- **howler spend guard.** Was item 1 here for two sessions and never moved — because *nothing in
  a Tessera session can do it*. The command runs against `~/Claude/howler`, the hook it installs
  denies Bash by default there, and the only way to learn whether it blocks a build/upload/signing
  step is to be in howler running those commands. A task that can only be executed in another
  repo does not belong on this repo's priority list; parking it at #1 made the list read as
  blocked when the framework work was never blocked. Command when in howler:
  `tessera-sync-harness ~/Claude/howler --apply` (drop `--exclude spend`), with
  `tessera-authorize` ready before any spend-committing command.
  **Tessera's residual share is real but small:** the fleet-currency *check* is Tessera's — today
  nothing tells you howler is 9 files behind except a human running `tessera-sync-harness`
  by hand. That gap is the same class as items 2 and 3 and belongs with them, not with the
  howler-side install.

---

## ═══ SESSION 2026-07-22 (wrap) — F-001 closed, sqlfluff adopted, fleet harness current ═══

*(Archived — the 2026-07-24 handoff above supersedes it. Kept for the trail.)*

### What happened (2026-07-22)

- **conclave F-001 closed** (`a7ba928`) — gate-scan content-addresses asking turns and subtracts
  turns ruled not-a-gate. Narrower than the finding asked: fired gates stay a *count*, because a
  `suggestion_gate` carries no reference to the turn that produced it.
- **sqlfluff adopted warn-only** (`e7162d4`, **ADR-0012 supersedes ADR-0011**). 0011 answered the
  wrong question — whether sqlfluff finds defects in settempo's SQL *today*, rather than whether
  the framework should carry the capability.
- **F-003 closed.** P4 rewritten to diff bytes; `tessera-hooks status` now compares content;
  ADR-0004's deferred settings auto-patch built; **all three frozen repos thawed**.
- **`tessera-sync-harness` built** — the fleet was silently behind by *time*, not by a missing
  `cp`. tess-dashboard had no gate harness at all.

### The through-line, and it is now the framework's most-repeated bug
**A component ships, and the thing that would tell you it is broken is also broken.** Six
instances now: F-001's interpreter, the dead ingest pipe, the falsifier's swallowed spawn
failure, P4 counting projects instead of bytes, `tessera-hooks status` advertising a drift check
it never performed, and the fleet quietly running a retired gate vocabulary. **Spec 11 is the
systematic answer and it is item 2 for a reason.**

Second, smaller: **name the pain, not the artifact that correlates with it** — retired-P2 (verb
count), old-P4 (project count), the sqlfluff trigger (file existence). Three proxy predicates.

### Cross-repo cautions learned the hard way
- A `git add -A` in settempo swept up **another session's** uncommitted edits. Caught only by
  reading the diff. Check `git status` before staging in a downstream; prefer explicit paths.
- Before committing in a downstream, check whether someone is working in it.

---

## ═══ SESSION 2026-07-22 (earlier) — F-001 closed, sqlfluff adopted, findings backlog empty ═══

*(Load-bearing heading — `.claude/scripts/tessera-watch-surface.sh` greps it at SessionStart.
Newest section carries it; doccheck `handoff-heading-is-current` guards the ordering.)*

**COMMITTED: `c626418` docs/handoff + spec 11, `a7ba928` gate disposition memory (F-001),
`e7162d4` sqlfluff warn-only (ADR-0012). Downstream: conclave `586cd8d`, settempo `78d3f96`
+ `f93c0d6`. Suite green (215 top-level), doccheck 20/20, tree clean, no escalations,
**findings backlog empty across all 5 projects**.**

### Next session — start here

1. **Spec 11 — fail-open sweep.** Now the top item; F-001 is done and it warmed up the same
   `scripts/gate/` code. Scope is fixed in the spec: five components, ~15 sites, **chaos tests
   FIRST**. Its new predicate is **P13** (P10 retired, P11/P12 taken).
2. ~~**P4 red**~~ **DONE — P4 is GREEN.** All three frozen repos thawed to `global`
   (heaviside `2319e24`, tess-dashboard `abecbf4`, howler `b274055`), unblocked by ADR-0004's
   settings auto-patch built the same day (`2fbeed3`). **`frozen` now has zero users.**
   **G-a still fires and that is correct** — it reads the fire-log (`watch.jsonl`), whose last
   3 *logged* runs predate the fix. Its docstring says so ("the log is the tail, not now"). It
   self-clears after 3 more SessionStart-logged runs. Do not "fix" it.
3. **Third hook layer still unchecked** — nothing compares `templates/` ↔ `~/.claude/templates/`,
   the layer `install.sh` writes. P4 covers downstream↔global; doccheck `hooks-match-templates`
   covers `templates/`↔`.claude/scripts/`. This is the last uncovered seam.
4. ~~**No back-fill mechanism for scaffold components.**~~ **DONE — `bin/tessera-sync-harness`
   (`401e0cf`, `df92cfe`, `c833edc`).** The whole fleet is current. It scaffolds a reference
   project with the real `tessera-new-project` and diffs against it, so it carries no second
   definition of "what the harness is" to drift from the scaffold. `--update-stale` refreshes
   files **only** when they are byte-identical to a commit in tessera's history — a proof of
   non-customization, not a judgement. `--exclude <substr>` skips a component (built for the
   spend guard). Sets `core.hooksPath`, but refuses when real `.git/hooks` would be shadowed.
   16 tests. **Only howler's spend guard remains, deliberately — see below.**
5. **Consider flipping sqlfluff to blocking per project** once its `.sqlfluff` is tuned enough
   that findings are real (`lint.sh` final `exit 0` → `exit 1`). settempo is NOT there — its
   RF05/PG01 hits are wrong.
6. Trim backlog (ADR-0008); minors: uuid prefix-resolve, historical `--reclassify --all`.

### What happened

- **conclave F-001 closed** (`a7ba928`). Gate-scan now content-addresses each asking turn
  (sha256 of the whole normalized turn — not the preview, which collides across this repo's
  many turns ending "…OK to proceed?"; not an index, which slides as transcripts grow) and
  subtracts turns ruled not-a-gate via `emit.py --not-a-gate --turn <id>` → a `gate_disposition`
  event. Detection is unchanged; it just stops asking twice. **Deliberately narrower than the
  finding asked:** it also proposed subtracting *fired* gates by identity, which is impossible
  today — a `suggestion_gate` carries no reference to the turn that produced it. Condition for
  revisiting is in `docs/contracts/gate-event.md`.
- **sqlfluff adopted warn-only** (`e7162d4`, **ADR-0012 supersedes ADR-0011**). ADR-0011 was one
  day old and not wrong on its facts — it answered the wrong question, evaluating whether
  sqlfluff finds defects in settempo's SQL today rather than whether the framework should carry
  the capability. Lorenzo's disposition; #12 is *Claude proposes, user disposes*. Ships as
  `scripts/sql/lint.sh` + `.sqlfluff` (`exclude_rules = layout`) + on-demand skill + a downstream
  `.githooks/pre-commit` and `core.hooksPath` — **caught mid-build that downstream projects had
  no pre-commit hook at all**, so the gate would have shipped with nothing invoking it.
- **A gate-log split worth fixing.** `emit.py` writes to `.tessera/logs/` **relative to cwd**, so
  a session working across two repos splits its gate log and each repo's scan under-counts by
  whatever was logged in the other. Hit live this session (the settempo adoption gate). Belongs
  next to the gate-scan work — same file, different cause from F-001.

### Cross-repo caution learned the hard way
A `git add -A` in settempo swept up CLAUDE.md edits that were **not mine** — another session was
working in that repo concurrently. Caught before committing, but only by reading the diff.
**Check `git status` for unexpected modifications before staging in a downstream repo**, and
prefer explicit paths over `-A` when another session may be live.

---

## ═══ SESSION 2026-07-21 — settempo adopted, three fail-opens closed, ADR-0011 ═══

*(This heading is load-bearing: `.claude/scripts/tessera-watch-surface.sh` greps
`^## Handoff — pick up here` at SessionStart. Newest section carries it; guarded by doccheck
`handoff-heading-is-current`.)*

**COMMITTED: `491b330` install worktree guard, `2ff424b` scaffold findings channel, `49b4bbc`
verify fail-open, `f1fbde1` P4 byte-drift, `17d69ee` ADR-0011 sqlfluff. Plus settempo `7e13bf8`
(harness adoption). Suite green (212 top-level), doccheck 20/20, tree clean, no open escalations.**

### Next session — start here

1. **Conclave F-001 — gate-scan disposition memory. CLOSEABLE IN ONE SESSION** (sized 07-22, see
   below). The only open finding, and it pairs with #2.
2. **Spec 11 — fail-open sweep.** Its thesis got a *third* live confirmation this session (the
   verify fail-open below). Scope is fixed in the spec: five components, ~15 sites, chaos tests
   FIRST. **Do not build the mechanism first** — the spec says why, in bold, and it is right.
   Note the spec calls its new predicate "P10"; that number is taken (retired haziness trigger)
   and P11/P12 exist — the next free one is **P13**.
3. **The third hook layer is still unchecked.** P4 now covers downstream↔`~/.claude/templates`;
   doccheck `hooks-match-templates` covers `templates/`↔`.claude/scripts/`. **Nothing covers
   `templates/` ↔ `~/.claude/templates/`** — the layer `install.sh` writes, and the layer that
   armed the latent regression in the F-003 entry.
4. **P4 is red on real drift:** 3 stale `mnemos-pre-compact.sh` in heaviside/howler/tess-dashboard.
   Deliberately not synced — frozen ship-critical repos, owners' call. **G-a also fires** (P4 3
   consecutive runs), but those runs straddle the predicate rewrite, so it is counting two
   different predicates as one. Resolve by syncing, or snooze.
5. Trim backlog (ADR-0008, unblocked by ADR-0010); minors: uuid prefix-resolve, historical
   `--reclassify --all`, skill-profiles refine.

### What happened — an adoption that turned into three fail-open fixes

Started as "should settempo become a downstream?". Answer was *defer* — until Lorenzo said a
session was starting, which flipped it. Wiring it surfaced bugs in the framework, not settempo.

- **A. `tessera-verify` was poisoning `~/.local/bin`.** It spawns a verifier in a temp worktree;
  when that agent ran `./install.sh`, line 130's `ln -sf "$root/.venv/bin/$c"` aimed the machine's
  console scripts at the worktree, which was then reaped. **All four (mnemos, icpg, polyphony,
  skill-lint) were dangling** into a deleted `/var/folders/.../tessera-verify-0iipykaq`. Tessera
  never noticed — its hooks try `.venv/bin/mnemos` before `command -v` — but settempo has no
  `.venv`, so it would have inherited F-001 on day one. Guard now lives in `install.sh` (protects
  every caller, not just tessera-verify): skip the global link when `$root/.git` is a *file*
  (linked worktree). Verified end-to-end, including under a real `tessera-verify` run.
- **B. The falsifier was failing open, inside the tool built to catch fail-opens.**
  `spawn_verifier` did `return result.stdout` and discarded returncode + stderr, so a spawn that
  never ran became `NO_VERDICT` — and `scripts/verify/scan.py` counted *any* verification event as
  a disposition. **A verifier that never ran was silencing its own Stop-hook backstop.** Fixed at
  three layers + `raw_excerpt` so `NO_VERDICT` is diagnosable. *Skip is a decision; `spawn_error`
  is an accident. Only decisions disposition.*
  **Wrong turn worth recording:** I attributed the first `NO_VERDICT`s to the permission classifier
  blocking the nested `claude -p`. That was a guess stated with too much confidence and it was
  **wrong** — tessera-verify runs fine from inside a session; the failures were transient. An
  escalation was raised and resolved on the corrected facts.
- **C. Scaffold shipped a *missing* findings channel.** `docs/contracts/findings.md` says every
  project carries `docs/FINDINGS.md` and that empty ≠ missing — but `tessera-new-project` never
  created it. All four prior downstreams had it *by hand*. A contract with a producer requirement
  and no producer.
- **D. P4 measured the wrong thing** — `len(downstream_projects) >= 5`. settempo (`global`, 0 local
  copies) tripped it while adding zero drift surface. Now diffs bytes and **names the file**; first
  run found 3 genuinely stale hooks the count predicate never saw and never would. It can also go
  *green*, which the old one could not.
- **E. ADR-0011 sqlfluff — Watching.** Trigger fired (settempo has standalone `.sql`), evidence said
  no: **206 violations, 0 actionable** (89% layout; the 21 survivors are idiomatic Supabase RLS
  names, `CONCURRENTLY` demanded on a fresh-install script, and a column named `date`). Zero
  `SELECT`s — pure write-once DDL.

### The through-line, and it is now a rule

**D and E are the same bug as retired-P2: a predicate firing correctly on a proxy that tracks no
real pain.** Three instances now. Stated in ADR-0011 as: ***name the pain, not the artifact that
correlates with it.*** Corollary learned the same day: a naive `find -name "*.sql"` would have
false-fired on conclave for months (130 vendored litellm migrations under `harness/venv`, **0
tracked by git**) — **use `git ls-files`, never `find`.**

**A, B and the 07-20 dead ingest pipe are all spec 11's thesis**: the instrument lied quietly, and
only ground-truth poking found it. Three in a week, each found by accident. That is the argument
for sweeping deliberately rather than waiting for the fourth.

### Also
- **settempo** is the framework's **first adoption of a pre-existing repo** — the other five were
  all greenfield (the scaffold commit is commit #1 in each). `tessera-new-project --adopt` was
  *not* built: n=1, so there is nothing yet to generalize from. Build it on the second adoption.
  Procedure used is in `7e13bf8`'s message.
- settempo is the first downstream with auth + SQL + user input, so the first place the universal
  profile's `security` skill has real surface.

---

## ═══ SESSION 2026-07-20 — eval → specs 14/15/16 closed, dead pipe fixed, P10 adjudicated ═══

*(This heading is load-bearing: `.claude/scripts/tessera-watch-surface.sh` greps
`^## Handoff — pick up here` at SessionStart. The `## ═══ SESSION` style used 07-17→07-19 silently
stopped the surfacer — it printed the 07-12 handoff for 8 days. Newest section carries this heading;
guarded by doccheck `handoff-heading-is-current`.)*

**MERGED: #36 (specs 14–16), #37 (should_fire stop-loss), #38 (ingest-pipe fix + P11), #39 (kind
enum), #40 (P10 adjudication), #41 (handoff-surfacer fix, doccheck #20), #42 (ADR-0010 skill
mirror + P12), #43 (downstream validation + scaffold fix), #44 (findings channels). Plus sibling
commits: conclave F-001 retitle, heaviside channel opened — both pushed. Suite green, doccheck
20/20, watch quiet (P7 snoozed). No branches in flight, remote pruned. Every item from the
morning eval AND every spec written today closed same-day.**

### Next session — start here
1. **Conclave F-001 — gate-scan disposition memory** (surfaces at SessionStart via findings).
   Well-specified in conclave's FINDINGS.md: a not-a-gate ledger keyed by turn hash, subtracted
   from the detected set alongside fired gates. Pairs naturally with:
2. **Spec 11 — systematic fail-open sweep.** Pattern proven (P11: trace + watcher); remaining
   scope = the other fail-open paths (hooks, spend guard, gate scan, escalation surfacing).
3. **Trim backlog (unblocked by ADR-0010)** — remaining ADR-0008 delivery-entangled trims under
   single-body policy, read-first, one decision at a time.
4. Minors: uuid prefix-resolve; historical `--reclassify --all` (cleans pre-carrier-fix
   denominators); deeper skill-profiles refine.

### What happened — an eval session that turned into a repair session
Started as a progress eval; the eval's probes found two live instrument failures. The through-line:
**three instruments were lying quietly, and only ground-truth sampling caught them.**

- **A. should_fire STOP-LOSS (#37, spec 14).** First real `--all` backfill failed eyeball acceptance
  (23T/51F vs ~90% T human anchor). Two causes: retro-logged gates' `ts` = adjudication time →
  disposition join grabs unrelated wrap-up turns (structural, untunable); soft assents read as No
  (invisible to the #35 eval — negative class was n=1). All 74 classifier labels rolled back;
  `emit.py --retro` marks adjudication-time events (scan message requires it; `label.py` skips them).
  **Verdict: asking-calibration rests on the 26-label human anchor — the gate is NOT over-firing.**
  Classifier path shelved; resumption criteria in `docs/contracts/gate-event.md`.
- **B. Stop-hook ingest was DEAD 07-17→07-20 (#38, spec 16).** `make_detector()`'s repo-root import
  raised under the console script the hook execs — before every fail-open guard, stderr swallowed.
  Every hook ingest since #19 wrote NOTHING; hand-runs worked (F-001's cousin; P9 blind by
  construction). Fixed path-relative + never-raises; per-ingest `classifier_status` trace; watch
  **P11** (DEAD = recent transcripts with no session row — the shape no status column can see;
  DEGRADED = 3 consecutive regex-only). Repair re-ingest: 72 sessions recovered, real-signal 24→50.
- **C. suggestion_kind enum (#39, spec 15).** 33 free-text kinds → 7 (`design/scope/sequencing/
  process/finding/doc/outward`), fail-closed at emit; `remap_kind.py` rewrote 50 events
  (`suggestion_kind_raw` kept, 0 unknown).
- **D. P10 fired and adjudicated (#40).** Silver-label pass (Lorenzo's push — 125 turns BOTH
  classes, Claude-judged, live-qwen replay via committed `eval_correction.py`): precision ~0.36–0.48,
  recall ~0.39–0.53, **measured density within ~±50% of true** — ordinal, not absolute. Bands
  0.25/0.50/0.75 → **0.05/0.12/0.20** (old bands labeled all 115 sessions 'clear'); weight stays
  0.30; **P10 retired** — standing trigger: any detector change re-runs `eval_correction.py`.
  Bonus: ~11% of the eligible denominator was carrier junk (`<bash-stdout>`, interrupts riding user
  role) → now `user-meta` at ingest.

### The day's transferable lesson (recorded in observatory, twice-confirmed)
An eval with a thin class measures half a classifier; a join defect masquerades as a rubric defect
until you read the basis quotes. Sample BOTH classes, on fresh data, before trusting any instrument.
And: a fail-open path that leaves no trace converts "broken" into "clean-looking data" (3 days here,
weeks for F-001) — every fail-open now wants a heartbeat.

### Known gaps / stale premises (logged, not fixed)
- **P7's snooze rationale is now stale:** it says "real fix is passive detector upgrade, spec 13" —
  but the should_fire classifier was stop-lossed, and pre-flag retro events are permanently
  unjoinable. When P7 resurfaces (2026-08-31) the likely disposition is **retire**, same logic as
  P10: the human anchor answered the calibration question. Decide then, not unilaterally now.
- Historical `claude_turns` rows keep pre-carrier-fix denominators; a future `--reclassify` cleans
  them (band edges robust to the ~10% shift).
- uuid prefix-resolve (`haze`/`divergence --session`) still open; skill-profiles deeper refine still
  open. Both low-stakes.

### Next (in order)
1. ~~**ADR-0010 — skill-body delivery mechanism.**~~ **DONE — same session (2026-07-20, evening).**
   Decided with Lorenzo: repo `skills/` is truth; global is a managed mirror
   (`bin/tessera-sync-skills`, mirror-with-delete, in `install.sh`, watched by **P12**); first sync
   applied (10 zombies deleted, 57→47 machine-wide listing; 6 stale bodies refreshed); single-body
   policy adopted. **The delivery-entangled trim blocker (07-18) is LIFTED** — trims proceed under
   ADR-0010 policy (a cut is a cut for downstream too; HARVEST-BEFORE-CUT with downstream in mind).
   Build-time find: a copier already existed (`install-skills.sh`, additive-only cp — kept for
   non-Claude targets) — the observatory's "no copy mechanism" was half-right; the missing pieces
   were delete + watcher.
2. ~~**Downstream validation**~~ **DONE — same session.** Fresh `tessera-new-project` bootstrap,
   ADR-0009 + ADR-0010 end-to-end: curation correct (36 off / 11 universal-on = the 47-mirror
   exactly — pre-sync it would have enumerated 57 with zombies), extension expansion verified
   (`extensions_added: [python, ai-app]` → exactly its 3 skills flip on), hooks resolve
   local→global templates, gate scripts ship current. **One real bug found+fixed:** spec 15 made
   `test_gate_emit` import `remap_kind`; the scaffold cp list drifted — fresh downstreams shipped
   broken gate tests. Fixed + `test_new_project_gate_copies.py` (runs the copied tests in a real
   scaffold output — guards the whole copy-list-drift class).
3. ~~**Findings channels (small)**~~ **DONE — same session.** Conclave's finding retitled to the
   F-NNN shape (committed there, unpushed — conclave rides local-main); heaviside channel opened
   empty (committed). `tessera-findings` now reads all 4 downstreams. **Every item from the
   2026-07-20 eval is closed.** Newly visible: **conclave F-001** (gate-scan has no
   disposition memory — re-flags adjudicated non-gates every Stop) is now a real open backlog
   item surfacing at session start; good first candidate next session, pairs naturally with the
   spec-11 sweep.

---

## ═══ SESSION 2026-07-19 — friction-detector Phase 3 + skill-profiles tidy + should_fire passive extraction ═══

**MERGED: #31 (Phase 3), #32 (skill-profiles tidy), #33 (dashboard provenance note), #34 (should_fire
extraction). #35 (should_fire rubric fix + eval) open. Suite green, doccheck 19/19. Both friction-calibration
vectors now have their passive instrument: *doing* (divergence #31) and *asking* (should_fire #34+#35).**

### What shipped — spec 13 is now CLOSED
**Phase 3 = action-link + divergence surface.** `scripts/mnemos/divergence.py` (new, pure) derives per
detected correction the **ASK → DID → CORRECTED(type)** unit: nearest preceding human prompt (intent),
the assistant work since it (files touched / tool counts / did-it-error), and the correction + its Phase-2
type. `aggregate()` = flat cross-session rollup by type.

- **Derivation, not storage.** The link is cheap structural data reconstructable from `claude_turns` any
  time → **no column, no migration, no ingest cost** (unlike Phase 1/2's expensive stored qwen verdicts).
- **Three surfaces:** `mnemos divergence --session <id>` (triplets), `--recent N` (by-type rollup), and a
  new **DIVERGENCE** section in `haze --session --explain`.
- **View-only, held:** does NOT feed the haziness composite (verified — `b6d7b6f5` composite unchanged at
  0.219 density, 0.11 CLEAR). Same stance as Phase 2; weight changes stay gated on P10.
- **The surface earns its keep:** it makes a real distinction visible — **action-divergences** (`did:` has
  edits) vs **conversational pushback** (`did: (no tool actions)`). The doing-calibration instrument the
  postmortems kept saying only a human catches.
- **Tests:** `test_divergence.py` (added to `run-tests.sh` enum) — nearest-window, window-reset-per-prompt,
  no-prior-ask, errors-in-window, non-correction-emits-nothing, aggregate rollup. All pure/fixture, no store.
- **Ceiling (marked `ponytail:`):** links to the *nearest* action window only; multi-window attribution
  deferred until it measurably misfits.

### B. skill-profiles tidy (#32)
3 audit-KEEP skills had no curation home (off everywhere downstream): **code-review → universal**,
**existing-repo → new `brownfield` ext**, **project-tooling → new `deploy` ext**. `workspace` +
`team-coordination` left intentionally off (removal candidates). Guard: doccheck **19th check**
`skill-profiles-names-are-installed` (dangling names, not orphans) + fail-clean on malformed JSON. Read-first
per rule-over-read (found no dangling, only the 3 orphans).

### C. should_fire passive extraction (#34) — the *asking*-calibration instrument
`scripts/gate/label.py` fills `should_fire` (gate-calibration ground truth, else `null` forever — dead P7
backlog) from the user's DISPOSITION (first human turn after the gate, **timestamp-joined**) via a balanced
local-qwen classifier. Writes back in place, idempotent, fail-open, `labeled_by: "classifier"`, **never
overwrites a human label**. 11 mocked tests (auto-discovered in the gate suite).
- **Deliberately backfill-first** (`--session`/`--all`) — Stop-hook auto-wire is a follow-on.
- **Ground-truth eval caught a rubric bug the n=3 backtest missed (the real lesson).** #34 shipped a rubric
  that scored **recall 0.08** on **n=26 human-labeled gates** (`scripts/gate/eval_should_fire.py`, new,
  committed) — near-always-No, reading terse option-picks ("commit", "1a 2a", "go with 2") as dismissals
  when *selecting a surfaced option IS the decision*. **Fixed the rubric** (fix/should-fire-rubric): engagement
  incl. terse pick = `should_fire=true`; only explicit "you didn't need to ask" = false. **recall 0.08 → 0.76,
  precision 1.00** on the same 26 (tuned+measured on one set; neg class n=1 → precision under-measured, P10
  confirms). Residual 6 FN not chased (2 unfair summary-bases, 4 non-option-pick engagements — overfitting risk).
  *Anecdotes lie, ground-truth evals don't — the eval is now committed as the runnable P10 spot-check.*

### Decisions surfaced this session (all resolved with Lorenzo, gate logged)
Phase 3: derive-not-store · both surfaces (aggregate flat) · added ask+error context · no composite.
Tidy: 3 placements + the guard. should_fire: label.py location · timestamp-join · balanced prompt ·
backfill-first · ship-as-is despite ~0.5 precision (tuning is P10-gated, n=3 too small).

### Docs synced (doc-drift discipline)
spec 13, `docs/observatory.md` (Phase 3 + should_fire updates), mnemos SKILL, `docs/contracts/gate-event.md`
(labeled_by provenance + producer status). This handoff.

### Known gaps logged (not fixed)
- `divergence --session` / `haze --session` need the FULL uuid, but `haze` prints 8-char ids — prefix-resolve
  would fix both. Sibling-consistency call.
- **should_fire human-overrides-classifier path is undefined** — a human disagreeing with an auto-label needs
  a manual edit today (`label.py` never re-touches a labeled event). Fine for now; note it.

### NEXT (in order)
1. **should_fire follow-ons** — (a) `--all` historical backfill (generates the P10 precision sample),
   (b) Stop-hook auto-wire (backgrounded, after backfill eyeballed), (c) human-override path.
2. **P10 haze-recalib** — self-fires at 40 real-signal sessions (precision spot-check → band re-tune).
3. **Refine `skill-profiles.json`** further vs the full KEEP set — the #32 tidy homed the 3 orphans; a
   deeper profile/extension review (which stack tags, defaults) is still low-stakes-open.

**Delivery-mechanism blocker still stands** (see 2026-07-18 section): do NOT trim further
delivery-entangled skills on the "survives globally" rationale until the delivery design session settles it.

---

## ═══ SESSION 2026-07-18 — friction Phase 2 + delivery-entangled trims + branch/doc cleanup ═══

**ALL MERGED to `main` (#25–#29). Suite green, doccheck 17→18, `tessera-watch` quiet (P7 snoozed). No
branches in flight (2 stale remote branches deleted). Skills 48 → 47.**

### What shipped
- **A. Friction-detector Phase 2 — typing (#25).** Each detected correction typed
  (`misunderstood/defied/overreached/wrong`) via a 2nd qwen prompt on already-detected corrections
  only. New `claude_turns.correction_type` col + idempotent ADD-COLUMN migration; `haze --explain`
  rollup + `CORRECT:<type>` markers; `--reclassify` backfills. **VIEW-ONLY — does NOT feed the haziness
  composite** (weight changes stay gated on P10). Verified vs live qwen3:8b: `b6d7b6f5` → 7 typed,
  density unchanged 0.219. Code-review Low fix folded in (`correction_type` shares the fail-disable).
  Only **Phase 3 (action-link)** remains — spec 13.
- **B. python TRIM + a phantom-claim fix (#27).** `python` 222→81 ln (cut toolchain/src-layout/CI/
  pre-commit/pydantic Tessera doesn't use; kept type-hints/DI/Result/anti-patterns). **Read-first
  surfaced a real bug:** `base`'s eager note claimed its cut content "survives in the GLOBAL
  `~/.claude/skills/base` copy… full body" — **FALSE** (`diff -q` identical, no copy mechanism). Fixed +
  guarded: **doccheck 18th check `no-phantom-global-skill-body-claim`** + 3 regression tests.
- **C. ui-testing MERGE (#28).** Unique parts → siblings (Pre-Flight Checklist + a11y automation to
  `ui-web`; checklist to `ui-mobile`); contrast tables dropped as dup; skill cut; `skill-profiles.json`
  react-web/react-native profiles updated. Harvest in-repo + verifiable.
- **D. doc-sync + cleanup.** #26 (observatory + mnemos SKILL synced to Phase 2). #29 (design-principles
  "Skills — keep" list marked **SUPERSEDED by ADR-0008** — was a pre-audit snapshot naming 10+ cut
  skills). Deleted 2 stale squash-merged remote branches (`feat/distribution-self-sufficiency`,
  `focus-004-content-audit`).

### The through-line: read-first paid off 3×
Every delivery-entangled trim was read-first per the rule-over-read lesson, and it caught what
pattern-matching would have shipped: (1) base's phantom global-copy claim, (2) the python-audit premise
drift (`pyproject.toml` now exists in sub-packages — TRIM still held), (3) design-principles' stale
keep-list. **Carry forward: skill/knowledge/delivery decisions stay read-first, single-decision.**

### NEXT (in order) — nothing started
1. **Friction-detector Phase 3** — action-link + divergence surface (tie each correction to the action
   it was about). The real remaining build; higher value. Follow-on now Phase 2 signal is trusted.
2. **Refine `skill-profiles.json`** vs the full KEEP set (low-stakes tidy).

### The open delivery question (blocks further "trim-on-survives-globally" moves)
**Skill-body delivery has no copy mechanism** (observatory finding, this session). `bin/tessera-new-project`
curation toggles skills on/off via `skillOverrides` — it never copies bodies; no `install.sh`/script
writes to `~/.claude/skills`. So "trim here, full body serves downstream" (the TRIM rationale) rests on
plumbing that doesn't exist. The trims done were still safe (this copy only harms the framework session;
downstream never received it by copy). **But do NOT trim any further delivery-entangled skill on the
"survives globally" rationale until the delivery-mechanism design session settles it** — see
`docs/observatory.md` → "Skill registry — which copy is source of truth" + "Skill-body delivery has no
copy mechanism".

---

## ═══ SESSION 2026-07-17 — Phase 1 + cohesion contract + skill removals (9/10) + template alignment ═══

**ALL MERGED to `main` (#19–#23). Suite green, doccheck 17/17, `tessera-watch` quiet (P7 snoozed). No branches in flight. Skills 57 → 48.**

### What shipped

**A. Friction-detector Phase 1 (spec 13) — #19.** correction recall un-blinded: keyword regex →
local **qwen3:8b** classifier on the passive ingest pipe. Heavy session `b6d7b6f5` went
`correction_density 0.000 → 0.219` (hand-labeled truth 0.188); clean sessions stay 0; spread across
~24 dogfood sessions is now 0.00–0.35 (was 0.00–0.06, blind). Three scope corrections found while building:
- **3B tier-classify model is USELESS here** — it parrots the prompt's ending polarity (constant-yes/no).
  Needs **qwen3:8b + `think=false`** (reasoning model; without it burns num_predict on a hidden `<think>`).
  Fails open to regex. Override: `MNEMOS_CORRECTION_MODEL`.
- **Injected user turns were counted as corrections** — hook feedback (`isMeta`) + task-notifications
  (`promptSource=system`) now tagged `user-meta`, excluded from numerator AND haziness denominator.
- **Latency was never real** — Stop hook is backgrounded (`& disown`) + incremental, so a live Stop
  classifies only new turns; full `--reclassify --all` backfill of ~26 sessions = 81s. No batch/cap needed.
- Review fix: disable the classifier after **3 consecutive** nulls, not the first (one blip was silently
  regex-only'ing the rest of a backfill).
- **`tessera-watch` P10** self-fires the deferred haziness band re-tune at ≥40 real-signal sessions
  (24 now → ~16 runway) → spot-check precision first, THEN decide bands + the 0.30 weight.

**B. Three-project cohesion contract — #20.** `docs/contracts/three-project-cohesion.md` — canonical
map of the **substrate/pattern/policy** stack: Conclave (serving + `divergence.py` instrument) /
pr-arbiter (multi-role union-recall review) / Tessera (governance + routing decisions). Tessera hosts as
coordinator; **hosting ≠ ownership**; runtime peers; lane-change needs that project's sign-off. Contains
layering table, 5 seams w/ owners, sequence (live/parked/ADR-gated), the **4 anti-conflation guards
verbatim**, Open decisions **D1–D4**. A coordination MAP, not an ADR — decisions surfaced, deferred.
- Resolved `council-review`'s pending roster/config decision → points at the contract (D1), flagged its
  **plan-validation** path is *select-best* → NOT shielded by guard (a) (unlike union-recall PR-review).
- Peer stubs point here: `../conclave/docs/INTEGRATION.md` (existed), `../pr-arbiter/docs/INTEGRATION.md`
  (authored this session, committed via a pr-arbiter session).

**C. Skill removals — 9 of 10 (ADR-0008) — #22.** HARVEST-before-CUT. Cut: `session-management`,
`code-deduplication`, `agent-teams`, `cross-agent-delegation` (ideas in design-principles Fossil lineage /
polyphony / icpg); `codex-review` + `gemini-review` (patterns → observatory convergence note);
`autonomous-testing` (→ observatory radar note); `ai-models` (skip-with-rationale); `build-in-public`
(corpus skill only — live plugin infra kept). **#10 `code-review` bulk still gated on D3.** `build-in-public`
writing-guidance harvest handed off for the plugin repo.

**D. Template/init alignment (ADR-0008/0009) — #23.** Dropped only `polyphony` from the downstream eager
block (kept `iterative-development`+`security` eager — they *fit* a downstream app, unlike framework-Tessera;
`@eager` ≠ "available"). Rewrote `initialize-project.md` Step 2/4 from the copy model → ADR-0009 selector.

**E. A FRICTION lesson, and its remedy — #22.** The `agent-teams` cut deleted 6 role files a KEPT command
(`spawn-team`, polyphony's) depended on — Lorenzo caught it, no check did. Root cause named: **rule-over-read**
(apply a documented rule by pattern-match instead of reading the specific artifact + checking its premise
holds here). Remedies landed: doccheck **`template-skill-refs-exist`** (17th check — catches `@`/`~/` skill
paths to deleted skills), observatory FRICTION finding, and a widened **`rule-over-read` memory**. The
eager-block over-application (D) was the same pattern, caught the same way. **Carry forward: skill/knowledge
decisions get read-first, single-decision, no batching.**

**F. Doc hygiene (end of session).** Promo HTML mosaic (dropped 6 cut skills, fixed eager flags to match
base+mnemos); `claude-bootstrap-reference` disclaimer (audit done, corpus now 48); this handoff.

### NEXT (in order)
1. ~~**Friction-detector Phase 2 — typing**~~ **DONE — #25 (2026-07-18).** Types each detected
   correction (misunderstood/defied/overreached/wrong) via a second qwen prompt on already-detected
   corrections; new `claude_turns.correction_type` col + ADD-COLUMN migration; `haze --explain` rollup;
   VIEW-ONLY (composite untouched, verified 0.219 on b6d7b6f5). **Phase 3 (action-link + divergence
   surface) deferred** — see spec 13.
2. ~~**Delivery-entangled trims** — `python` TRIM, `ui-testing` MERGE~~ **DONE (2026-07-18).**
   `python` TRIM #27 (222→81 ln); `ui-testing` MERGE this session (Pre-Flight Checklist + a11y
   automation → `ui-web`; checklist → `ui-mobile`; contrast tables dropped as dup; skill cut;
   `skill-profiles.json` react-web/react-native profiles updated). **Read-first paid off twice:** it
   surfaced base's phantom global-copy claim (fixed + guarded, #27) and, here, that
   `design-principles.md`'s "Skills — keep" list (§128–132) is a **pre-ADR-0008 snapshot** still
   listing 7 now-cut skills — a holistic drift flagged below, NOT partially edited.
3. **Refine `skill-profiles.json`** vs the full KEEP set (low-stakes).
4. **Friction-detector Phase 3** — action-link + divergence surface. Follow-on once Phase 2 signal trusted.
5. **Doc-hygiene: `design-principles.md` "Skills — keep" list is pre-ADR-0008** — §128–132 lists
   `codex-review`, `gemini-review`, `agent-teams`, `cross-agent-delegation`, `session-management`,
   `code-deduplication`, `ui-testing` as KEEP, all since cut. Needs one "superseded by ADR-0008 —
   see the audit" marker, not per-skill surgery. Also `claude-bootstrap-reference.md:295` +
   `design-principles.md:910` list `ui-testing.md` (both are dated snapshots w/ disclaimers).

**MOVED OUT — S2 divergence build is NOT Tessera work (drift fix 2026-07-18).** Prior NEXT #1 said
"design + build the scoring variant of `divergence.py`." Per `docs/contracts/three-project-cohesion.md`
**S2**, that instrument is **Conclave-owned** (`../conclave/orchestrator/divergence.py`); the scoring
function is co-owned with pr-arbiter. Tessera's only piece of S2 is the **consumer** — the *"is
review-fan-out worth it?"* gate, i.e. **decision D2**, which is *surfaced, not decided*, and
evidence-gated on the metric existing in the peer repo. So it's a `../conclave` build + a deferred
Tessera decision — **not** an in-repo NEXT. See "Deferred with their own triggers" below.

*(The "10 removals" are 9-done — #22. Only `code-review` bulk remains, gated on D3. `workspace` +
`team-coordination` were never in the 10; they're separate removal candidates.)*

### Deferred with their own triggers (not "next")
- **S2 divergence build (`../conclave`) + decision D2** — the union-recall scoring variant of
  `divergence.py` is a **Conclave-repo build** (instrument owner; scoring fn co-owned w/ pr-arbiter).
  Tessera's piece is **D2**, the *"is review-fan-out worth it?"* gate: *surfaced, not decided*,
  evidence-gated on the metric existing. Do the build in a `../conclave` session; D2 firms once its
  result lands. Validates pr-arbiter's thin headline (guard (d)). Was mis-filed as in-repo NEXT #1.
- **Three-project ADR — D1/D3/D4** — evidence-gated: D3 needs pr-arbiter **Phase 3** (8–15h annotator
  pilot) + a **standing conclave fleet**; D4 (pr-arbiter adopts `.tessera/`) trips `tessera-watch` P4 at 5
  downstreams. D1 (routing home) firms with D2's result. See the contract's Open decisions.
- **P10 haze-recalib** — self-fires at 40 real-signal sessions → precision spot-check + band re-tune.
- **`should_fire` passive extraction** — apply spec-13's pattern to retire the dead labeling path.
- **Team-spawning feature seam** *(needs a call — read-first)* — ship it downstream (wire `install.sh` +
  activate polyphony) or retire (cut spawn-team + the `templates/agents/` roles). See observatory.
- **Canonical setup entry point** *(needs a call)* — `/initialize-project` (interactive) vs
  `bin/tessera-new-project` (greenfield); `install.sh`/`GETTING_STARTED` advertise only the former.
- **`code-review` bulk removal (#10)** — gated on D3. `templates/codex-auto-review.sh` deferred there too.
- **De-dup the registry / Listing-budget floor / P7 (snoozed 2026-08-31) / Mnemos compaction-recovery
  (→ real CLI venue)** — carried from prior sessions; own venues.

---

## ═══ SESSION 2026-07-16 — delivery reframe shipped, + a deep friction-instrumentation thread ═══

**ALL MERGED to `main` (12 PRs). Suite green, doccheck 16/16, `tessera-watch` quiet. No branches in flight.**

### What shipped, by arc

**A. FOCUS-004 delivery (the headline).** #4 (audit + ADR-0008 + adr-gate), #5 (safe bucket: fossil
harvests → `design-principles.md`, `base` 532→122, `icpg` 327→246), **#9** (*was #6*; ADR-0009 + scaffold).
- **ADR-0009 refines ADR-0008's mechanism:** Claude Code unions global+project skills, so downstream
  *already sees every skill* — never *undelivered*, just *un-curated*. Fix = a **selector**
  (`skillOverrides` off per profile), NOT a copier. `bin/tessera-new-project` writes it from the
  composable map `templates/tessera/skill-profiles.json` via `scripts/skill_overrides.py`. Verified
  end-to-end (47 off/9 on). Reviewed; fail-loud + universal-inviolable hardening applied.

**B. Eager-load cleanup — DONE.** #8 (`security` ADAPT — de-eager OWASP, keep the secrets floor) + **#11**
(`iterative-development` de-eager). **Eager set is now just `base` + `mnemos`** — the genuinely-universal,
framework-native two. The full skills stay in the registry, on-demand, shipped downstream via curation.

**C. Mnemos trial — SORTED.** #7. Fatigue is LIVE (token-util 0.27, not degraded — 07-15 all-None was
transient). Compaction DOES fire here, but via the harness-summarization path with no `{trigger}` (→
`unknown`); instrumented with a key-only `payload_probe`. **DECISION: compaction-recovery verdict → real
Claude Code CLI venue** (P3 can't reach 3 real `auto` events here); fatigue stays here. (`docs/observatory.md`
→ "Mnemos compaction vehicle", 07-16.)

**D. Infra hygiene.** #13 (P1 hook↔template drift, root-caused: an edit wrote the live hook not the
template, and P1 was a SessionStart advisory with no commit block — added doccheck `hooks-match-templates`,
**now uncommittable**). #16 (**`tessera-watch` snooze mechanism** — the G-a-earned remedy; tracked+expiring
+ reason-required; G-a snooze-aware. **Applied to P7, 45d.**).

**E. Design threads SEEDED (noted, not built).** #12 (conclave/pr-arbiter convergence), #14 (haziness
finding), #15 (spec 13). See the friction thread below.

### The friction-instrumentation thread (P7 → should_fire → action-divergence → haziness)
Started from P7's nag; went deep and it paid. Conclusions:
- **should_fire is SOUND** (user-disposition ground truth, real dashboard consumer) — I was wrong to want
  it retired. But its **backlog is dead data** (52 unlabeled across 19 sessions won't be hand-labeled), so
  **P7 is snoozed** (#16), not resolved by labeling.
- **The valuable vector is action-divergence** (did the agent do the *opposite* of what was asked) — the
  friction the framework keeps admitting only a human catches. Its one instrument, Mnemos
  `correction_density`, has **near-zero recall** (#14): a keyword regex that missed *this* session's heavy
  redirection entirely (`correction_density 0.000`). The *pipe* is right (passive, stores evidence); the
  *detector* is blind.
- **The fix for both is passive extraction, never manual labeling.** Scoped: **`_project_specs/13-friction-detector-upgrade.md`**
  (Phase 1 = local-qwen recall detector + backtest; typing/action-linking deferred).

### NEXT (in order) — nothing here is started
> **SUPERSEDED by the 2026-07-17 section above.** Item 1 (Phase 1) shipped as #19; the queue was
> re-ordered (D2 is now the unblocked lead). Kept for the trail.
1. **Friction-detector Phase 1** (`_project_specs/13`) — the highest-value build; instruments the
   action-divergence friction. Recalibrates haziness bands as a side effect (flagged in the spec).
2. **The 10 removals** — HARVEST-first; `codex`/`gemini-review` harvests now have a home (the conclave note,
   #12). `ai-models`→URL pointers, `autonomous-testing`→pipeline note, `build-in-public`→plugin docs. The 3
   Maggy skills (`agent-teams`, `autonomous-testing`, `workspace`) all live here → 0 Maggy after.
3. **Remaining delivery-entangled trims** — `python` TRIM, `ui-testing` MERGE.
4. **Refine `skill-profiles.json`** vs the full KEEP set (starter map; low-stakes).
5. **Conclave design session** (needs Lorenzo) — ADR-0008's open thread; seeded in `docs/observatory.md`
   → "Tessera ↔ Conclave ↔ pr-arbiter". Firms up with a review-flavored divergence measurement + pr-arbiter
   Phase 3. Gates the `code-review` bulk removal.

### Still deferred (own venues)
- **De-dup the registry (D)** — ADR-0009 further deferred it (global stays authoritative). Observatory.
- **Listing-budget floor ("Goal B")** — settings can't zero a skill's listing name; `/doctor`-measure
  before any physical partitioning. YAGNI.
- **P7 gate-labels — SNOOZED to 2026-08-31** (#16). Resurfaces then if the detector upgrade (spec 13)
  hasn't superseded the whole should_fire-labeling approach by making it passive.

---

## Handoff — 2026-07-13 (FOCUS-004 / the skill audit, and what it actually found)

**`docs/adr/0007-skill-corpus-prune.md` (Proposed) is the record. Read it before touching skills.**
Per-skill ledger with evidence: `_project_specs/todos/focus-004-audit.md`.

### The audit did its job, but the findings were NOT in the skills

- **6 skill invocations from the 56-skill corpus, ever** (171 transcripts, 34,636 events) — all
  `code-review`. The other 4 invocations machine-wide are skills *Anthropic ships*. **The
  inherited corpus has contributed exactly one skill, ever.** 22 skills declare `paths:` globs
  that match 0 files here and cannot fire.
- **Two byte-identical registries both load** (`tessera/skills/` + `~/.claude/skills/`), so every
  skill is listed twice. **Tessera is the only project with a local skills dir**; all 20+ others
  use the global one — which means *cutting `tessera/skills/` would not reduce Tessera's context
  at all.*

### What was actually broken — and it was NOT skill debt

1. **`bin/validate-plan` manufactured verdicts out of its own brokenness.** FIXED (`7a725f7`).
   It returned a confident `CHANGES_NEEDED 0/3` because a **missing backend was counted as a
   reviewer voting NO**. Three states now: voted / unavailable / **broken**. Zero usable
   reviewers → **exit 2, no verdict**. `scripts/test_council.py`.
2. **The entire multi-model stack had never run.** FIXED (`ec041d3`). Five `bin/` scripts
   `import httpx`; **httpx is installed nowhere**. `build-in-public-status` would not even
   *compile*. Ported to stdlib `urllib`.
3. **The F-001 detector was a blacklist** — `{mnemos, icpg, polyphony, skill_lint, pytest, yaml,
   requests}`. `httpx` simply was not on it. New check `bin-scripts-are-stdlib-only` names
   nothing and tests by execution: *every module `bin/` imports must be findable by the
   interpreter it actually runs on.* **15 doccheck checks** *(16 as of 2026-07-16 — added `hooks-match-templates`).*

### THE LESSON — and it cost three wrong conclusions

> **I audited whether files sat at the paths the docs claimed, and never once RAN the thing I was
> condemning.** `~/bin/deepseek` was absent, so I called the subsystem dead. It meant the *path*
> was wrong — `deepseek` was on PATH the whole time. **That is F-001's exact confusion:
> `unreachable` misread as `unused`,** which `CLAUDE.md` warns about in those words. Then I said
> "the stack works" because `command -v` found the files — **existence is not function.**
>
> **Every correction came from outside me:** the spec-12 adversary refuted 2 of 4 claims; Lorenzo
> caught the deletion momentum ("what are we short-shrifting?") and stopped me deleting a
> subsystem over a path typo; the *real run* caught a half-fix the tests called green.
> **`tessera-verify stats`: author error rate 38%.**

### ⚠️ THE AUDIT WAS NOT RUN. What ran was a reachability sweep.

**Caught by Lorenzo at the end of the session** — *"rather than reading through the skills there
was a leap to unnecessary and deletion."* **Correct, and it is the same error a fourth time.**

~31 of the 56 verdicts were reached **without reading the skill's body**, on two signals: *its
`paths:` can't match in Tessera* and *it was never invoked*. **Neither judges the skill.** Both
measure **reachability**. Those verdicts are **VOID** (ADR-0007, "The third correction").

- **The invocation argument is circular:** there are **6 invocations machine-wide across ALL
  skills, including Anthropic's own.** That indicts the *discovery mechanism*, not any skill.
- **The frame was wrong:** these live in the **global** `~/.claude/skills/`, serving **20+ repos**.
  **`flutter` SHOULD be inert in Tessera.** That says nothing about its worth to the Flutter repos.
- **So the `paths:`-match scan is the WRONG next step** — more reachability evidence for a
  question reachability cannot answer. **It was previously listed here as item 2. It is not.**

**And this restores the compaction premise.** I declared it falsified ("the audit didn't need the
205k read") — but only because I'd swapped a cheap proxy for the real judgment. **The real content
audit IS read-heavy, exactly as the spec said. FOCUS-004 is still the P3 compaction vehicle.**

**AND THE FLOOR OF IT: USAGE IS NOT EVIDENCE — not a CUT, not even a DEFER.** An earlier draft
said "never fires → DEFER". That still smuggled the signal in; **DEFER is suspicion, and suspicion
is a verdict.** Zero usage carries **zero information**, because the audit *already found what
fully explains it*: **`tessera-new-project` ships ZERO skills** (no delivery path downstream) and
**6 invocations machine-wide across every skill including Anthropic's own** (discovery barely
works). *Once a cause fully explains an observation, the observation is not evidence for anything
else.* The audit wrote both causes down and spent the number anyway.

**It is the same argument that saved the multi-model stack an hour earlier** — *never ran,
directional, framework hasn't got there yet, KEEP*. Accepted for `bin/`, refused for `skills/`.
**That is not a principle, it is a mood.**

> **The 6-invocation finding indicts the FRAMEWORK's distribution and discovery — not the skills.
> It was the audit's headline and it was aimed at the wrong target.**

**The rubric is in `_project_specs/todos/focus-004-audit.md`.** Only *is it true / is it superseded
/ is the guidance good* can CUT. A fourth question — *is it on the path we are building?* — can
only **KEEP**. **If a future session reaches for an invocation count to justify a cut, that is
drift. Challenge it.**

### Where to pick up

0. ~~**RUN THE ACTUAL AUDIT.**~~ **DONE (2026-07-14).** All 56 bodies read in the main thread, judged
   on the 5 admissible questions only. **Record: `focus-004-audit.md` → "═══ FINAL TALLY — REAL AUDIT ═══".**
   Headline: it **near-inverts the void table** — ~44 keep-in-some-form, **10 removals**, every one on
   stale/superseded/foreign-product/vendor-manual grounds, **zero on reachability**. Three verdicts flipped
   from reading current state (council-review CUT→FIX, iterative-development CUT→KEEP, cpg-analysis CUT→KEEP).
   **The real finding stands and is now content-confirmed:** the corpus is mostly *good, current,
   downstream-applicable* — but undeliverable, because `bin/tessera-new-project` ships **zero** skills.
---

## ═══ FOCUS-004 EXECUTION STATUS + POSTURE (2026-07-15) — read this to resume ═══

**Record of decisions:** ADR-0008 (supersedes 0007). **Per-skill ledger + harvest manifest:**
`focus-004-audit.md` → "REAL AUDIT" + "FINAL TALLY". **Verdict: keep 46, remove 10** (all removals
on stale/superseded/foreign-product grounds — **never** on reachability).

### The working method (agreed with Lorenzo 2026-07-15)

The 56-body audit already answered *"is each skill good"* (in the ledger). What execution adds is the
**forward-posture pass** — every destructive item resolves to ONE of three, and **the design note is
written BEFORE the cut, not after**:

1. **CUT CLEAN** — genuinely don't need the capability. *(e.g. `ai-models` — native `claude-api` covers it.)*
2. **ROLL OUR OWN → write the design-note/spec stub FIRST, then cut.** We want the capability, this
   version is wrong. *(e.g. `agent-teams`' step-enforcement → capture as Stop-hook kin before deleting;
   `code-review` multi-engine → conclave note before the bulk goes.)*
3. **LOG TO OBSERVATORY** — might want it later, not now. *(e.g. `autonomous-testing`'s pipeline shape.)*

This is *harvest-before-cut* **plus** *replacement-posture-before-cut*. It is the antidote to "cut
something we need in two months."

### Buckets (by risk, not by phase)

- **Mechanical, zero corpus risk (do anytime):** the FIXes + the *safe half* of D.
- **Low-stakes judgment (nothing leaves the corpus):** TRIM `base`/`python`/`icpg`, ADAPT `security`,
  MERGE `ui-testing` → decide *what within* survives; wrong = re-add, not lost.
- **Judgment-heavy, forward-posture protocol, don't rush:** the harvests + the 10 removals (A/B).
- **Design sessions (need Lorenzo):** delivery mechanism, skill instrumentation, Tessera↔conclave.

### DONE

- ✅ Audit + ADR-0008 + `adr-gate` split (#8) + `supabase-python` glob FIX → **PR #4** (10 commits).
- ✅ **FIX `council-review`** (2026-07-15): paths `~/bin/`→`bin/`; dropped the Maggy-dashboard ref;
  flagged the design-blocked parts (absent `council.yaml`, no `claude-fable-5` wrapper, `codex` absent)
  as *illustrative pending the conclave design* — **not rewritten** (conclave session reshapes it).
- ✅ **FIX `code-graph`** (2026-07-15): corrected the config claims — backend is live (MCP tools exposed)
  but configured **globally**, not via a committed `.mcp.json`; `install-graph-tools.sh` absent.

### DEFERRED / NEEDS-DESIGN — and WHY (this is the "don't lose it" part)

- ⏸ **D · de-dup the skill registry → BLOCKED on the delivery-source decision (E).** The two copies
  (`tessera/skills/` 57, global `~/.claude/skills/` 56) **have now DIVERGED** — this session added
  `adr-gate` + FIXes to the tessera copy only. So de-dup is no longer "delete the identical copy"; it
  *is* the question "which registry is authoritative for downstream delivery." **Do not delete either
  until delivery is designed.** → Observatory: "Skill registry — which copy is source-of-truth."
- 🎨 **D · the `skill-declared-backends-exist` doccheck check → NEEDS DESIGN, do not implement naively.**
  A literal "every binary a skill names must exist here" check **re-commits the exact reachability error
  the audit was about** — it would flag every downstream stack skill (`vercel`, `gh`, `supabase`…). The
  *correct* check lints the **fail-open PATTERN** (imperative "do not skip / mandatory / 0-of-3 → revise"
  gating language tied to an external backend), repo-local, no binary-existence. That's a design task.
  → Observatory: "Fail-open skill lint (the check council-review earns)."

### NEXT (in order)

1. **Low-stakes judgment bucket** — TRIM/ADAPT/MERGE (safe, nothing leaves).
2. **Harvests** (fossils→design-doc, `ai-models` pointers, `build-in-public`→plugin, vendor→conclave note)
   via the posture protocol.
3. **Then the 10 removals** — each already has its posture in the ledger's harvest manifest.
4. **Build the delivery path** — `bin/tessera-new-project` ships the KEEP set, profile-gated. **The fix
   the whole audit points at, and the gate on de-dup.** *(Design session — needs Lorenzo.)*

*(The numbered items below predate ADR-0008. **Superseded/done:** old #2 paths-scan (the content audit
replaced it), old #3 "22 authorized cuts" (audit says keep most), old #5 supabase-python (FIXed).
**Still live:** old #1 conclave = E above; old #4 `bin/kimi` broken.)*

---

## ═══ MNEMOS TRIAL — side-mission result (2026-07-15) ═══

> **⚠️ SUPERSEDED 2026-07-16 (#7) — kept for the trail.** Both gaps below were re-checked and the
> reading corrected: fatigue is LIVE (not degraded); compaction DOES fire here (via the no-`{trigger}`
> harness path). See the "Mnemos trial — RESOLVED this session" block at the top and `docs/observatory.md`
> → "Mnemos compaction vehicle" (07-16 update). The "NEXT SESSION" items below are done.

**This FOCUS-004 session was deliberately run long (side mission) to overfill context and test Mnemos's
compaction-recovery. RESULT: auto-compaction did NOT fire — a ~200k-token overfill produced zero
Mnemos-visible `compaction_fired` events dated this session.** Full finding + hypothesis + next-session
checks: **`docs/observatory.md` → "Mnemos compaction vehicle — does Claude Code auto-`/compact` even
happen in this harness?"**

- **Likely cause:** this harness manages context via its *own summarization* (system-prompt-stated), a
  different mechanism from Claude Code `/compact` — the only thing Mnemos's PreCompact hook instruments.
  So Mnemos may be watching a door this harness never opens. **Filling more won't help** — we already
  massively overfilled.
- **Second gap:** `fatigue.json` is all `None` — fatigue runs *degraded*, not dark. The statusline isn't
  writing token metrics, so the token-util dimension (0.40 weight) is blind; the behavioral dims still
  compute (a forced checkpoint scored **0.29**). Narrow fix: the statusline→`fatigue.json` token write.
- **What worked:** SessionStart restore (loaded at startup) + Stop-hook checkpoint (`941b43b7` today).
  Resume-across-*sessions* works; recovery-across-*compaction* stays untested (trigger never occurred).
- **NEXT SESSION — pick up:** (1) confirm whether this harness ever invokes `/compact`, or point Mnemos
  at the signal that *does* fire (or evaluate the recovery layer on a real Claude Code CLI session);
  (2) fix why `fatigue.json` isn't being written; (3) P3 consequence — if auto-compaction can't fire
  here structurally, the compaction-half of the Mnemos verdict needs a different venue.

---

## Housekeeping — deferred to next session (2026-07-15, context too full to do now)

> **⚠️ SUPERSEDED 2026-07-16 (#16).** P7 is **snoozed to 2026-08-31**, not labeled — the backlog is dead
> data and the real fix is the passive detector upgrade (spec 13). The note below is kept for the trail.

- **P7 gate-labels: ~45 unlabeled post-backstop gates.** `tessera-watch` flags it (≥20 threshold).
  Byproduct of a heavy-decision session (9 gates logged). The friction-journal review that tunes the
  #17 backstop precision — label each `should_fire` true/false (genuine gate vs noise). Distinct
  maintenance pass; nothing else depends on it. Resolve or snooze via the dashboard / observatory.

1. **The Tessera ↔ conclave design session.** *(ADR-0007, "NOT decided".)* The stack is a
   **directional keep** — more local models coming, Tailscale + AWS-hosted, **council/ensemble
   review is the path**. conclave is itself a multi-model stack. Shared council / isolated /
   one fronts the other = **ADR-weight, and deliberately not decided in a prune ADR.**
   *Now unblocked: the stack RUNS and FAILS HONESTLY, so this can be designed against a working
   mechanism instead of a phantom.*
2. **The `paths:`-match scan across all 20 repos.** The measurement that decides the **22
   deferred stack skills** (`flutter`, `supabase*`, `react-*`, `android-*`, …). They are dead
   *in Tessera* and **unmeasured elsewhere** — an invocation count is structurally blind to a
   `paths:` auto-load. **Cutting them without this scan is drift; challenge it.**
3. **Execute the 22 authorized cuts** — the Maggy corpses and stale/superseded skills. Safe,
   mechanical, evidence in the ledger.
4. **`bin/kimi` is broken** — it `exec`s `~/.local/bin/kimi`, which does not exist. Recorded,
   not fixed; it matters to item 1.
5. **`supabase-python` is misfiring** — its `**/*.py` glob matches 123 Python files here. It
   surfaced itself, live, during this very session when a `.py` file was written.

### What NOT to do

**Do not cut the multi-model stack.** It was condemned in the first draft of ADR-0007 and that was
wrong. It is kept on purpose. **Do not re-litigate it without the design session.**

---

## Handoff (2026-07-12, end of the F-001 session — SUPERSEDED, kept for the trail)

**Full accounting: `docs/postmortem-2026-07-12.md`.** One document, the whole story — what
happened, the ten bugs, why each rule failed, the mechanism ranking, the numbers, and the
direction. Start there. The formal decision is `docs/adr/0006-instrumentation-not-control.md`;
the evidence base is `docs/observatory.md` → "Fail-open everywhere".

### What actually happened

A venv fix became a 90-minute rathole of fixes-on-fixes. Three rounds of "it's closed" were
each refuted by an **independent session** verifying from a clean context. Every refutation was
correct.

**The rathole was not about Python.** It was that *nothing in Tessera reports its own failure*,
so every fix required a fresh adversarial read to find the next silent thing. Eight bugs in one
session; **not one announced itself.** See the observatory table.

### The two that actually mattered

1. **THE SPEND GUARD WAS FAILING OPEN.** On a `/usr/bin`-first PATH, `python3` is macOS 3.9;
   PEP-604 annotations raise `TypeError` at definition time; `guard.py` exits 1; the wrapper
   passes that through as "not 2" — which Claude Code reads as **ALLOW**. *An unauthorized GPU
   boot proceeded.* This is **the** precondition for unsupervised spend, and it was broken.
   Fixed (`from __future__ import annotations`) + checked (`safety-scripts-run-on-system-python`,
   which **executes** on 3.9 — `ast.parse` passes, PEP-604 only explodes when *evaluated*).
2. **The spend backstop shipped DISABLED to every clone.** `.spend-backstop-fires` was committed
   holding **5** against a `MAX_FIRES` of **3**. It would never have fired, anywhere, ever.

**Both were caused by me, both were invisible to the framework, and both were found only because
Lorenzo asked for independent verification.**

### The rule that broke, and the one that replaced it

The worst bug was **built by a carve-out I wrote**: *"the gate/spend hooks may use bare `python3`
— they're stdlib-only and must survive a broken venv."* That sentence is the bug. **Stdlib-only
is NOT version-independent:** when the interpreter NAME drifts, the VERSION drifts with it.

> **New standing rule: a carve-out from a safety invariant must ship with a check that the
> carve-out holds.** And: **a mechanism that fails OPEN needs a paired detector that fails LOUD.**

### Where to pick up — in this order, in SEPARATE sessions

0. **READ `docs/adr/0006-instrumentation-not-control.md` FIRST.** It retargets the framework:
   *Tessera does not make the agent reliable — it makes the agent's unreliability visible and
   bounded.* It ranks the five mechanism tiers by their actual record under a full night of
   adversarial pressure, withdraws ADR-0005's readiness claim, and sanctions pruning. **Every
   item below is downstream of it.**

1. ~~**Adversarial verification — `_project_specs/12-adversarial-verification.md`. BUILD THIS
   FIRST, BEFORE SPEC 11.**~~ **SHIPPED 2026-07-13** — `bin/tessera-verify` + fail-LOUD Stop-hook
   trigger + `verification` event contract + doccheck `verify-scan-is-wired`. The hook fired
   unprompted on the session that built it (criterion 2, live); the falsifier confirmed 4/4
   claims with landmines walked; `--self-test` refuted its planted landmine (criterion 5).
   **Remaining: criterion 1 — Lorenzo's manual acceptance replay of the three 2026-07-12
   refutations, deliberately human-witnessed (ADR-0006: watch a channel fail before trusting
   it).** Spec's "Shipped" section has the full evidence.

2. **PRUNE — and FOCUS-004 *is* the prune. One item, not two.** *(ADR-0006 §5, sanctioned work.)*

   **Why this outranks spec 11, by ADR-0006's own ranking:** pruning is **tier 1** (make the bad
   state unrepresentable — *deleted machinery cannot fail silently*). Spec 11 is **tier 4**
   (detect the failure of machinery we chose to keep). **Prevention beats detection, and the ADR
   says so.** Practical consequence: spec 11 scopes five components — **if the prune kills one,
   you will have instrumented a corpse.** Prune first, and it tells spec 11 what is actually
   worth watching.

   - **FOCUS-004 — 56 skills, zero ever evaluated**, overdue by principle #15. Still the only
     honest path to a real `auto` compaction: **205,085 tokens measured** across the corpus vs a
     ~166k threshold (verified, not repeated). **The Mnemos trial counter is genuinely 0** — and
     P3 was silently counting an *unclassifiable* compaction as evidence until it was fixed on
     2026-07-12.
   - **The gate apparatus** — recorder + Stop-hook scanner + ratio + `should_fire` labeling is
     four moving parts to answer *"did Claude ask before deciding."* At least one too many.
   - **Mnemos itself.** The kill/keep trial has run for **months** and has **never produced a
     valid verdict**. Until 2026-07-12 its hooks wrote through a *drifting interpreter*, so any
     earlier verdict would have measured broken machinery. *"We cannot judge it"* is itself a
     finding, and the trial is long overdue.

   **Two disciplines, both learned the hard way:** (a) **audit, do not repair** — recording a
   broken skill is the job; fixing it is how tonight became a rathole. (b) **I must not certify
   the compaction restore myself** — that is the "verify with the instrument under test" failure,
   three times over. The verdict comes from the compaction log + P3, or from spec 12's adversary.

3. **Fail-open detection — `_project_specs/11-fail-open-detection.md`. SCOPE AND ORDERING ARE
   WRITTEN DOWN THERE. Read it before starting.** *And scope it to what SURVIVES the prune.*
   Five components (spend guard, spend backstop, gate-scan, Mnemos hooks, doccheck) — **not** the
   54 bail-out sites. Mechanism is ~35 lines (`tessera-degraded` + watcher P10); the substance is
   the chaos tests and the classification.
   **THE ORDERING IS THE POINT: write the break-it-on-purpose tests FIRST and watch them all
   fail.** The 2026-07-12 session built a detector and then verified the fix *with the detector
   that had the hole* — three times, reporting green each time. If a future session proposes
   building the mechanism first, **push back and point at spec 11.**
   **Bar for done (binary): break a component on purpose → Tessera says so within one session,
   with no human asking.** Nothing on 2026-07-12 would have met it.

4. **Ship the portable doccheck core downstream.** 7 of 13 checks are portable
   (`no-bare-python3-with-toolchain-import`, `safety-scripts-run-on-system-python`,
   `runtime-state-is-not-tracked`, `test-command-is-not-a-bare-interpreter`,
   `ignored-test-suites-are-run`, `spend-guard-is-wired`, `spend-backstop-is-wired`); 6 are
   Tessera-only. **`bin/tessera-new-project` mentions doccheck zero times**, so conclave, howler
   and tess-dashboard have the spend guard and the backstop but **not the checker that verifies
   either is wired**. That violates the "ship both halves or neither" rule written in
   `tessera-new-project`'s own comment. Bounded: ~one session.

5. ~~**Re-open ADR-0005's readiness claim.**~~ **DONE — ADR-0006 withdraws it.** Its Tier-1
   reordering stands; its *preconditions-met* framing is retracted. Two of three were broken and
   undetectable.

### Session findings 2026-07-13 (P7 labeling session)

- **P7 resolved:** 40 of 44 post-backstop gates labeled inline (`should_fire` +
  `should_fire_basis` + `labeled_ts`), 4 honestly null. Rubric: user's recorded disposition,
  verbatim quotes. Adversary sample-check: 2 CONFIRMED, 1 PARTIAL — caught a typo-corrected
  composite quote, fixed to verbatim, rule added to gate-event.md. Notable calibration hit:
  heaviside `voicing-defaults` was **held and should have fired** (user pushback followed).
- **BUG FIXED same session: `hooks/subagent-route-hook` broke ALL Agent tool calls** whenever
  a CLAUDE_* tier was cached and no explicit model set — `updatedInput` REPLACES tool input
  wholesale, and the hook emitted `{model}` alone, stripping `prompt`/`description`. Fixed by
  merging (`.tool_input + {model}`), guarded for null/empty/non-object `tool_input` and
  multi-document stdin — the null-input guard exists because the **first adversary run REFUTED
  the fix** (jq's `null + {model}` re-opened the bug through a side door). Verified: live spawn
  green, `tessera-verify` CONFIRMED merge + explicit-model-wins + fail-open across 14 degenerate
  shapes.

> **Ordering note, recorded because it drifted once already.** FOCUS-004 sat at #4, was argued up
> to "defensibly second", then **sank to last by accretion** when ADR-0006 added three items above
> it — with no decision and no announcement. Lorenzo caught it. It is now #2 **on principle, not
> position**: pruning is tier 1, spec 11 is tier 4, and ADR-0006 ranks prevention over detection.
> **If a future session finds FOCUS-004 drifting down the list again, that is drift, not a
> decision — challenge it.**

### What NOT to do next

**Do not keep fixing.** The rathole instinct was right. Everything is committed, pushed, green,
and the one live safety hole is closed. The next move is *design*, not repair.

---

## Handoff — 2026-07-12 (spec 06 / escalation backstop / venv, chronological)

**Spec 06 shipped — but not the spec that was written. It was retargeted first, and that was
the whole job.**

### The spec did not solve the problem it was promoted for

ADR-0005 promoted spec 06 to Tier 1 on one finding: *an unsupervised agent in conclave is an
agent that boots GPUs on its own.* But spec 06's mechanism, written in April under its old
Tier 3 framing, was a **Claude token meter** — declare `tokens`/`api_calls`, accumulate from
the transcript, hard-stop. **A token budget cannot stop `terraform apply enable_gpu=true`.** The
agent commits hundreds of dollars inside a few thousand tokens. All five of its success
criteria were token-denominated; none mentioned cloud spend. **Built as written, it would have
shipped green with the GPU boot path wide open.**

Worse — its Step 4 hard-stopped by *"rejecting further Edit/Write/Bash."* **Teardown is a Bash
command.** It would have frozen an agent with a live GPU and blocked its own teardown, *causing
the runaway it existed to prevent.* That produced the invariant the guard is now built around:
**a spend gate must never be able to block the exit.**

The token budget is real but minor, and it is a different mechanism. Split out to **spec 10**,
Tier 3, with an honest note that there is *no evidence it is worth building* (12 sessions, all
`clear`, max haze 0.09 — the agent does not flail).

### What shipped

- **`bin/tessera-authorize`** — a human grants a run-scoped envelope (`--usd 20 --ttl 4h`).
  **This is the piece that converts conclave from supervisable-only to unsupervised:** it
  collapses 14 synchronous boot gates into one up-front authorization.
- **`scripts/spend/guard.py`** + PreToolUse(Bash) hook — deny-by-default on spend-committing
  commands. **Teardown always allowed, unconditionally.** Denied → spec 07 escalation.
- **The TTL is enforced; the dollar figure is not.** Tessera cannot meter dollars; AWS can, and
  does. Tessera gates *authorization*, AWS meters *spend*. Three layers, three trust domains —
  don't collapse them.
- **We did not rebuild the ceiling.** conclave already had one (`budget.tf` → SNS →
  `hardstop.tf` lambda; `gpu.tf` idle-stop; tag chain verified end to end). It is *out-of-band*,
  outside the agent's trust domain, and strictly stronger than a hook. What it lacked was
  per-run *authorization* — a monthly cap bounds blast radius, it doesn't decide if the boot
  should happen.
- Wired into tessera + conclave + `templates/` + `bin/tessera-new-project`, each **verified by
  invoking it**, not by checking that files copied.

### Three things live-fire found that reasoning did not

Every one came from *running* the guard. None from reading the design.

1. **A live hole in the flagship downstream.** `conclave/scripts/sweep-gpu-capacity.sh:23` runs
   `terraform apply -auto-approve` — it boots g6e GPUs, it's the AZ-sweep from the gate log, and
   the guard saw only the wrapper's *name*. **A classifier that reads the command but not what
   the command runs is checking the wrong text.** Now reads local scripts one level down.
2. **The guard blocked its own wiring commit — and I misread the result.** The install command
   quoted a boot command in a test string, so the guard blocked the *whole* Bash call and
   **none of the wiring ran**. The probe that followed reported `allowed` for a GPU boot,
   because the wrapper fails open when the guard is absent. *It looked like a working guard
   saying yes. It was a missing guard saying nothing.* Caught only by checking disk.
3. **The guard blocked `cp guard.py test_guard.py`** — it followed the `.py` token, opened the
   *test file*, and found a boot command quoted in a fixture. **Naming a script is not invoking
   it.** Scripts are now followed only in *command position*. `git add`, `cat`, `vim`, `cp` on a
   script are no longer boots.

### The false-positive posture changed — v1's noise was buying less than it looked like

v1 classified raw text, so a *mention* read as an *invocation*. It produced **four false
positives against its own author in one session** (a test heredoc, the conclave install command,
the commit message describing the guard, the gate-log entry describing the false positive).

The defence of that noise was "stripping quotes opens `bash -c` as a bypass." **Checked rather
than trusted: the no-evasion property was already only partly true** — `echo "…" | bash` splits
to a bare, neutral `bash` segment either way. So quoted text and heredoc bodies are now data,
*unless the command is wrapper-led* (`bash -c`, `python3 -c`, `eval`, heredoc→shell), where they
are code. **Wrapper-ness is global, never per-segment** — `python3 -c "a; b"` splits on the `;`
inside its own quotes; judging that fragment alone reopens the bypass. That mistake was made and
caught by tests before shipping.

**Residual, deliberate:** `echo "…" | bash`, cloud-SDK calls, and script-calls-script are not
caught. This guard stops an agent booting a GPU *by mistake or without authorization*; it is not
built to defeat one actively evading it, which has easier routes. Layer 3 bounds those.

### A finding about the checker itself

`doccheck` gained **`ignored-test-suites-are-run`**, and it is a finding, not just a check. The
2026-07-11 *"test command ran 6 of 12 files and reported green"* bug was fixed **without leaving
a check behind** — which is the one thing doccheck's standing rule forbids. The rule was
violated by the commit that fixed the bug the rule exists for. Adding `scripts/spend/` to the
`--ignore` list nearly repeated it. Now: `--ignore` a suite without running it → doccheck fails.

Also added: `spend-guard-is-wired` (the doc claims a hook; is it in settings.json?) and
`spend-auth-is-not-tracked` (a committed grant would authorize spend on every clone, forever,
past its own TTL). **8 checks, 0 false claims.**

### The escalation backstop — spec 06 falsified the reason it was deferred

`docs/contracts/escalation.md` deferred the backstop on this premise: *"a blocked agent cannot
proceed, so the failure mode is not silence but a summary that isn't a packet."* **Spec 06 made
that false.** The guard denies **one tool call** — the agent can do other work, take an offline
path, or just move on, and the denial vanishes with it. The trigger was never really "the first
unsupervised run"; it was **the moment a block stops halting the agent**, and spec 06 was that
moment. I shipped a mechanism whose deny path ended in *prose* ("raise a packet"), i.e. model
recall — the exact trigger that missed ~85% of gates.

**BUILT.** Stop hook → `scripts/spend/backstop.py`. A denial must end in a grant (supervised) or
a packet (unsupervised); **neither → exit 2**. A grant *before* the denial doesn't count — an
expired envelope is what caused it. Better-conditioned than the gate-scan: `spend_denied` is a
*logged event*, not a text heuristic, so there is nothing to adjudicate away. The one quiet
disposition it invites is *"that was a guard false-positive"* — **a backstop that forces a bogus
packet is worse than none.**

### The suite was manufacturing the evidence

Found by reading the log the backstop was about to fire on: `guard.main()` → `_log_denial()` →
`emit()` keys on `CLAUDE_CODE_SESSION_ID`, **which is set under a real session** — so every hook
test wrote a *real* `spend_denied` to the production log. **26 of this session's 31 denials were
made by pytest.** An 84%-polluted friction journal, and a backstop poised to fire on its own
tests.

This is the P3 trigger-tagging lesson in a new costume: **a test must never become evidence about
the thing it tests.** There, a hand-run `/compact` could have delivered the Mnemos verdict on
manufactured data. Here, pytest was manufacturing the spend journal. Fixed at the root
(`scripts/spend/conftest.py` strips the session id suite-wide, so `emit()` is inert by
construction) and pinned by a test, so no future test can pollute by forgetting to mock.

**Today's log still contains that test noise — it was not rewritten.** Treat spend-denial counts
before 2026-07-12 as unusable; the journal is honest from here.

### The venv landed — F-001 is closed, and it bit me *during the fix*

Opened 2026-06-26. Resolved 2026-07-12 on a **uv-managed** interpreter (`.python-version`
tracked, base under `~/.local/share/uv/python/`, brew cannot touch it). Toolchain removed from
Homebrew's python entirely; console scripts symlinked into `~/.local/bin`, which **precedes**
`/opt/homebrew/bin` — `tessera/bin` does **not** (position ~17, behind brew), so a symlink there
would have been silently shadowed while everything *looked* fixed.

**My first recommendation was a brew-based venv, and it was wrong.** Reflex ("don't add a
dependency") applied without checking whether the cheap option met the *requirement*. It didn't:
the requirement is *never again suffer a silent interpreter break*, our hooks all **fail open**,
so a broken base degrades into **silence** — F-001 exactly. `uv` is a build-time tool with no
runtime coupling; the anti-dependency rule never applied to it. Corrected on Lorenzo's pushback.

**F-001 recurred live, inside the session fixing it.** `uv python install` shimmed the *name*
`python3.13` into `~/.local/bin`, ahead of Homebrew. A `pip uninstall` and its verification both
silently addressed **uv's** interpreter instead of brew's — **and reported success.**
`run-tests.sh`'s `python3.13` pin became a different interpreter with no pytest.

> **An interpreter is a path, not a name.** A name is a lookup through a mutable, ordered PATH
> that four package managers write to. There is no fallback to `python3` anywhere anymore — a
> silent fallback to a toolchain-less interpreter is *how F-001 stayed invisible for six weeks.*

**Two detector bugs found, both by testing the failure and not just the fix:**

1. **P9 could never have gone green.** Its predicate was *"bare `python3` can import mnemos"* —
   which post-venv is **false, and correctly so**. It would have fired forever, G-a would have
   escalated forever, and the only exit was snoozing our own detector. The pre-commit lesson
   inverted: **a detector that cannot go green teaches you to ignore the watcher.** Rewritten to
   assert the invariant F-001 actually violated: *the interpreter the consumer resolves must
   import what it imports*, and its base must not be a package manager's.
2. **P9 was silent on the worst case.** With `.venv` gone the symlink dangles, `which` returns
   None, and it said *"nothing to drift from"* — quiet while the toolchain was **entirely
   missing** and every hook was failing open. Absence is the loudest drift there is. Found by
   parking `.venv`; fixed; re-tested.

**And a shipped bug of my own, caught on the way past.** `.tessera/.spend-backstop-fires` — the
backstop's fire counter — **was committed, holding 5, against a `MAX_FIRES` of 3.** Every fresh
clone and downstream would have inherited a backstop **already past its cap: born disabled,
silently.** The guard would deny a GPU boot and nothing would ever catch the denial going
undispositioned. I gitignored `spend-auth.json` correctly one hour earlier and *the lesson did
not generalize to the sibling file on its own.* Now a rule, with a check:
`runtime-state-is-not-tracked`.

**The venv is the mechanism; the guardrail is a check.** A venv does not stop anyone typing
`python3` in a new script tomorrow. `doccheck`'s **`no-bare-python3-with-toolchain-import`**
fails if any hook invokes bare `python3` on code importing a venv-only module. The
stdlib/toolchain split was the de facto design for months and had **never once been enforced**.

**G-a still fires** — it intersects the last 3 logged runs and P9 genuinely did fire in all
three. It clears on its own as green runs accumulate. Deliberately *not* spamming `tessera-watch`
to force it quiet: that is gaming a detector, same species as a hand-run `/compact` contaminating
the Mnemos trial.

### Next

**All three preconditions to an unsupervised run are now met** (spec 06, the escalation backstop,
the venv). The blocker is gone.

1. **FOCUS-004 — the skill audit.** Now the front of the queue, and unchanged in shape: 56 skills,
   zero ever evaluated, and it is still **the only honest path to a real `auto` compaction** — the
   Mnemos trial's counter is *still 0* and its clock has never started. Must run in the **main
   thread**, its own session; the ~208k of reading has to land in the real context or the trial
   gets nothing.
2. **Gate-scan recall holes** — before any `should_fire` labeling pass. Two known: the
   question-shaped detector misses declarative gates, and it cannot see the gate in the turn that
   fires it (*last-block → last-turn*).
3. **Spec 03** — after calibration data.
4. ~~**Prune the inherited Maggy docs.**~~ **DONE 2026-07-12** — 18 files, 5,538 lines, during
   the pre-public provenance audit. It was *bigger than this item stated*: all **14** phase specs
   were Maggy's roadmap, not just the two with "maggy" in the filename, plus `benchmark-results.md`
   and `mwp.md`. Note how the item was scoped — from filenames, without opening the files. Reading
   them took a minute and doubled the set. **`commands/maggy.md`, `commands/maggy-init.md` and
   `bin/maggy-usage` also pruned** (2026-07-12) — the commands launched a dashboard absent from this
   repo, and `maggy-usage` read `~/.claude/routing-log.jsonl`, which only the *unwired*
   `route-task-hook` writes: it reported `$0.00` forever, by construction.
5. **The multi-provider harness is still shipped, and it is entangled — needs a decision (ADR-level).**
   `bin/{deepseek,kimi,qwen3,grok,gemini-api,gemini-cli}`, `hooks/route-task-hook`,
   `hooks/usage-summary-hook`, `commands/usage-summary.md`. **ADR-0003 §3 says Tessera does NOT own
   this** — "the full DeepSeek/Gemini/MiniMax/Kimi stack is maggy's reason to exist"; Tessera keeps
   only the Claude-tier sliver (`tier-classify-hook`/`subagent-route-hook`, both wired). But the
   wrappers are *consumed* by `bin/research`, `bin/review`, `bin/validate-plan` and by three live
   skills (`cross-agent-delegation`, `autonomous-testing`, `polyphony`). So this is not cleanup:
   deleting them decides whether Tessera keeps cross-agent delegation at all. **Do it with FOCUS-004,
   not before.** Note `install.sh` copies `bin/`, `hooks/` and `commands/` into `~/.claude/`, so
   whatever survives here is installed globally on every downstream machine.
2. **FOCUS-004 skill audit** — unblocked, and still the only honest path to a real `auto`
   compaction (the Mnemos trial's counter is still **0**). Deliberately not run concurrently
   with this session: the audit's 208k of reading must land in the *main thread* or the trial
   gets nothing.
3. **Gate-scan recall hole** — before any `should_fire` labeling pass. **Grew a second head on
   2026-07-12: the scan cannot see the gate in the turn that fires it** (the transcript it reads
   does not yet contain the turn in flight). Observed twice in one session. It is the last-block
   bug one level up — *last-block → last-turn* — and the miss is not random: it is always the
   *freshest* gate, i.e. the one most likely still unlogged. See observatory.
4. **Spec 03** — after calibration data.

**Standing caution, reinforced.** Every finding above came from *running the thing*, not from
reading it. The spec's flaw was visible in its own text for three months. The sweep-script hole
was live in conclave. Both surfaced within minutes of invocation. Under unsupervised runs
nobody is there to invoke and look — **build the instruments accordingly.**

---

## Handoff — 2026-07-11

Two sessions today. **25 commits across four repos, all pushed, all clean.**

### Session A — the autonomy inflection

- **Gate-scan backstop BUILT** — the last standing #17 violation is closed. Stop hook
  `.claude/scripts/tessera-gate-scan.sh` → `scripts/gate/scan.py` counts gate-shaped turns in
  the transcript, diffs against the session's gate log, exits 2 on a gap so the model must
  adjudicate before finishing. **The trigger is now the harness, not model recall.** The
  detector is a recall net (over-counts on purpose); the model is the precision filter; it
  cannot *forget*, which was the whole failure. Fires on gap ≥2 **or zero-logged**. Loop-safe,
  caps at 3 fires/session, fails open. Wired into all downstreams.
- **THE INFLECTION POINT — Tier 1 taken up.** Decided: the human-in-the-loop phase was the
  *on-ramp to autonomy, not the destination*. Claude's first read (decline Tier 1) was **wrong**
  — it inferred a terminal preference for supervision from the repo instead of asking. Lorenzo
  corrected it. Tier 1 reordered **07 → 03 → 01**.
- **Spec 07 v1 SHIPPED:** `bin/tessera-escalate` + `docs/contracts/escalation.md` + watcher
  **P6**. Escalation is the suggestion-gate's *asynchronous* form (#12 needs a disposer;
  unsupervised there is none).
- **ADR-0005 RECORDED**, and it carries the day's biggest finding — one that came from data,
  not reasoning: **50% of conclave's gates are `aws-launch` / `aws-teardown` / `aws-spend`.**
  An unsupervised agent in conclave is an agent that boots GPUs on its own. **The autonomy
  boundary in real work is spend and irreversible infrastructure, not design** — the exact
  opposite of what Claude predicted. Spec 06 promoted Tier 3 → **Tier 1**. A hard budget stop
  is now a *precondition* of any unsupervised run, not an optimization.

### Session B — the machinery started catching *Claude's* mistakes

- **COMPACTION FIRED FOR THE FIRST TIME EVER** (hand-run `/compact`). All four machinery
  checks passed. **Layer 2 delivered** — goal, constraints, and a fresh checkpoint landed in
  post-compaction context with no re-derivation. The trigger-tagging fix worked on its first
  live exercise: **P3 correctly read `0 real (1 manual test excluded)`.** A test did not become
  evidence. *Layer 3's injection remains unproven* (see backlog). **The trial's clock has NOT
  started** — a real `auto` compaction has still never happened.
- **`scripts/doccheck.py` + watcher P8 + a pre-commit gate.** Six doc-drift bugs had been found
  in three days — *every one* because Lorenzo got suspicious and asked "all docs updated?", and
  every one fixed without leaving a check behind. **The human was the detector.** Now
  mechanical: doccheck asserts the checkable claims docs make about the repo, `.githooks/pre-commit`
  **blocks** a lying commit, P8 surfaces red at session start. See `docs/contracts/doc-claims.md`.
- **`.tessera/config.yml` built — bottom-up, not as the profile-override layer the design doc
  imagined.** One key (`test:`), one live consumer (`bin/tessera-test`), zero speculative knobs.
  An agent must never have to *guess the test command*. Wired into all three downstreams, each
  command **verified by running it**, not inferred from the manifest.
- **`tessera-watch` P9 — interpreter-drift.** The F-001 detector we never had. Fires every
  session until the venv lands (see backlog). This is the "clean up the python fun" reminder,
  made mechanical — *a note is what gets dropped on the floor.*

### The thread that ties Session B together — read this before building anything

**Five separate bugs today, one root cause: we validated against the environment we were
standing in, not the one the code runs in.**

| Bug | It existed… | …but not where it mattered |
|---|---|---|
| **F-001** (historical) | `python3` on my PATH | not the one the *hook* resolved |
| **`.tessera/config.yml`** | on disk, in 4 repos | **gitignored** — untracked, would vanish on clone |
| **PATH export** | in `~/.zshrc` | **interactive-only** — invisible to the *agent's* shell |
| **pre-commit hook** | would have been in `.git/hooks/` | **not tracked** — no gate in any other clone |
| **`test:` command** | ran and reported "57 passed" | **6 of 12 files** — gate + override + mnemos silently skipped |

Three of these were **shipped by Claude today, inside the very machinery built to catch that
class**, and were caught by the tooling rather than by Lorenzo. That is the system working —
but the lesson generalizes and should be applied *before* the autonomy work, not after:

> **Existence is a local fact. Reachable-by-the-consumer is the shared one.** Before trusting
> any capability, invoke it the way the consumer will: `zsh -c` not `which`; `git ls-files`
> not `ls`; run the suite, don't count the files.

---

## State of the machinery (verified 2026-07-12, end of session)

```
toolchain       .venv/ — uv-managed python (NOT homebrew). `./install.sh` builds + verifies it,
                idempotently; rebuilt from scratch to prove the fresh-machine path.
                AN INTERPRETER IS A PATH, NOT A NAME. No fallback to `python3`, anywhere.
tessera-test    194 green   (80 top-level + 17 gate + 13 override + 84 spend + 3 mnemos)
doccheck        11 checks, 0 false claims  (+no-bare-python3-with-toolchain-import,
                                             +runtime-state-is-not-tracked)
spend guard     LIVE in tessera + conclave + templates + tessera-new-project
                live-fired in all four; a fresh scaffold blocks a boot and allows a teardown
spend backstop  LIVE — Stop hook; a denial must end in a grant or a packet, or exit 2
pre-commit      wired + live-fire verified (a lying commit was refused)
tessera-watch   P9 GREEN — F-001 CLOSED (was firing every session since 2026-07-11)
                G-a still firing: trailing indicator on P9's 3-run streak; clears itself
                P1/P3/P4/P5/P6/P7/P8 green
repos           tessera, conclave, howler, tess-dashboard
```

**P9 is the only thing firing, and it is meant to.** It nags every session until the venv
lands; G-a escalates it after 3 consecutive runs.

---

## Next session — priorities

Nothing is due *cold*; everything is signal-gated. **Run `tessera-watch` first.** In priority
order when you want to push forward:

1. **Spec 06 (cost/budget) — Tier 1, and it BLOCKS unsupervised downstream work.** This is the
   real next build. Conclave is the target: hard budget stop, spend ceiling, no GPU boot
   without one. **Not started.** The evidence is in ADR-0005 — half of conclave's gates are
   spend gates. Until this exists, "let the agent run unsupervised in conclave" means "let the
   agent boot GPUs unsupervised."

2. **The venv (P9 is firing).** Kills the dual-Homebrew Python split. **Hard trigger: before
   the first unsupervised run.** A silent interpreter break with no human watching *is* F-001 —
   and F-001 was invisible for weeks and confounded the entire Mnemos trial. Details in backlog.

3. **FOCUS-004 — the skill audit.** Now **unblocked** (both preconditions met). 56 skills,
   never once evaluated despite principle #15 saying they're a starting point. It is also the
   only realistic way to produce a **real `auto` compaction** (~208k tokens of reading, ~25%
   past the auto-compact threshold) — which is what the Mnemos trial actually needs. Two birds.

4. **Fix the gate-scan recall hole** *before* any `should_fire` labeling pass, or the labeling
   calibrates on a knowingly biased sample. See backlog.

5. **Spec 03** — only after calibration data exists. Its risk is P2-shaped.

**Standing caution for the autonomy push.** Across today, the findings that most changed
direction came from *Lorenzo pushing back*, not from the machinery: the Tier 1 premise, the
downstream doc audit, "actually do the config.yml", and "we should have a note to clean up the
python fun." Claude inferred instead of looking, repeatedly. **Under unsupervised runs that
check is absent by construction.** Build the instruments accordingly — that is the entire
argument for spec 06 and the escalation backstop.

---

## [FOCUS-004] Skill audit — and the session that finally tests compaction

**Status:** queued, unblocked
**Priority:** high — overdue by our own doctrine, and it is the compaction test vehicle

### Why this is two things at once

**1. It is overdue.** `CLAUDE.md` says the skill set is "a starting point per principle #15 —
trim or expand based on evidence in subsequent sessions." **56 skills. Zero have ever been
evaluated.** No evidence has ever been gathered. The doctrine was written and never executed.

**2. It is the only honest way to reach compaction.** Measured 2026-07-11:

| | tokens |
|---|---|
| all 56 `SKILL.md` files | **~208,000** |
| *context window* | *~200,000* |
| *auto-compaction fires at ~83%* | *~166,000* |

Reading the corpus to audit it overshoots the auto-compaction threshold by ~25% **with no
padding and no artifice** — the work is *genuinely* read-heavy. Expect **1–2 auto-compactions**,
which is exactly what the Mnemos trial needs (P3 requires ≥3 *non-manual* `compaction_fired`;
the counter is **0**).

**Do not pad a session to force compaction.** Pick work whose nature is token-heavy. A padded
session produces a restore judgment about work you were not really doing.

### Preconditions — both MET (2026-07-11)

1. ~~Manual `/compact` machinery check must pass first.~~ **PASSED** — see below.
2. Trigger-tagging **done** (`22f06b9`) — manual `/compact` cannot pollute P3. Verified live.

### What "done" looks like

- Every skill: keep / trim / cut, with a one-line evidence-based reason (used in a real
  session? covered by another skill? never once loaded?).
- Cuts recorded in `docs/design-principles.md` (the framework-evaluation section is where
  skill-set changes get their reasoning, per CLAUDE.md).
- **Secondary payload — the docs↔code consistency audit.** Partly mechanized now (`doccheck`),
  but doccheck covers only the ~60–70% that is machine-checkable. The prose 30% still needs
  eyes, and it bit twice today (design-principles said config.yml was "not built" 30 minutes
  after it was built). Same read-heavy shape; fold it in.

---

## Compaction test protocol — Step 1 RUN, PASSED (2026-07-11)

For 171 fatigue samples (max token_utilization **0.51**, `flow` in **171/171**) compaction had
**never fired, once**. Every band above 0.4 (COMPRESS / PRE-SLEEP / REM / EMERGENCY) was dead
code by observation.

**Step 1 — machinery. Done. All four checks green.**

| Check | Result |
|---|---|
| `compaction-log.jsonl` exists | ✅ first entry ever, `trigger: "manual"` |
| marker consumed, not orphaned | ✅ absent; `restore_injected` logged |
| restore block reached the model | ✅ **Layer 2** (`MNEMOS SESSION RESUME`) |
| P3 still reads `0 real` | ✅ `0 real (1 manual test(s) excluded)` |

The summarizer also honored the PreCompact preservation block. **The trigger-tagging fix worked
on its first live exercise: a test did not become evidence.**

**Caveat, recorded honestly.** Layer 3 (`mnemos-post-compact-inject.sh`) logged `restore_injected`
and consumed the marker, but its `CONTEXT RESTORED AFTER COMPACTION` text was never *observed*
arriving in context. Plumbing confirmed; injection unconfirmed. Moot while Layer 2 fires — but
**do not record Layer 3 as proven.**

**Step 2 — value. STILL OPEN.** `trigger: auto` has never happened. Only a genuine
auto-compaction answers what the trial asks: *did the restored checkpoint let work resume
without re-deriving?* That is FOCUS-004's job. **P3 remains at 0 real.**

---

## Backlog (triggered — do when the condition fires)

- **Kill the dual-Homebrew Python split — do the venv.** *Decided 2026-07-11 (1a/2b): venv is
  the right fix, deliberately deferred.* **`tessera-watch` P9 fires every session until this
  lands**, so it cannot be quietly dropped; G-a escalates after 3 consecutive runs.
  - **Measured, and it closes the obvious escape hatch:** `python@3.14` is
    `installed_on_request: **False**` — a brew **dependency** of awscli/httpie/mlx/mlx-c/**ollama**
    (the tier-classifier's engine). **Not removable**, and it owns the `python3` name with
    *nothing installed in it*. `python@3.13` is `installed_on_request: **True**`, nothing in brew
    depends on it, and it holds the **entire** toolchain. *The removable one is the one we use.*
  - **Why not just migrate to 3.14:** Homebrew re-points `python3` whenever a *dependent* formula
    moves. 3.14 arrived because ollama wanted it; 3.15 will do the same and orphan the toolchain
    again. **Migration resets the clock, it does not stop it.**
  - **Hard trigger: before the first unsupervised downstream run (ADR-0005).**
  - Scope: `install.sh` + the bin scaffold. Interim pin (`python3.13`, PATH-relative) works.

- **Namespace `scripts/gate/` and `scripts/override/` — the trigger already FIRED.** Both dirs
  contain an `emit.py` *and* a `scan.py`; with no packages, pytest binds `import emit` to
  whichever collected first and the other suite fails collection. The backlog said the trigger
  was *"next time anything needs a single green-suite command (CI, **a pre-commit gate**, ...)"* —
  **a pre-commit gate was built on 2026-07-11 and the trigger was not noticed.** Worse, the
  workaround (enumerating test files in `config.yml`) **silently ran 6 of 12 files while
  reporting green.** *Mitigated same day:* `scripts/run-tests.sh` runs each suite in a separate
  process (separate `sys.modules`, no collision) — all 87 tests now run. **Still open:** proper
  namespacing. *Deferred because* `python3 scripts/gate/emit.py` is the invocation documented in
  four repos' CLAUDE.md and in the gate-event contract; packagifying breaks that bare same-dir
  import contract. That is a real migration. *Trigger:* CI, or the next time the contract is
  being touched anyway.

- **Gate-scan detector is question-shaped — it misses *declarative* gates.** Found by the
  backstop's own first live fire. `_is_asking()` looks for a `?` in the last 300 chars, so the
  "here's what I'd do, proceeding unless you object" gate — the one used constantly — is
  **invisible**. **Consequence: the measured miss rates (howler 91%, conclave 61%) are FLOORS,
  not ceilings.** *Trigger:* fold in when P7 fires, **before** labeling. *Do not reach for NLP*:
  also treat a turn as asking when it ends on an explicit proposal marker, and accept that some
  recall is unreachable — a recall net with a **named** hole beats one with an unnamed one.

- **Label `should_fire` on the gate corpus. DEFERRED — and the deferral is watcher P7, not a
  note.** Fires at ≥20 unlabeled post-backstop gates. *Two things to get right when it fires:*
  **(a) the model must not label its own gates** — the contract needs a truth signal independent
  of the gate's own decision, and Claude filling in nulls with its own opinion is self-assessment
  wearing calibration's clothes; **(b) `should_fire` ≠ "could an agent self-dispose this"** — they
  come apart exactly where it matters (an `aws-launch` gate *should* have fired for a human, yet
  an agent with a hard budget stop could safely self-dispose a $2 boot inside budget). Add a
  distinct `can_self_dispose` label. See ADR-0005, `docs/contracts/gate-event.md`.

- **Prove Layer 3 (`mnemos-post-compact-inject.sh`) actually injects.** Its `restore_injected`
  line and marker consumption were confirmed 2026-07-11, but its text was never observed
  reaching the model — PreToolUse stdout may not surface. Moot while Layer 2 fires, but **Layer 3
  is the only net when a post-compaction turn has no SessionStart.** Cheap check first: does
  PreToolUse stdout reach the model at all?

- **Mnemos compaction-recovery verdict.** ⚠ **RETIRED 2026-07-27 — the ≥3 threshold below is
  SUPERSEDED by ADR-0015 and P3 no longer counts toward it.** The trial was watching the wrong
  event: the restore path is not compaction-specific, so it ran ~121 times against ~3
  compactions. Kept for the trail; do not read the criterion below as live. *(Found by
  doccheck's `handoff-retires-its-own-figures` on its first run — a stale trigger stated as
  current, 15 days after the decision that retired it.)*
  *Original text:* Fires at **≥3 non-manual `compaction_fired`**
  (currently **0 real**; one `manual` test, correctly excluded). Watcher **P3**. When it fires:
  did `restore_injected` follow each one, and did the restored checkpoint let work resume
  without re-deriving? An **empty log is not a signal** (untested ≠ useless), and a
  **`trigger: manual` entry is not a signal either** (a test of the layer, not evidence about
  it). Scope: compaction-recovery only, never session-continuity.

- **`design-principles.md` promises two files that were never built.** *(`.tessera/config.yml`
  was the third — it **graduated**: built 2026-07-11 with a live consumer. That is what a
  `PLANNED_PATHS` entry is *for*.)* Remaining, parked in doccheck's `PLANNED_PATHS` so the debt
  stays legible: `.tessera/third-party-scope.yml` (**build its consumer first** — the Data
  Handling review category does not exist; a data file with no reader is ceremony) and
  `.tessera/project.yml.template` (**deletion candidate**, not a build candidate — all repos are
  private, so the profile field leaks nothing).

- **The profile model has no consumer.** `profile: standard` is read by **nothing**; no
  `profiles/` dir exists; `healthcare` is named throughout design-principles and is zero bytes
  on disk. Same shape as the retired P2 — a mechanism whose value is *assumed*, never
  exercised. Observatory entry opened 2026-07-11 with an **event trigger**: *a second profile
  becoming real.* If one never arrives, that is the answer — a one-valued enum is a constant,
  and a constant does not need a model. **Do not let a verdict on the model condemn
  `.tessera/project.yml` as a marker file** — that demonstrably works and is how every tool
  discovers downstreams.

- **Content-aware hook drift, remaining gap.** Watcher **P1** now content-diffs
  `.claude/scripts/` ↔ `templates/`. **Not covered:** the third layer, `~/.claude/templates/`
  (out-of-repo), and making `templates/` generated rather than hand-copied. *Trigger:* next
  `install.sh` rework.

- **Cut CHANGELOGs when repos go public.** All four are expected to go public eventually. Only
  tessera has one — deliberately (premature until there is a public reader). When a repo goes
  public: `tessera-changelog --since <ref> --version <v> --date <d>` (commits are already
  Conventional). Keep the tool **single-source in `tessera/bin`, reached via PATH — do NOT copy
  it into each repo** (the F-003 drift trap).

---

## Parked for discussion (not started)

- **The 5-entry GSD observatory cluster** (byte-budget, `.planning` schema, domain probes, gate
  types, plan-drift). Tied to the Tier 1 discussion — resolve together, not piecemeal.

- **Roadmap Tiers 2–3.** Tier 1 is now taken up (ADR-0005), so the old "does Tier 1 earn its
  keep" question is settled. The successor question — how far past Tier 1 to go — is *not* open
  yet and should not be until spec 06 ships.

---

## Archive

### Handoff — 2026-07-10

**Observatory-watcher pilot built** — roadmap Tier 1 / spec-03 de-risking. `bin/tessera-watch`
evaluates the Observatory's silent+machine-checkable "When to revisit" triggers as predicates,
surfaced by a SessionStart hook. Substrate-only: predicate list + runner + append-only fire-log
+ `G-a` graduation predicate that reads the log, so "graduate to a stateful engine" is itself
channelized, not prose. On first run it caught **two real drifts** (a live hook missing from
`templates/`; a 167-line phantom `mnemos-compact-recovery.sh` contradicting its own doc).
FOCUS-003 closed; findings backlog cleared to 0.

**Do not re-litigate:**
- **Substrate-only.** No snooze/hysteresis/prose-parsing/umbrella until a graduation predicate
  fires on real fire-log evidence. Building any of them now is the exact over-build the pilot
  exists to prevent.
- **P2 (tess-umbrella) declined + RETIRED.** Verb count tracked no real friction — the
  `tessera-*` binaries are hook-invoked and callers name them directly, so an umbrella aliases
  without consolidating. Don't rebuild it. **P2 is now the canonical name for the failure mode
  "a predicate that fires correctly on a proxy tracking no real pain"** — it gets cited a lot.

### [FOCUS-001] Tier-classifier under-rating — **done (2026-07-08)**

Short decision/strategy prompts ("what's next?") matched no keyword and fell through to
HAIKU/SONNET — under-rating the most reasoning-heavy turns exactly when stakes were highest.
Fixed by prompt-engineering the classifier (judge *reasoning demanded*, not prompt length;
balanced few-shot). 5/6 empirical. Residual (context-blind lookup-shaped decisions) logged to
observatory as mitigation #1, still open.

### [FOCUS-002] Observatory sweep, 22 entries — **done (2026-07-08)**

Framework too young for a >6mo cull; nothing dead. **Promoted:** convention-surfacing drift →
**design principle #17**. Spawned FOCUS-003. Flagged the 5-entry GSD cluster (still parked, above).

### [FOCUS-003] Audit CLAUDE.md "surface X" against #17 — **done (2026-07-10)**

Six candidates, **one real violation**. The audit's own contribution: the instruction
*conflated* gate-**surfacing** (an accepted reasoning-convention, which #17 explicitly permits)
with gate-**recording** (the violation — a user-facing artifact riding pure model recall, ~85%
miss). Both files reworded so the convention half is no longer tarred with the violation half.
**The violation itself was then closed 2026-07-11 by the gate-scan backstop.**
