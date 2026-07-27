# /icpg-drift — Show All Drift

Run a full drift scan and display all unresolved drift events, grouped by dimension and sorted by severity.

---

## Usage

`/icpg-drift`

---

## Steps

### 1. Run drift scan

```bash
icpg drift check
```

### 2. List the unresolved backlog WITH ids

```bash
icpg drift list     # every open event and the id `resolve` needs
icpg status         # counts, top 5, and the coverage line
```

### 3. Display results

Each line is already adjudicable — id, severity, symbol, file, dimensions, repeat count:

```
UNRESOLVED DRIFT (12):
  1a0a1f74  [1.00] validateToken (src/auth/service.ts) — changed(0.60), usage(1.00)  ×3
  0b8a6016  [0.60] UserService (src/users/service.ts) — decision(0.60)

BY DIMENSION (three — the ones with producers):
  Changed:   {count}    checksum differs from the recorded one
  Decision:  {count}    contract predicates no longer hold
  Usage:     {count}    referenced outside the intent's scope (tracked files only)

SEPARATELY, not a drift dimension:
  Intents w/o tests: {n}/{m}    graph coverage, reported by `icpg status`
```

**Do not report ownership, dependency or test drift** — those dimensions were removed on
2026-07-27 because they scored the absence of edge types nothing writes (`test` was a
constant `0.30` on 712 of 712 events). A `×N` suffix means the same drift was seen N
times, not N separate problems.

### 4. Offer resolution

For each event, suggest:
- `icpg drift resolve <id>` to mark resolved — a short prefix works; an unknown id exits 2
- Create a new MODIFIES ReasonNode if the change was intentional
- For `decision` drift, check whether the intent's invariant should be updated or the code
  should be — the predicate names a file that no longer exists at that path

**Resolving is a judgement, so do not batch it.** A resolved drift that recurs comes back
as a new event, which is the correct behaviour and also means a careless sweep hides
nothing permanently — but it does cost the record of who decided what.
