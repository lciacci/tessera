# ADR-0011: sqlfluff — the trigger fired, the evidence said no, and the trigger was the bug

- **Date:** 2026-07-21
- **Status:** Watching
- **Decision driver:** Observatory trigger fired. `docs/observatory.md` → "sqlfluff — adopt when a downstream project has standalone SQL" named its adopt-when condition as "a downstream project introduces standalone `.sql` files or dbt models." settempo was adopted as the fifth downstream on 2026-07-21 carrying two standalone Postgres files (208 lines). The condition was met exactly as written.

> **Watching for:** first-party SQL that is **query-shaped and frequently changed** — a dbt project, an analytics repo, a migrations directory under active iteration, or any tracked `.sql` containing `SELECT`. Not merely the existence of a `.sql` file.
> **Next check:** 2026-09-19

---

## Target

- **Name:** sqlfluff
- **URL:** https://github.com/sqlfluff/sqlfluff
- **What it is:** A dialect-aware SQL linter and autoformatter with 26+ dialects, Jinja/dbt templater support, and a native pre-commit hook.

---

## Side-by-side summary

| Dimension | Tessera | sqlfluff |
|---|---|---|
| Maturity | Solo, dogfooding | 9.8k stars, 1.1k forks, ~6.8k commits, v4.2.2 (2026-06-04), monthly releases |
| Cross-runtime | Claude Code only | CLI, Docker, pre-commit, VS Code — runtime-independent |
| Original IP | Profile model, gate log, findings channel, watcher predicates | Dialect-aware SQL parser; the parser *is* the moat |
| Maintenance model | Solo | Community; Datacoves sponsors |
| License | — | MIT |
| Community size | Single user | Large, active (305 open issues, 31 PRs) |
| Primary problem solved | Agent-legible development discipline | SQL style consistency and dialect correctness |
| Distinct strength | Knows *why* code exists | Actually parses SQL |

---

## 1. Identity & maturity

Healthy by every available measure: MIT, monthly releases, latest v4.2.2 three weeks before this eval, broad dialect coverage, first-class pre-commit integration. **Maturity is not the question here and never was.** Adopting sqlfluff carries no meaningful project risk. The question is entirely whether Tessera's downstreams have SQL it can say anything useful about — and that is an empirical question this ADR answers with numbers.

Bias to name up front: **excitement/legitimacy bias.** sqlfluff is a well-run project and the observatory entry had been sitting there for twelve days anticipating adoption. The entry was written expecting a yes. Reaching a "not yet" required actively resisting the entry's own framing.

---

## 2. Problem-space overlap

| Overlap area | Tessera approach | sqlfluff approach | Classification | Notes |
|---|---|---|---|---|
| Quality gates at commit time | `.githooks/pre-commit` → doccheck, blocking | `.pre-commit-hooks.yaml`, blocking | Compatible | Both are "fail the commit"; sqlfluff would be another entry, not a conflict |
| Style enforcement | Rules live in skills as prose the agent reads | Rules are executable and deterministic | Compatible | Tessera's whole thesis (#17) is that executable beats prose — sqlfluff is on-thesis |
| SQL correctness | None. Zero coverage | Parser-level, dialect-aware | Compatible | A real gap Tessera does not address |
| No-op when irrelevant | Watcher predicates fire only when their condition holds | `pre-commit` scopes by `files:` regex | Compatible | Trivially satisfied |

**Tessera does not address (gaps sqlfluff fills):** SQL syntax validity, dialect portability, index/lock hazards, style consistency in DDL and queries.

**sqlfluff does not address (gaps Tessera fills):** everything about intent, decisions, and why code exists. No overlap in either direction — these are orthogonal tools, which is exactly why "adopt patterns" is not a meaningful option here. There are no patterns to steal; there is only a tool to run or not run.

---

## 3. Integration cost

**Adopt fully (replace Tessera with it):** Not applicable. Orthogonal tools.

**Adopt patterns (steal ideas, keep Tessera):** Nothing to steal. The value is the SQL parser; the ideas (lint at commit, scope by path) Tessera already implements.

**Hybridize (run alongside):** Cheap and clean. `uvx sqlfluff` runs it with no install. A `.sqlfluff` config per project plus a pre-commit entry scoped to `\.sql$` no-ops in the four downstreams with no SQL. Estimated effort: under an hour. **Cost is not the obstacle.**

**Continue without:** Zero maintenance burden. The gap that remains is unlinted SQL in exactly one downstream, whose SQL is 208 lines of write-once DDL.

---

## 4. The evidence

This is the section that decided it. Run against settempo's two files, `--dialect postgres`:

| Cut | Violations |
|---|---|
| Default ruleset | **206** |
| Layout/whitespace (`LT*`) | 185 — **89%** |
| Remainder after `exclude_rules = layout` | **21** |

The 21 survivors, inspected individually:

| Rule | Count | What it flags | Verdict |
|---|---|---|---|
| RF05 special chars in identifier | 7 | `create policy "Users own their shows"` | **False positive.** Quoted, space-containing policy names are idiomatic Supabase RLS. |
| PG01 `CREATE INDEX` without `CONCURRENTLY` | 7 | Every index in the schema | **False positive.** This is a fresh-install script; the tables are created empty in the same file. `CONCURRENTLY` cannot run inside a transaction block and there is nothing to lock. |
| RF04 keyword as identifier | 7 | A column named `date` | **Debatable nit.** Legal Postgres, works, arguably worth knowing. Not a defect. |

**206 violations, 0 actionable.** And the files contain **zero `SELECT` statements** — they are pure DDL. sqlfluff's value concentrates in query-heavy, frequently-edited SQL (dbt models, analytics). Write-once schema DDL is close to its weakest case.

---

## 5. Lock-in & maintenance

**If we adopt:** dependency on sqlfluff's Postgres dialect and rule stability. Exit is trivial — delete a config file and a pre-commit entry. `uvx` means not even an install to unwind. Genuine lock-in: none.

**If we do not adopt:** no equivalent to maintain, because Tessera is not in the SQL-linting business and would not build one.

The asymmetry is worth stating plainly: this decision is **cheap to make and cheap to reverse in either direction.** It therefore should not be agonized over, and the correct default is the one that adds nothing until it pays.

---

## 6. Decision

**Verdict:** Watching

**Reasoning:**

The trigger fired exactly as written and the answer is still no, which means **the trigger was measuring the wrong thing.** "A downstream has standalone `.sql` files" is a proxy for "sqlfluff would tell us something we do not know," and on first contact with reality the proxy produced 206 findings containing zero actionable ones. Adopting on that evidence would install a gate whose entire observable output is noise — and a gate that only ever cries wolf trains you to bypass it. That is the pre-commit lesson recorded in `CLAUDE.md` running in reverse: *green is only meaningful if failing it stops something*, and red is only meaningful if it ever means anything.

This is the **P2/P4 failure shape a third time**, and it is becoming the framework's most recurrent bug: a predicate that fires correctly on a proxy tracking no real pain. P2 was retired for it (verb count). P4 was rewritten for it earlier this same session (project count → byte-level drift). This entry is the same error in prose form. The pattern is now well enough evidenced to state as a rule: **when writing an adopt-when trigger, name the pain, not the artifact that correlates with it.**

Two further findings the evaluation surfaced, both about the trigger rather than the tool. First, a naive `find . -name "*.sql"` would have false-fired on conclave months ago — it has 130 `.sql` files, every one a vendored litellm migration inside `harness/venv`, and **zero tracked by git**. Any future SQL predicate must use `git ls-files`, not `find`; first-party is the only thing that counts. Second, the observatory used sqlfluff as its own worked example of a trigger that is "trivially checkable and *worthless* to watch — the day you write SQL and want it linted, the need announces itself." That was right, and better than the entry that followed it: the need did **not** announce itself here, because there is no need. Watching for the artifact produced a false alarm that cost an evaluation to clear.

Bias check: **sunk-cost on the observatory entry** (twelve days of anticipation is not evidence), and **excitement bias** toward a well-run project. Resisted by insisting on running the tool before judging it. The counter-bias also deserves naming — having just fixed two proxy-predicate bugs this session, I was primed to find a third, and should not have trusted that pattern-match without the numbers. The numbers happened to agree.

**Concepts adopted:** None yet.

**Concepts considered and rejected:**
- *Adopt now with `exclude_rules = layout`* — rejected. Filtering to 21 findings that are 14 false positives and 7 nits is not a signal worth a gate.
- *Adopt as formatter-only (`sqlfluff format`)* — rejected. It would reformat 185 lines of deliberately hand-aligned DDL for zero correctness gain, producing a large diff on a file nobody is editing.
- *Add it to the standard profile as an on-demand skill now* — rejected on principle #15 (defaults are starting points, earned by evidence). The skill would activate on `**/*.sql` in one project and say nothing useful.

**Re-evaluate trigger conditions:**
- A downstream acquires **git-tracked** SQL that is query-shaped — any tracked `.sql` containing `SELECT` — or adopts dbt. This is the corrected trigger: query-shaped and first-party, not merely present.
- A downstream's SQL becomes *frequently edited* (say, a migrations directory gaining 5+ commits in a month). Change frequency is what makes a linter pay.
- A real SQL defect reaches a downstream's production that sqlfluff would have caught. One such incident overrides every argument above.
- Next cadence review: 2026-09-19

---

## References

- `docs/observatory.md` → "sqlfluff — adopt when a downstream project has standalone SQL" (the entry whose trigger fired)
- `docs/observatory.md` → "The Observatory's own triggers are prose" (the entry that correctly called this trigger worthless to watch)
- `bin/tessera-watch` → `p4_downstream` docstring — the same proxy-predicate error, fixed in bytes on the same day as this ADR
- ADR-0006 — Tessera is instrumentation, not control (why an all-noise gate is worse than no gate)
- settempo `supabase-schema.sql`, `supabase-migration-uuid.sql` — the corpus this evaluation ran against
