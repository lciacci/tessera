---
name: icpg
description: Intent-Augmented Code Property Graph — tracks WHY code exists via ReasonNodes with formal contracts, drift detection over the 3 dimensions that have producers, and 3 canonical pre-task queries for autonomous development
when-to-use: "Before any code change — query the reason graph for intent, constraints, and risk"
user-invocable: false
effort: high
---

# iCPG Skill (Intent-Augmented Code Property Graph)


**Purpose:** Add a Reason Graph layer on top of code structure so every
function, class, and module is traceable to the goal that created it,
the agent or human that owns it, and whether it's still doing what it
was supposed to do.

```
┌────────────────────────────────────────────────────────────────┐
│  iCPG = AST + CFG + PDG + RG (Reason Graph)                    │
│  ─────────────────────────────────────────────────────────────│
│  AST  = Abstract Syntax Tree (structure)      ← existing       │
│  CFG  = Control Flow Graph (execution paths)  ← existing       │
│  PDG  = Program Dependency Graph              ← existing       │
│  RG   = Reason Graph (WHY layer)              ← THIS SKILL     │
│                                                                │
│  The RG stores ReasonNodes (goals/tasks), links them to code   │
│  symbols via typed edges, enforces contracts (DbC), and        │
│  detects when code drifts from its original purpose.           │
│                                                                │
│  Storage: .icpg/reason.db (SQLite, per-project, gitignored)   │
│  CLI: icpg init | create | record | query | drift | bootstrap │
└────────────────────────────────────────────────────────────────┘
```

---

## Core Principle

**Intent first, code second.** Before writing or modifying code, query
the reason graph to understand WHY existing code was written, WHAT
constraints it must preserve, and WHETHER your change duplicates prior
work.

**The problem isn't duplicate *code*, it's duplicate *purpose*.** Knowing
what already exists before writing something new is a capability-index
problem, and `icpg query prior` is that index — answered structurally from
the ReasonNode graph, not from a hand-maintained code index that rots.
*(Harvested from the retired `code-deduplication` skill, ADR-0008.)*

---

## The 3 Canonical Pre-Task Queries

**Every agent MUST run these before writing code:**

| # | Query | Command | What It Answers |
|---|-------|---------|-----------------|
| 1 | **search_prior_work** | `icpg query prior "<goal>"` | Has this been attempted before? Prevents duplication. |
| 2 | **get_constraints** | `icpg query constraints <file>` | What invariants apply to files I'll touch? Prevents breakage. |
| 3 | **get_risk_profile** | `icpg query risk <symbol>` | Is this symbol fragile? Drift history, ownership changes. |

---

## ReasonNode — The Core Primitive

Each ReasonNode captures a stated purpose with a formal contract:

```
id              UUID
goal            Natural language: what is this trying to achieve
decision_type   business_goal | arch_decision | task | workaround | constraint | patch
scope           Files/modules expected to be touched
owner           Human or agent accountable
status          proposed | executing | fulfilled | drifted | abandoned
source          manual | commit | inferred | agent-session

FORMAL CONTRACT (Design by Contract):
  preconditions    What must be true before this intent executes
  postconditions   What must be true when fulfilled
  invariants       What must remain true throughout and after
```

**Drift = predicate failure.** A symbol has drifted when its current
behavior no longer satisfies the postconditions of the ReasonNode that
created it, or when an invariant is violated.

---

## Six Edge Types

```
CREATES      Reason  → Symbol   (this intent created this function)        ← written
MODIFIES     Reason  → Symbol   (this intent changed this function)        ← written by
                                                                             `icpg record`,
                                                                             wired to no hook
REQUIRES     Reason  → Reason   (B depends on A being done first)          ← NO WRITER
DUPLICATES   Reason  → Reason   (these two goals overlap)                  ← NO WRITER
VALIDATED_BY Reason  → Test     (this test proves the intent was satisfied) ← NO WRITER
DRIFTS_FROM  Symbol  → Reason   (this symbol no longer does what it was made for) ← NO WRITER
```

**Four of the six have no producer anywhere in the codebase**, and the drift detector used
to score their absence — see the drift section below. The enum is the design; the arrows
are what is actually fed. Keep them distinct when reasoning about what this graph knows.

---

## 3-Dimension Drift Model *(was 6 — shrunk 2026-07-27)*

| Dimension | What It Means | Detection | Fed by |
|-----------|--------------|-----------|--------|
| **Changed** | Symbol checksum differs from the recorded one | Compare stored vs current checksum | `upsert_symbol` |
| **Decision** | Contract predicates no longer hold | Evaluate invariants + postconditions | `contracts.py` |
| **Usage** | Symbol referenced outside its intent's scope | `git grep` over **tracked files only** | git |

Run `icpg drift check` to scan; each dimension produces a 0-1 severity score, and the
event's severity is their mean.

### Why three and not six — read this before adding a fourth

The other three dimensions scored **the absence of an edge type nothing writes.**
`REQUIRES`, `DUPLICATES`, `VALIDATED_BY` and `DRIFTS_FROM` appear only in the enum and on
the read side; no code in `scripts/icpg/` produces them. So:

- **Test drift** returned a constant `0.30` for every symbol on every scan — **712 of 712**
  stored events carried it. A dimension with one possible value is not a measurement.
- **Ownership** (needs >3 distinct reason owners) and **dependency** (needs REQUIRES edges)
  **never fired once**, in either direction.
- **Usage** shelled out to `grep -rl <name> .` over an unfiltered tree including `.venv/`,
  so any common symbol name saturated the score inside vendored code alone.

**"No linked tests" is still reported — as coverage, not drift.** `icpg status` prints
`Intents w/o tests: N/M` from `scripts/icpg/coverage.py`. Reporting an absent edge is
honest; *scoring* it as though the code had drifted was not.

**Adding a dimension means adding its PRODUCER first.** doccheck's
`drift-dimensions-have-producers` fails the commit if `drift.py` reads an edge type nothing
writes — including reading edges *untyped*, which is how the ownership dimension slipped
past every guard. See `docs/observatory.md` → "iCPG's drift detector measures the emptiness
of its own graph".

---

## CLI Reference

### Setup
```bash
icpg init                          # Create .icpg/ and database
icpg bootstrap --days 90           # Infer ReasonNodes from git history
icpg bootstrap --days 90 --no-llm  # Without LLM (commit-message only)
```

### Create & Record
```bash
icpg create "Add JWT auth" --scope src/auth/ --owner feature-auth --type task
icpg record --reason <id> --base main         # Record symbols from git diff
icpg record --reason <id> --edge-type MODIFIES # Record as modifications
```

### Query (the 3 canonical queries)
```bash
icpg query prior "user authentication"     # 1. Duplicate detection
icpg query constraints src/auth/service.ts  # 2. Invariants for file
icpg query risk validateToken              # 3. Symbol risk profile
icpg query context src/auth/service.ts     # All intents for a file
icpg query blast <reason-id>               # Full blast radius
```

### Drift
```bash
icpg drift check          # Full scan; dedups against open events, does not re-insert
icpg drift file <path>    # Fast single-file scan (what the PreToolUse hook runs)
icpg drift list           # Unresolved events WITH their IDs — start here to adjudicate
icpg drift resolve <id>   # The drift was REAL and is fixed; short prefix ok, unknown id exits 2
icpg drift dismiss <id> --reason "<why>"   # The drift was NEVER REAL — detector error
```

**`resolve` and `dismiss` are different facts, and the split is the point (ADR-0016).**
`resolved` = real, and the code or intent was fixed. `dismissed` = the detector was wrong.
`icpg status` prints dismissals **by dimension**, and that count is the only evidence able to
say whether a dimension is miscalibrated — a dimension climbing that list is not busy, it is
wrong. `usage` currently fires on ~1 in 5 symbols against thresholds nobody calibrated, and
this is the question that has been waiting for evidence.

**A dismissed drift stays suppressed while the evidence is unchanged.** A severity move
re-opens the same row (so the note saying why it was once dismissed travels with it); a new
dimension is a different key and therefore a new event. Re-raising it every scan would
re-litigate a closed ruling on every Stop — conclave F-001, which this repo has already paid
for once.

Every drift line carries `<id>  [severity] symbol (file) — dimensions  ×seen_count`.
The id is the argument `resolve` needs; before 2026-07-27 no command printed one, so the
verb was unreachable without opening SQLite by hand and 700 rows accumulated unread.

**Repeats refresh, they do not accumulate.** The natural key is `(symbol, reason,
sorted(dimensions))` — deliberately not the description, which embeds the scores, so a
severity moving by 0.1 would otherwise mint a new row. `seen_count` counts the repeats;
`detected_at` stays *first* seen and `last_seen` moves. A drift that was **resolved** and
then recurs gets a NEW row — that is news, not a merge into something already closed.

### Status
```bash
icpg status               # Stats: reasons, symbols, edges, drift
```

---

## Storage

Per-project, gitignored, zero infrastructure:

```
.icpg/
  reason.db       SQLite database (4 tables: reasons, symbols, edges, drift_events)
  .gitignore      Contains: *
  chroma/         ChromaDB vectors (if chromadb installed)
  tfidf_cache.json  TF-IDF fallback cache
  .current-intent   Marker file for active intent
```

Install options:
```bash
pip install ./scripts/icpg            # Core (zero deps)
pip install "./scripts/icpg[vectors]"  # + ChromaDB for duplicate detection
pip install "./scripts/icpg[all]"      # + ChromaDB + scikit-learn + openai
```

---

## Workflow: Before Any Code Change

```
0. INTENT       → icpg create (or identify existing intent)
1. DEDUP        → icpg query prior (check for duplicate work)
2. CONSTRAINTS  → icpg query constraints (understand invariants)
3. RISK         → icpg query risk (check fragile symbols)
4. LOCATE       → search_graph to find symbols (code-graph skill)
5. CHANGE       → Make the edit
6. RECORD       → icpg record (link symbols to intent)
7. DRIFT CHECK  → icpg drift check (verify no unintended drift)
8. VERIFY       → Run tests, lint, typecheck
```

**Step 0 is non-negotiable for autonomous agents.** Every change must
be linked to a stated purpose. Without an intent, there's nothing to
measure drift against.

---

## Bootstrapping from Git History

For existing codebases, infer ReasonNodes from commit history:

```bash
icpg bootstrap --days 90 --verbose
```

This will:
1. Get commits from last 90 days
2. Cluster by temporal proximity (2-hour window)
3. Infer intent via LLM (Claude or OpenAI) or commit message parsing
4. Create ReasonNodes with `source: "inferred"`, `confidence: 0.6-0.8`
5. Extract symbols from changed files, create CREATES edges
6. Run duplicate detection against existing ReasonNodes

**Quality note:** Inferred intents are marked low-confidence. Review and
promote high-value ones manually.

---

## Contract Predicates

Predicates are structured assertions over codebase state:

```
file_exists("src/auth/middleware.ts")
test_exists("src/auth/__tests__/service.test.ts")
symbol_count("src/auth/") <= 15
function_signature("validateToken") == "(token: string) => Promise<User>"
```

Contracts can be:
- **Hand-authored** for high-risk ReasonNodes
- **LLM-inferred** via `icpg create --infer-contracts`
- **Heuristic** (scope → file_exists, test → test_exists)

---

## Anti-Patterns

| Anti-Pattern | Do This Instead |
|-------------|-----------------|
| Coding without stating intent | `icpg create` before every non-trivial change |
| Assuming your change is isolated | `icpg query constraints` + `icpg query risk` first |
| Rebuilding what already exists | `icpg query prior` to check for prior work |
| Leaving intent in 'executing' forever | Update status to 'fulfilled' when done |
| Ignoring drift events | `icpg drift check` weekly, resolve or create new intents |
| Storing full source in symbols | Store signature + checksum only — read source from files |
| Skipping bootstrap on existing repos | `icpg bootstrap --days 90` to build initial graph |
