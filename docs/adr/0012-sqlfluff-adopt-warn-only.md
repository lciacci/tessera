# ADR-0012: sqlfluff adopted, warn-only — supersedes ADR-0011

- **Date:** 2026-07-22
- **Status:** Accepted (supersedes ADR-0011)
- **Decision driver:** Human disposition. ADR-0011 concluded "Watching" on 2026-07-21. Lorenzo's instruction was to *implement* sqlfluff across Tessera and downstream projects — the evaluation had answered a question that was not the one being asked.

---

## Why this ADR exists

ADR-0011 is one day old and not wrong on its facts. Every number in it still holds. It is
superseded because **it answered the wrong question.**

The ask was "implement sqlfluff in Tessera and downstream projects." What ADR-0011 delivered was
an evaluation of whether sqlfluff would find defects in settempo's SQL *today*. Those are
different questions, and the second one is not the one that governs a framework decision.
ADR-0011's verdict was a proposal; principle #12 is *Claude proposes, the user disposes*, and
this is the disposition. ADRs are immutable once written, so the record is a supersession rather
than an edit — 0011 stays as the evidence it gathered, which this ADR relies on heavily.

**The reasoning error worth naming**, because it is the interesting part: ADR-0011 generalized
from a sample of one project's *current* SQL to a claim about a *capability the framework should
carry*. Tessera is not settempo. A framework's job is to have the rail laid when a downstream
needs it — the same argument ADR-0004 made for the global hook fallback, where the rail was built
before any project rode it. "No downstream benefits from this today" is an argument about
sequencing, not about whether to build. Read that way, ADR-0011's own evidence supports adoption
with the noise tuned out, which is what this ADR does.

---

## Decision

**Adopt sqlfluff, warn-only, on-demand, shipped by default to every project.**

The shape is the one `docs/observatory.md` prescribed before either ADR existed — on-demand skill
plus a gate that no-ops when no SQL is present, not an eager default (principle #15).

| Piece | What it is |
|---|---|
| `scripts/sql/lint.sh` | Pre-commit gate. Lints **staged** `.sql` only. Silent when none. **Never blocks.** |
| `templates/tessera/sqlfluff.template` → `.sqlfluff` | Shipped config. `exclude_rules = layout`, `dialect` set per project. |
| `skills/sqlfluff/SKILL.md` | On-demand skill, `paths: ["**/*.sql"]`. Loads when you touch SQL, not every session. |
| `bin/tessera-new-project` | Ships all three, **plus** a downstream `.githooks/pre-commit` that invokes the gate, and sets `core.hooksPath`. |
| `templates/tessera/skill-profiles.json` | New `sql` extension → `["sqlfluff"]`. |
| `uvx sqlfluff` | No install to maintain, pin, or unwind. Exit cost stays ~zero. |

### The three judgments that make this safe

**1. Warn-only, from ADR-0011's numbers.** Stock sqlfluff on settempo: 206 violations, 185 (89%)
whitespace. Of the 21 survivors, 14 are false positives — `RF05` flags idiomatic Supabase RLS
policy names, `PG01` demands `CONCURRENTLY` on a fresh-install script where tables are created
empty in the same file and nothing can be locked. **Blocking on that fails commits over spacing
and wrong advice, and a gate that only cries wolf gets bypassed — then it protects nothing.**
That is `CLAUDE.md`'s pre-commit lesson (*green is only meaningful if failing it stops
something*) run in reverse: red is only meaningful if it ever means anything. Flip to blocking
per project once its rules are tuned and its findings are real.

**2. `exclude_rules = layout` in the shipped config.** This is what converts the tool from noise
to signal, and it is why "ship both halves or neither" applies: `lint.sh` without `.sqlfluff`
runs stock rules and is 89% whitespace. The scaffold ships both, same rule the gate recorder and
spend guard already follow.

**3. It shouts when it cannot run.** Spec 11's distinction, applied: *no staged `.sql`* is
"nothing to do" and exits silently; *sqlfluff unreachable, or exited >1* is "I could not do my
job" and prints loudly every time while still allowing the commit. **A linter that silently skips
looks exactly like a linter that passed** — the failure shape of F-001, the dead ingest pipe, and
the falsifier, three times in eight days.

---

## What ADR-0011 got right and is preserved

- The **206 / 185 / 21 / 14** measurements. This ADR's tuning is derived from them.
- The **corrected trigger**: git-tracked, *query-shaped* SQL is where sqlfluff pays. Still true —
  it now governs *when to consider blocking*, rather than whether to adopt at all.
- **`git ls-files`, never `find`** — conclave has 130 vendored `.sql` files under `harness/venv`
  and 0 tracked by git. Any SQL-detecting predicate must count first-party files only.
- The **proxy-predicate lesson** (*name the pain, not the artifact that correlates with it*).
  Untouched by this reversal; it was a finding about the observatory's trigger, not about
  sqlfluff, and it stands on its own alongside retired-P2 and the P4 rewrite.

---

## Bias check

ADR-0011 named excitement bias and resisted it. It did not name the one that actually bit:
**over-weighting locally-measured evidence against a stated instruction.** Having just found
three proxy-predicate bugs in one session, I was primed to find a fourth, and pattern-matched
"the trigger is a bad proxy" onto a request that was not asking about the trigger at all. The
numbers were right; the question was wrong. Cheap to correct here — one day, one superseding
ADR — but the failure mode is worth recording: *an evaluation is not a substitute for the
decision it was asked to inform.*

---

## Re-evaluate triggers

- **Flip a project to blocking** when its `.sqlfluff` is tuned enough that findings are
  predominantly real. Change `lint.sh`'s final `exit 0` to `exit 1` for that project.
- **Revisit the shipped defaults** if a downstream acquires query-shaped SQL (dbt, analytics,
  a migrations directory under frequent edit) — the layout exclusion may be worth relaxing there.
- **Reconsider `uvx`** if cold-start latency becomes a felt cost in the commit path.
- **Drop it entirely** if, after a downstream has accumulated real SQL, the gate has produced no
  finding anyone acted on. Absence of value over a real corpus is the honest kill condition, and
  ADR-0011's numbers are the baseline to measure against.
- Next cadence review: 2026-10-20

---

## References

- **ADR-0011** — the evaluation this supersedes; all measurements live there
- `docs/observatory.md` → "sqlfluff — adopt when a downstream project has standalone SQL"
- `_project_specs/11-fail-open-detection.md` — the "could not do my job" vs "nothing to do" distinction the gate implements
- ADR-0004 — precedent for building the rail before a project rides it
- ADR-0009 — skill curation; the `sql` extension is how this reaches downstreams
