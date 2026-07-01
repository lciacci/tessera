# ADR-0004: Per-project hook distribution — global default, freeze for ship-critical

- **Date:** 2026-06-30
- **Status:** Accepted
- **Decision driver:** Project decision — "formalize moving Tessera hooks global vs. staying contained, and a formal way to enact it at inception and at inflection." Graduates observatory entry F-003 (Downstream script drift) to a decision, as that entry pre-committed.

> Internal architecture decision (not an external-tool evaluation), so it uses the
> classic ADR form (Context / Decision / Alternatives / Consequences / Re-evaluate)
> like ADR-0002 / ADR-0003, not `_template.md`.

---

## Context

Every downstream project scaffolds its own copies of the 8 mnemos hook scripts
into `.claude/scripts/`. When Tessera patches a script, the copies don't update —
no sync mechanism. A statusline fix (2026-06-27) landed in tessera but not in
howler / tess-dashboard: three repos, one change, manual N-way sync. F-003.

F-003 claimed the "rail" for going global was already laid — a runtime
local→global fallback where hooks resolve `.claude/scripts/X` **or**
`~/.claude/templates/X`. **Investigation while formalizing this decision found
that claim was false at the hook-entry level.** Every hook command — in
tessera's live settings, the scaffold template, and the statusline — was:

```
if [ -x ".claude/scripts/mnemos-X.sh" ]; then exec ".claude/scripts/mnemos-X.sh"; fi; exit 0
```

No `elif ~/.claude/templates/X`. No script resolved global siblings internally.
Global `~/.claude/settings.json` carries zero mnemos hooks. So
`~/.claude/templates/mnemos-*.sh` was populated but **nothing read it at
runtime** — it was an *install source* (install.sh copies FROM it TO projects),
not a *runtime fallback*. A project with no local copies would hit
`if [ -x … ]` → false → silent `exit 0` → every mnemos hook dead. The same
silent-success failure mode this project keeps hitting. Going global was not a
config flip; it required building the switch.

---

## Decision

**G1 — centralize the scripts, keep settings per-project.** The `.sh` files are
the drift surface; `settings.json` changes rarely and *should* differ per
project (allow-lists). So centralize the scripts, not the settings.

1. **Runtime fallback branch (the switch).** Each mnemos hook command in
   `templates/tessera/settings.base.json` (7 hooks + statusline) gains:
   ```
   if [ -x ".claude/scripts/mnemos-X.sh" ]; then exec ".claude/scripts/mnemos-X.sh";
   elif [ -x "$HOME/.claude/templates/mnemos-X.sh" ]; then exec "$HOME/.claude/templates/mnemos-X.sh"; fi; exit 0
   ```
   `frozen` → local copy present, local branch wins. `global` → no local copy,
   global branch fires. The switch is purely "are the `.sh` files copied locally."

2. **Declared state in `.tessera/project.yml`:** `hook_distro: global | frozen | source`.
   Default `global`. Version-controlled, PR-visible. **Declarative metadata** —
   the actual switch is the filesystem (which the fallback resolves); the field
   records intent, drives the scaffold and the freeze/thaw verbs, and lets
   `status` detect declared-vs-actual drift. `source` marks the framework repo
   only: its local `.claude/scripts` ARE what install.sh ships.

3. **Enact at inception.** `tessera-new-project` defaults to `global` — no local
   mnemos copies. `--frozen` pins live copies for ship-bound projects.

4. **Enact at inflection.** `bin/tessera-hooks freeze|thaw|status`:
   - `freeze` — pin `~/.claude/templates/mnemos-*.sh` → `.claude/scripts/`, set `frozen`.
   - `thaw` — drop local copies, set `global`. Refuses on `source`; refuses if
     settings lack the fallback branch (would silently disable hooks).
   - `status` — declared mode + local count + fallback presence + drift check.

5. **Existing repos grandfathered, no mass migration** (per F-003). howler +
   tess-dashboard stamped `frozen` (they carry local copies; howler ships to a
   store). tessera stamped `source`. Flip when convenient.

---

## Alternatives considered

- **G2 — move mnemos hooks into global `~/.claude/settings.json`.** Rejected:
  fires on every project including non-Tessera ones, collides with GSD's global
  hooks (ADR-0001), maximizes "all projects change together" blast radius, and
  removes per-project opt-out. G1 keeps granularity.
- **Status quo — all projects keep local copies forever.** Rejected: manual
  N-way sync is the drift F-003 named; cost grows with project count.
- **Full global now — thaw all three existing repos.** Rejected: howler is
  shipping and wants churn-immune hooks; F-003 explicitly said don't mass-migrate.

---

## Consequences

- **Positive:** New projects ride a single source, zero drift day one. The switch
  the observatory thought existed now actually exists. freeze↔thaw is reversible.
- **Positive:** `status`'s drift check surfaces declared-vs-actual mismatch — the
  exact silent-success failure mode (empty layer, dead shebang) this project
  keeps hitting.
- **Cost (machine coupling):** a `global` project's hooks only fire where
  `install.sh` has populated `~/.claude/templates/`. On a fresh machine with an
  empty global layer they silently no-op. Mitigated by install.sh's `verify()`
  (hard-aborts on empty global layer) and the scaffold's global-mode reminder to
  run install.sh. A `frozen`/`source` project is immune (self-contained).
- **Cost (thaw needs fallback):** the 3 grandfathered repos' *live* settings.json
  predate the fallback branch, so `thaw` refuses them until their settings are
  updated. Deliberate — refuse-with-guidance beats silently dead hooks. Auto-patch
  in thaw is deferred (no repo is thawing yet; YAGNI).
- **Scope:** only mnemos hooks. The tier-classify / subagent-route hooks
  (ADR-0002) resolve on their own path and are out of scope here.

---

## Re-evaluate trigger conditions

- A `global` project's hooks are found silently dead on a machine → strengthen the
  scaffold reminder into a hard check, or teach `status` to run at SessionStart.
- First real `thaw` of a grandfathered repo → build the settings-fallback
  auto-patch into `thaw` rather than refuse-with-guidance.
- Project count crosses ~4–5 with several still `frozen` → revisit whether frozen
  is worth its sync cost, or push more projects to `global`.
- The tier-classify / subagent-route hooks need the same global-mode support →
  extend the fallback pattern to them.

---

## References

- Observatory F-003 — Downstream script drift (the entry this decision graduates)
- ADR-0003 — Tessera owns its distribution (install.sh, the `~/.claude/templates/` layer)
- ADR-0001 — GSD coexistence (global settings merge semantics)
- `templates/tessera/settings.base.json` — the fallback branch
- `bin/tessera-new-project`, `bin/tessera-hooks` — inception + inflection enactment
