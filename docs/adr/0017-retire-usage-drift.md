# ADR-0017: `usage` drift retired — the dimension was `git grep`, so it could not answer the question that justified it

- **Date:** 2026-07-27
- **Status:** Accepted
- **Executed:** 2026-07-27 — `scripts/icpg/drift.py`, `scripts/icpg/test_drift.py`, `scripts/icpg/models.py`, `scripts/icpg/__main__.py`, `scripts/icpg/symbols.py`, `scripts/icpg/test_symbols.py`. The cut is *within* those files, not of them — see "What was actually changed" below.
- **Decision driver:** ADR-0013 §6 held this open in as many words — *"Deterministic two-predicate drift vs. iCPG's 6-dimension composite. Standing pattern #3 says the composite is a proxy. Retiring it is a separate decision needing its own evidence."* This is that evidence. Immediate trigger: `_project_specs/todos/active.md` item 1 and its binding stopping rule.

---

## Decision

**Retire the `usage` drift dimension.** iCPG's detector now scores two: `changed` and `decision`.

This does **not** retire iCPG, and does not conclude its kill/keep trial. iCPG does four jobs — record intents, link them to symbols, detect drift, and feed Mnemos's restore path. This touches one third of one job.

### What was actually changed

Every file below survives; the cut is of code *within* them.

| File | Change |
|---|---|
| `scripts/icpg/drift.py` | drops `_check_usage_drift` and its three helpers (`_relative_to`, `_tracked_files_mentioning`, `_in_scope`), the `usage` entry in `check_symbol_drift`, and the now-unused `subprocess`/`Path` imports |
| `scripts/icpg/test_drift.py` | drops 4 usage tests and `test_a_symbols_own_file_is_not_usage_outside_its_scope`; the declared-vocabulary test now asserts two dimensions **and** that `usage` is absent, with the reason |
| `scripts/icpg/models.py` | `DRIFT_DIMENSIONS` listed six names for a detector scoring three — now the live two, with a note that retired names stay legal in stored rows |
| `scripts/icpg/__main__.py` | the dismissals comment claimed `usage` "fires on ~1 in 5 symbols against thresholds nobody calibrated"; now records that the dismissal state did its job |
| `scripts/icpg/symbols.py`, `scripts/icpg/test_symbols.py` | the extractor coverage that made the measurement fair (shell + shebang dispatch) |

*A note on this line, kept because the check is the point: the first draft used the `removed:` form, which asserts the named paths are **gone**. doccheck rejected it — correctly, these are edits. The second draft backticked bare basenames in prose and doccheck read those as paths too. `adr-execution-recorded` earned its keep against the ADR that cites it, twice, within the hour.*

---

## The measurement

Item 1 was on its third re-scope. The stopping rule written into `active.md` bound it to one bounded change and one decision, so the change was made **first**, to remove the standing objection that `usage` had never been judged over a fair corpus.

**Step 1 — make the corpus honest.** `symbols.py` dispatched purely on file extension, so iCPG saw **84 of 260** code files. Every `.sh` hook and every extensionless `bin/tessera-*` was invisible — 46 of 56 scope entries pointed at files the extractor could not parse. Added `.sh`/`.bash`/`.zsh` plus shebang detection for extensionless executables, and a regex shell extractor. Corpus went to **261 of 261**.

**Step 2 — measure, then decide on that one measurement.**

| | scored | fires | |
|---|---:|---:|---|
| python | 6239 | 829 | 13.3% |
| shell | 229 | 157 | 68.6% |
| **all** | **6468** | **986** | **15.2%** |

73.0% scored zero, 11.7% fell below the cut, 10.1% pinned at the 1.00 ceiling.

**The spread is an artifact, not discrimination.** The top firers:

```
shell    ok 311   run 262   err 247   main 202
python   ev 373   read 285  check 271  run 267  get 263  repo 203  main 202
```

`_tracked_files_mentioning` shelled out to `git grep --fixed-strings`, a **substring** match with no word boundary. `ok` matched "hook", "token", "look" — in a repository whose subject matter is hooks. The dimension measured **name length and commonness**, not out-of-scope usage. Shell fired 5× more than python for one reason: shell function names are 2–6 characters.

**The obvious repair was tried before retiring, not after.** `git grep -lw` (word boundary) cut `ev` from 373 to 14 — and left `read` 180, `run` 214, `check` 171, `main` 137, every one still far past the cut of 2 and still pinned at 1.00. The repair does not repair it.

**The lifetime record agrees.** Across 202 stored drift events: 165 involved `usage`, **zero** were ever resolved, and the single event any human ever touched was a **dismissal** whose note reads *"usage threshold is uncalibrated; a common symbol name in a narrow scope."* That was written before this measurement and reached the same conclusion from one example. The `dismissed` state ADR-0013 asked for did its job on n=1.

---

## Why this is retirement and not recalibration

`design-principles.md:459` sets iCPG's kill test with two questions. Q2 is: **"Does drift detection catch things grep wouldn't?"**

`usage` *was* a subprocess call to `git grep`. By construction the answer is no — no threshold, no word-boundary flag, and no scope refinement can change that, because the mechanism and the thing it was being tested against are the same mechanism. Q2 is now answered for this dimension, against a corpus that includes the framework's own code.

This is **standing pattern #3** in its purest form: *name the pain, not the artifact that correlates with it.* The pain is "this symbol is being used somewhere its intent never claimed." The artifact counted was "how many tracked files contain this byte sequence." A predicate that fires correctly and means nothing.

Worth stating plainly, since the 2026-07-27 shrink from six dimensions to three **kept** `usage`: that shrink deleted dimensions with no *producer*, and `usage` had one. Having a live producer is necessary and not sufficient. It fed real data into the wrong question.

---

## What this costs, stated rather than buried

The stopping rule required naming the cost and not letting it purchase a fourth re-scope.

Drift detection is now `changed` (fires on 0.6% of symbols — live and quiet) and `decision` (**0 fires ever**; as of the 07-27 fix it is live-and-silent rather than dead — all 53 invariants currently hold). That is a thin instrument, and this ADR does not pretend otherwise. **Whether drift detection as a whole earns its keep is a separate question with separate evidence, and is not decided here.**

Two things argue against reading this as a step toward deleting it:

1. **It moves iCPG toward the design ADR-0013 judged better.** ADR-0013 §4 rated scryer's deterministic predicate — *"this file changed since we last reconciled it"* — as **"Idea-only — open, do not adopt yet,"** and named iCPG's weighted composite as the proxy. `changed` **is** that predicate. Retiring `usage` does not move toward no drift detection; it moves toward the two-predicate design, arrived at from our own measurement rather than from their README.
2. **`changed` demonstrably works.** During this very edit the decision-surface hook re-scored `check_symbol_drift` the moment the `usage` line was cut, and `_check_usage_drift` flipped to `changed(0.80)` — the "symbol removed entirely" score — as it was deleted. Low volume is not the same as dead.

ADR-0013's re-evaluate trigger *"the iCPG kill/keep trial concludes kill"* is **not** met and is not being met here.

---

## Biases named

- **Sunk-cost, inverted.** ADR-0013 flagged a pull toward *defending* iCPG's composite against scryer's simpler design. Having now measured it, I notice the opposite pull — momentum toward cutting, having just cut. That is why the word-boundary repair was tested **inside** step 2 rather than dismissed: retiring had to survive the strongest available rescue, or it would be a preference wearing a measurement.
- **Confirmation risk on my own corpus fix.** I extended the extractor and then measured with it. If the extractor were wrong, the measurement would inherit the error. The check: shell and python fire at 68.6% and 13.3% via the *same* code path, and the collision explanation predicts exactly that gap from name length alone. The finding does not depend on the shell half — python alone fires 829 times on `ev`, `read`, `check`, `run`.
- **Scope pressure.** Item 1 had been re-scoped twice. I wanted it closed. The stopping rule existed precisely to stop that from choosing the answer, and its "no step 3" clause is why the two side-findings below are separate entries rather than a fourth scope.

---

## Consequences

- `icpg drift` reports fewer, more meaningful events. 165 of 202 historical events came from the retired dimension.
- **Historical events stay readable.** Stored rows carrying `usage` (and the earlier `spec`/`ownership`/`test`/`dependency`) are evidence, not schema; nothing purges them and `models.py` records that retired names remain legal in old rows.
- Re-adding `usage` requires an ADR superseding this one. `test_drift.py` asserts the declared vocabulary from `inspect.getsource(check_symbol_drift)` and carries an explicit assertion that `usage` is absent, with the reason — so it fails on the day it returns rather than never.
- **The extractor fix outlives the dimension it was built to judge.** Shell and extensionless coverage now feeds `changed`, which is the dimension that survived.

## Side-findings, logged separately per the stopping rule's "no step 3"

Both go to `docs/observatory.md`, not into this decision:

1. **46 of 78 shell files have zero symbols.** Tessera's hooks are straight-line scripts, not function libraries. Corpus coverage bought *files*, not *symbols* — shell contributes 76 of 1968. Whether symbol-level tracking is the right unit for a shell-heavy repo is an open question.
2. **`icpg create` has no flag to hand-author contracts**, which is why Q1 (does the agent populate ReasonNodes in practice?) still has one non-bootstrap data point.

---

## References

- `docs/adr/0013-scryer-evaluation.md` §4, §6 — held this question open; this ADR answers it
- `docs/design-principles.md:459` — the kill test whose Q2 this settles for one dimension
- `docs/observatory.md` → "iCPG's drift detector measures the emptiness of its own graph" — the 6→3 shrink that kept `usage`
- `_project_specs/todos/active.md` item 1 — the binding stopping rule this followed
- Standing pattern #3 (name the pain, not the proxy), #7 (a test is never evidence about the thing it tests)
