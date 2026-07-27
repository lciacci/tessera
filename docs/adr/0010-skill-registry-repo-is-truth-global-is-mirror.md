# ADR-0010: Skill registry — repo is truth, global is a managed mirror

- **Date:** 2026-07-20
- **Status:** Accepted
- **Executed:** 2026-07-17 — `bin/tessera-sync-skills` (repo → global mirror) plus `bin/tessera-watch` P12, which fires on mirror drift and did so this session.
- **Refines:** ADR-0009 (leaves curation untouched; fixes what curation selects *from*). Closes ADR-0007 finding #7 (the de-dup) and ADR-0008's "delivery mechanism NOT decided."
- **Decision drivers:** two observatory entries — "Skill registry — which copy is the source of truth" and "Skill-body delivery has no copy mechanism — and a skill claimed it did." Adjudicated with Lorenzo 2026-07-20.

---

## The problem

Claude Code union-loads `~/.claude/skills` (global, machine-level) into every project on the
machine (ADR-0009). Downstream projects therefore receive whatever body the *global* copy holds.
But global is unmanaged: not in git, no writer, no checker. Measured 2026-07-20:

- Repo `skills/` = 47 — where every edit, trim, merge, and review actually lands (the framework's
  project `.claude/skills` symlinks to it).
- Global = 57: the shared 47 **plus all 10 skills ADR-0008/#28 cut** — the cuts never propagated.
  Verified: every global-only entry is an adjudicated cut (plus one misfiled older draft of
  `adr-gate` inside `code-review/`); nothing personal lives only in global.
- **6 of the shared 47 had already diverged** (base, code-review, mnemos, python, ui-mobile,
  ui-web) — recent curation work that downstream consumers never received.
- **Build-time correction (read-first paid off again):** a copier DID exist —
  `scripts/install-skills.sh` (Maggy baseline), wired into `install.sh`, but **additive-only**
  (`cp -r`, no delete). That is why shared bodies refreshed whenever `install.sh` happened to run,
  while cut skills persisted forever. The observatory's "no copy mechanism" was half-right: the
  missing pieces were *deletion* and *a watcher*, not copying. An additive copier is arguably
  worse than none — it keeps the mirror fresh enough to look maintained while zombies accumulate.

Worse, the unmanaged mirror had already produced a documented deletion-safety illusion: the
`base` skill claimed its trimmed content "survives in the full-body global copy" — false
(doccheck `no-phantom-global-skill-body-claim` now guards that class).

## Decision

**1. Source of truth: repo `skills/`.** Git-tracked, PR-reviewed, doccheck-guarded. Global is
never edited directly; it holds no original content by definition.

**2. Global is a managed mirror: `bin/tessera-sync-skills`.** One-way `rsync --delete`
repo→global, printing the full delta it applies (`--dry-run` to preview). Wired into
`./install.sh`, so a fresh machine gets the current registry the same way it gets the toolchain
— this also closes the skill-share of the "new-machine bootstrap is tribal knowledge" gap.
The sync never writes repo-side; there is no reverse path.

**3. Drift is watched: `tessera-watch` P12 (skill-registry drift).** Diffs repo vs global and
fires on any difference — the same shape as P1 (hook-drift, scripts vs templates). A mirror
without a watcher is how the last three weeks of divergence happened silently.

**4. Single-body policy.** One body serves every consumer — framework sessions, downstream
projects, and every other repo on the machine. "The full body survives globally" is dead as a
trim rationale: a cut is a cut for downstream too, so HARVEST-BEFORE-CUT (ADR-0007) now applies
with downstream consumers explicitly in mind, and anything a downstream genuinely needs is
restored into the skill (or homed in an on-demand sibling) as an explicit, reviewed change.

**Applicability stays curation's job (ADR-0009), not sync's.** "Not everything Tessera fits
globally" is real — and it is answered per-project by `skillOverrides` selection, not by letting
bodies drift. Sync decides *freshness*; overrides decide *visibility*.

## What the first sync changes (applied 2026-07-20)

Every repo on this machine immediately: loses the 10 zombie listings (listing budget 57→47
machine-wide), and receives the 6 updated bodies. The delta was printed and reviewed at apply
time. The 10 deletions re-execute ADR-0008's adjudicated dispositions — content was harvested
before those cuts; the bodies remain in git history (pre-`3a36bc4` and #22/#28).

## What this deliberately does not do

- **No two-artifact split** (framework-lean vs downstream-full bodies). Dual maintenance,
  guaranteed drift, and it re-creates the exact illusion the phantom-claim bug came from.
- **No per-skill symlinks from global into the repo.** No copy drift, but every repo on the
  machine would then read live working-tree state — mid-edit, mid-rebase — and a moved/deleted
  repo silently breaks the machine. A synced copy fails stale, which P12 catches; a symlink
  fails weird.
- **No plugin packaging.** `skillOverrides` cannot gate plugin skills (ADR-0009) — packaging
  would break the curation layer.
- **Skill content decisions** — this ADR moves bodies; what belongs *in* them stays governed by
  ADR-0007/0008 discipline.

## Re-evaluate triggers

- **A second machine (or another person) consumes the registry** → the mirror needs a
  distribution channel (git pull + sync, or packaging); re-open the mechanism, not the
  source-of-truth decision.
- **A downstream needs a skill body Tessera deliberately does not carry** → the single-body
  policy meets its first real exception; decide restore-vs-sibling-vs-split on that skill's
  evidence.
- **Claude Code load semantics change** (project dirs gain restrict-global, or listing budget
  becomes per-project) → re-derive with ADR-0009.
- **P12 fires repeatedly from non-Tessera edits to global** → someone/something else is writing
  the mirror; the one-way assumption broke — find the writer before re-syncing over it.

## References

- ADR-0007 (finding #7, HARVEST-BEFORE-CUT), ADR-0008 (corpus verdict + delivery reframe),
  ADR-0009 (curation via `skillOverrides`; union-load semantics), ADR-0004 (the
  one-source/per-project-config precedent hooks set).
- `docs/observatory.md` → the two source entries, resolved by this ADR.
- `bin/tessera-sync-skills`, `./install.sh`, `bin/tessera-watch` P12.
