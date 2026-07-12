# Active Focus

Declared current priority for Tessera framework dev. One focus at a time.

**Read this top section, run `tessera-watch`, and you are caught up.**

---

## Handoff — pick up here (2026-07-12)

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

### Two things live-fire found that reasoning did not

1. **A live hole in the flagship downstream.** `conclave/scripts/sweep-gpu-capacity.sh:23` runs
   `terraform apply -auto-approve` — it boots g6e GPUs, it's the AZ-sweep from the gate log, and
   the guard saw only the wrapper's *name*. **A classifier that reads the command but not what
   the command runs is checking the wrong text.** Now reads local scripts one level down.
2. **The guard blocked its own wiring commit — and I misread the result.** The install command
   quoted `terraform apply` in a test string, so the guard blocked the *whole* Bash call and
   **none of the wiring ran**. The probe that followed reported `allowed` for a GPU boot,
   because the wrapper fails open when the guard is absent. *It looked like a working guard
   saying yes. It was a missing guard saying nothing.* Caught only by checking disk.

### A finding about the checker itself

`doccheck` gained **`ignored-test-suites-are-run`**, and it is a finding, not just a check. The
2026-07-11 *"test command ran 6 of 12 files and reported green"* bug was fixed **without leaving
a check behind** — which is the one thing doccheck's standing rule forbids. The rule was
violated by the commit that fixed the bug the rule exists for. Adding `scripts/spend/` to the
`--ignore` list nearly repeated it. Now: `--ignore` a suite without running it → doccheck fails.

Also added: `spend-guard-is-wired` (the doc claims a hook; is it in settings.json?) and
`spend-auth-is-not-tracked` (a committed grant would authorize spend on every clone, forever,
past its own TTL). **8 checks, 0 false claims.**

### Next

1. **The venv (P9, still firing).** Now the *last* thing between here and an unsupervised run —
   spec 06 was the other. Hard trigger, unchanged: before the first unsupervised run.
2. **FOCUS-004 skill audit** — unblocked, and still the only honest path to a real `auto`
   compaction (the Mnemos trial's counter is still **0**). Deliberately not run concurrently
   with this session: the audit's 208k of reading must land in the *main thread* or the trial
   gets nothing.
3. **Gate-scan recall hole** — before any `should_fire` labeling pass.
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
tessera-test    150 green   (66 top-level + 17 gate + 13 override + 54 spend + 3 mnemos)
doccheck        8 checks, 0 false claims  (+ignored-test-suites-are-run, spend-guard-is-wired,
                                            spend-auth-is-not-tracked)
spend guard     LIVE in tessera + conclave + templates + tessera-new-project
                live-fired in all four; a fresh scaffold blocks a boot and allows a teardown
pre-commit      wired + live-fire verified (a lying commit was refused)
tessera-watch   P9 FIRING (interpreter drift — the venv debt, deliberate)
                P1/P3/P4/P5/P6/P7/P8, G-a all green
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

- **Mnemos compaction-recovery verdict.** Fires at **≥3 non-manual `compaction_fired`**
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
