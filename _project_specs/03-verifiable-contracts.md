# Spec 03: Verifiable Contracts (Property-Based Test Generation)

**Status:** pending
**Priority:** Tier 1 (highest leverage)
**Effort:** Large

## Context

iCPG's ReasonNodes already carry formal contracts:

```
preconditions:   What must be true before execution
postconditions:  What must be true when fulfilled
invariants:      What must remain true
```

Today these are natural-language strings. Drift detection matches commit patterns and checksums against them heuristically. That's good but not verifiable — the agent can't prove a postcondition still holds after a change.

For autonomous engineering, we want machine-checkable contracts: the agent writes a postcondition, and the system generates tests that will fail if the postcondition is ever violated.

## Goal

Generate property-based tests from iCPG postconditions so drift detection becomes "did the test pass?" instead of "does the string still plausibly match?"

## Approach

### Step 1 — Structured postconditions (optional schema)

Let authors write postconditions in either natural language (current) or a structured form that's machine-generatable:

```yaml
postconditions:
  - type: "returns"
    of: "save_response"
    shape: "Response"
    properties:
      - "response.id is not null"
      - "response.org_id == input.org_id"
      - "len(response.answers) == len(input.answers)"
  - type: "invariant"
    holds: "during_save"
    assertion: "db.responses.count() increases by 1"
```

The structured form compiles to tests; natural language fallback uses LLM-assisted generation (Step 2).

### Step 2 — Pluggable property-based test generators

One generator per language/framework:

- `scripts/icpg/codegen/hypothesis_python.py` — Hypothesis (Python)
- `scripts/icpg/codegen/fastcheck_ts.py` — fast-check (TypeScript)
- `scripts/icpg/codegen/proptest_rust.py` — proptest (Rust)
- Natural-language postconditions use LLM generation, structured ones compile directly

Each takes a `ReasonNode` and returns a test file with a `# @icpg-generated from R-abc123` header so the agent knows not to hand-edit.

### Step 3 — `icpg contracts generate <intent-id>`

CLI command that:

1. Reads the intent's postconditions
2. Detects the language of the scope files (already tracked)
3. Invokes the right generator
4. Writes tests to `tests/generated/contracts/<intent-id>.test.py` (or equivalent)
5. Adds a `VALIDATED_BY` edge automatically

`icpg contracts generate --all` regenerates every intent's tests (bulk operation for upgrading existing projects).

### Step 4 — Drift check gains a "contract-verified" signal

Existing drift detection checks whether `VALIDATED_BY` tests exist and pass. With this spec, those tests are now *derived from the postconditions* rather than hand-written, so failure is a direct postcondition violation signal — not just "a test broke."

### Step 5 — Regenerate on intent edit

When a ReasonNode's postconditions change, stale generated tests are flagged. Agent can run `icpg contracts sync` to regenerate; humans can review the diff.

## Integration points

- `scripts/icpg/models.py` — add structured `postcondition` variants alongside existing strings
- `scripts/icpg/codegen/` — new package, one module per language/framework
- `scripts/icpg/__main__.py` — `contracts generate`, `contracts sync` subcommands
- `skills/icpg/SKILL.md` — document how to write structured postconditions
- `templates/reasonnode-structured.yaml` — template showing both forms

## Success criteria

1. Given an intent with structured postconditions, `icpg contracts generate` produces a runnable property-based test in Hypothesis/fast-check
2. The generated test has a header marking it as machine-generated
3. Running the test suite fails immediately when a postcondition is violated in the actual implementation
4. Natural-language postconditions fall back to LLM generation cleanly (doesn't silently skip)
5. Drift detection differentiates "stale test" from "postcondition violation" in its severity score

## Pilot: the Observatory as a cheap corpus (added 2026-07-09)

This spec's premise — *natural-language conditions are unverifiable, so nobody
knows when they're violated* — has a second, much cheaper instance in this repo.

`docs/observatory.md` carries ~23 entries, each with a **"When to revisit"**
condition written as prose. Nothing evaluates them. They are checked only when a
human remembers to sweep. On 2026-07-09, three shell commands found **three
triggers at or past threshold that nobody had noticed**:

| Entry | Stated condition | Reality on 2026-07-09 |
|---|---|---|
| Override mechanism | "when a second `tess` verb appears" | four exist (`tessera-{changelog,findings,hooks,new-project}`) |
| Downstream script drift (F-003) | "project count crossing ~4–5" | exactly 4 |
| Namespace skill routing | "60+ skills"; entry says "currently ~50" | 56 |

**A trigger written as a sentence can only be checked by someone who reads the
sentence.** That is this spec's thesis, restated on a corpus where a wrong
predicate costs nothing.

### Why pilot here first

This spec is **Effort: Large** — it needs structured postconditions, property-based
test generation, and an LLM fallback for natural-language contracts. The
observatory needs shell one-liners exiting 0 or 1. No codegen, no LLM, no CI
coupling. Same conversion, ~2% of the risk.

Prove "prose condition → machine-checked predicate" where a false positive is a
noisy session-start line, *before* betting a Large effort on doing it to iCPG
contracts where a false positive breaks the build.

### Scope, if pursued

Give each observatory entry an optional `check:` field — a shell predicate. Only
entries that have one get evaluated. Ride the existing SessionStart channel next
to `bin/tessera-findings`; print fired triggers, stay silent otherwise. Precedent
is exact: the downstream findings backlog was a compendium read by human recall
until `tessera-findings` + a SessionStart hook made it a channel — the third
instance that promoted **design principle #17**.

**Scope filter — build only the silent triggers.** The useful cut is not
machine-checkable vs. not; it is *silent* vs. *self-announcing*. sqlfluff's
trigger ("first `.sql` file") is machine-checkable and worthless to watch: the
day you write SQL and want it linted, the need announces itself. Hook-layer
content drift is machine-checkable and silent — bare `python3` sat in the install
payload for two weeks with no symptom because every copy was independently valid
bash. Watch only what cannot announce itself.

Candidate checks, each corresponding to a **documented past failure**, not an
anticipated one (principle #3):

1. three-layer hook content diff (`.claude/scripts/` ↔ `templates/` ↔ `~/.claude/templates/`) — bit us 2026-07-09
2. **non-manual** `compaction_fired` count ≥ 3 in `.mnemos/compaction-log.jsonl` — the re-armed Mnemos trial. `trigger: manual` entries are *tests* of the recovery layer, not evidence about it, and must never count (see `tessera-watch` P3)
3. skills diverging from the global install
4. a `hook_distro: global` project whose hooks silently no-op on this machine
5. JNI symbol drift after a package rename — Howler F-004, cost a tester crash

### Explicitly not folded into Spec 01

Spec 01 observes the **deployed product** (Datadog, Sentry, p99 latency). This
pilot observes the **framework's own invariants**. Same word, different referent.
The shared vocabulary is a trap worth naming once.

## Depends on

None (iCPG only). But pairs well with:

- Spec 01 — runtime postconditions (metric predicates) complement code-level postconditions
- Spec 02 — a generated test failure is a strong auto-revert signal
