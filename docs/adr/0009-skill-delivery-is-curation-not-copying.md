# ADR-0009: Skill delivery is curation, not copying — Claude Code already unions the corpus into every project

- **Date:** 2026-07-16
- **Status:** Accepted
- **Refines:** ADR-0008 (its *delivery mechanism*, not its verdict). ADR-0008's corpus verdict (keep 46, remove 10) and its reframe *prune → profile-gated delivery* both stand. This ADR corrects **how** that delivery works — the "ship the skills downstream" framing rested on a false premise about how Claude Code loads skills.
- **Decision driver:** ADR-0008 named the structural gap as "`bin/tessera-new-project` ships **zero** skills," and framed the fix as *building skill delivery* — a copier that lays the KEEP set into each downstream, profile-selected. Before building it, FOCUS-004 verified the actual Claude Code skill-load semantics (skills.md / settings.md, confirmed 2026-07-16). The premise was wrong in a way that makes the fix an order of magnitude cheaper.

---

## The premise ADR-0008 assumed, and what is actually true

**ADR-0008 assumed** skills reach a project only if *placed* there — so a downstream with no local skills and no shipping step is starved, and delivery means copying the KEEP set in.

**What Claude Code actually does:** the global `~/.claude/skills/` registry and a project-local `.claude/skills/` are loaded as a **union**. Every project on this machine already sees **every** global skill. There is no starvation. `bin/tessera-new-project` ships zero skills and the downstream still gets all ~100 of them — via global, automatically.

So the corpus is not **undelivered**. It is **un-curated**. A Flutter downstream loads `supabase-python` not because anything shipped it there, but because global unions it in and nothing turns it off. The misfire the audit found (`supabase-python`'s `**/*.py` glob firing in a non-Supabase repo) is a *curation* failure, not a *delivery* failure.

**This does not weaken ADR-0008 — it sharpens it.** The gap is still real and still at the distribution layer; it is just a different primitive than "copier." The fix is a **selector that turns the wrong skills off per project**, not a shipper that turns the right skills on.

---

## The load semantics that decide the mechanism

Confirmed against `code.claude.com/docs` (skills.md, settings.md, permissions.md), 2026-07-16:

1. **Union load, no restriction-by-placement.** Global + project + plugin + `--add-dir` skill dirs all load together. A project-local dir *adds*; it cannot *subtract* from global. (Same-name conflict resolves personal-over-project — irrelevant here, we don't shadow.)
2. **Settings CAN scope skills — first-class, no directory surgery:**
   - **`skillOverrides`** (per-skill, writable in any settings scope incl. project `.claude/settings.local.json`): `"on" | "name-only" | "user-invocable-only" | "off"`. `"off"` hides a skill from Claude, the `/` menu, Remote Control, and SDK callers. Absent key = `"on"`. **Does not affect plugin skills** (those need `/plugin` / `enabledPlugins`).
   - **`Skill(name)` permission rules** — allow/deny by exact or `name *` prefix; **merge across scopes**, so a true per-project allow/denylist is possible.
3. **Listing budget is the one thing settings cannot zero.** Every skill's *name* is always injected into context (name + description listing = ~1% of the context window). Under budget pressure, descriptions are **silently dropped, least-used first** — a bloated set starves the descriptions of the skills that matter. `paths:` gates **activation only, not listing**: a `paths:`-dead skill still costs listing budget. Only *not-installing* a skill removes its listing cost entirely; `skillOverrides: "off"` still leaves the name listed.

---

## Decision

**The delivery mechanism is a profile → `skillOverrides` map, written by the scaffold. Not a copier.**

- `bin/tessera-new-project` reads the downstream's profile (`.tessera/project.yml`) and emits a `skillOverrides` block into its `.claude/settings.json`: every skill **outside** the profile's set → `"off"`; the profile's set left `"on"`.
- **The profile model is composable: a universal base + additive stack-tags.** A universal set (`base`, `mnemos`, `icpg`, `framework-evaluation`, `security`, `code-graph`, …) is always-on; each stack-tag (`+python`, `+supabase`, `+flutter`, `+react-web`, …) flips its skills on. A Supabase-plus-Next.js app is `+supabase +nextjs`, not a new named profile — this avoids a combinatorial explosion of profiles and maps 1:1 onto `skillOverrides` (start all-off-except-base, turn tags on). *(Chosen over a fixed named-profile set; composable is reversible data and matches the override primitive. Low-stakes — the map is editable.)*
- The audit's per-skill dispositions (`_project_specs/todos/focus-004-audit.md`, the KEEP set) supply the base/stack-tag assignment directly.

**Cost:** ~30 lines of generated JSON per scaffold + a profile→tag→skill table. A ~1-day change, not a distribution subsystem.

---

## What this changes, and what it deliberately leaves alone

- **Changes from ADR-0008:** the delivery primitive is `skillOverrides`, not a skill copier. No skill files move; no per-downstream copies exist to drift.
- **De-dup (the blocked D item) is *further* deferred, not decided.** Because global stays whole and authoritative for the union, and the scaffold only *writes settings*, nothing here forces the `tessera/skills/` vs `~/.claude/skills/` source-of-truth question. It stays open (observatory), now with less pressure on it.
- **ADR-0004 (hooks global-by-default) is untouched** — and this is the same shape: one shared source, per-project configuration selects behavior. Skills now mirror hooks.
- **Deferred — the listing-budget floor ("Goal B").** Settings cannot drive a skill's listing cost to zero; only not-installing can. With skills activating rarely (ADR-0008's 6-invocations-machine-wide finding), the floor is unlikely to bite. **Measure with `/doctor` before spending anything on it.** If it ever bites, the heavier lever is physically partitioning universals-in-global vs a Tessera-owned stack catalog — explicitly NOT built now (YAGNI, and it would collide with the 20+ repos on the shared global registry).

---

## Re-evaluate triggers

- **`/doctor` shows skill-listing context cost materially starving descriptions** → the listing floor is biting; revisit physical partitioning (universals-global vs stack-catalog).
- **A profile needs a skill that isn't installed on the machine at all** → the union assumption breaks for that skill; that is the case where a real *copier* (or a global install step) is finally required, and it reopens ADR-0008's original framing for that skill only.
- **Claude Code changes skill-load semantics** (project dir gains the ability to restrict global, or `skillOverrides` gains plugin reach) → re-derive the mechanism from the new primitives.
- **Plugin skills need per-project gating** → `skillOverrides` can't do it; needs `enabledPlugins` per project or `Skill(...)` deny rules — design at that point.

---

## References

- ADR-0008 — the content audit and the prune→delivery reframe this refines.
- `_project_specs/todos/focus-004-audit.md` — the KEEP set that becomes the profile→skill map.
- Claude Code docs (confirmed 2026-07-16): `code.claude.com/docs/en/skills.md`, `settings.md`, `permissions.md` — union load, `skillOverrides`, `Skill(...)` permissions, listing budget (`skillListingBudgetFraction`), `paths:` as activation-only.
- ADR-0004 — hook distribution (global default); the precedent this mirrors.
