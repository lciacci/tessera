# ADR-0003: Tessera owns its distribution; maggy depends on Tessera, not the reverse

- **Date:** 2026-06-26
- **Status:** Accepted
- **Decision driver:** Project decision — "should the bootstrap dir have its own version? Tessera should eventually not need maggy files/repo."

> Internal architecture decision (not an external-tool evaluation), so it uses the
> classic ADR form (Context / Decision / Alternatives / Consequences / Re-evaluate)
> like ADR-0002, not `_template.md`.

---

## Context

Tessera's scaffolding had a hidden runtime dependency on the external
**maggy/claude-bootstrap** repo. Symptoms surfaced while wiring the model-tier
routing hooks (ADR-0002) into downstream scaffolding:

- The session-hook commands in `templates/settings.json` resolve their scripts
  from a project's `.claude/scripts/` **or** a `$HOME/.claude/templates/`
  fallback. That fallback was populated only by maggy's `install.sh` — absent
  here, so the fallback resolved to nothing.
- `commands/initialize-project.md` Phase 0 hard-called
  `$BOOTSTRAP_DIR/tests/validate-structure.sh`, a maggy-only file, and
  `~/.claude/.bootstrap-dir` pointed at a maggy checkout.

Yet Tessera **already vendored ~80% of the installer**: `detect-agents.sh`,
`install-hooks.sh`, `install-skills.sh`, `install_session_hooks.py`,
`onboard.sh`, `model_routing.py`. The only missing keystone was a unifying
entrypoint that copies the pieces into `~/.claude/` and writes the marker.

The boundary was under-specified (`docs/maggy-rfc.md`, the `phase-11-maggy-mesh`
/ `phase-05-maggy-v2-ui` specs show maggy as a **superset product** — UI, mesh —
not merely Tessera's installer). "Decouple from maggy" was really two decisions
that needed separating: distribution vs. the multi-provider routing harness.

---

## Decision

1. **Tessera owns its own distribution.** A root `install.sh` copies skills /
   commands / hooks into `~/.claude/`, populates the `$HOME/.claude/templates/`
   script-fallback from `.claude/scripts/`, installs `templates/settings.json` +
   `install_session_hooks.py` as the scaffold source, and writes
   `~/.claude/.bootstrap-dir` pointing at the Tessera clone. `git clone tessera
   && ./install.sh` now scaffolds projects with **zero maggy dependency**.

2. **Invert the dependency, don't sever it.** Tessera must stand alone; maggy,
   as the superset, embeds Tessera. `.bootstrap-dir` resolves to whichever repo
   ran `install.sh` — Tessera self-hosted, or a maggy checkout when embedded —
   so the same `$BOOTSTRAP_DIR` references work both ways. maggy → Tessera, never
   Tessera → maggy.

3. **Do NOT absorb the multi-provider routing harness.** The full
   DeepSeek/Gemini/MiniMax/Kimi/council/srooter stack is maggy's reason to exist.
   Tessera owns only the **Claude-tier sliver** (`tier-classify-hook` /
   `subagent-route-hook`, ADR-0002), which fails open to Sonnet when its local
   classifier is absent. Multi-provider stays an **optional** maggy integration.

4. **Maggy-only artifacts degrade gracefully.** `initialize-project` Phase 0 runs
   `validate-structure.sh` only if present, else falls back to a self-hosted
   check that `~/.claude/{skills,commands,hooks}` landed.

---

## Alternatives considered

- **Full absorption — vendor the entire maggy harness into Tessera.** Rejected:
  bloats Tessera, breaks its "Claude Code framework" identity, and duplicates a
  product that has its own UI/mesh roadmap. Dependency inversion gets
  self-sufficiency without the bloat.
- **Status quo — keep the maggy hard dependency.** Rejected: the empty
  `~/.claude/templates/` fallback is a silent failure mode (routing simply never
  fires downstream), and a framework that can't install itself isn't a framework.
- **Delete the maggy relationship entirely.** Rejected: repo evidence shows maggy
  is a legitimate superset consumer; inversion preserves that without coupling.

---

## Consequences

- **Positive:** Tessera self-installs and self-scaffolds standalone. The hidden
  fallback dependency flagged during ADR-0002 work is closed. The
  Tessera/maggy boundary is now explicit and one-directional.
- **Positive:** `install.sh` is idempotent and thin (~70 lines) — it wires
  existing scripts rather than reimplementing them.
- **Cost:** Two sources of truth for the install pieces if maggy also vendors its
  own copies — drift risk. Mitigated by inversion: maggy should consume
  Tessera's, not fork them.
- **Cost:** `validate-structure.sh` (maggy-only) is not reimplemented; the
  self-hosted path does a shallower directory check. Acceptable until evidence
  says otherwise.

---

## Re-evaluate trigger conditions

- maggy starts vendoring its own forks of Tessera's install scripts (drift
  observed) → enforce inversion or extract a shared installer package.
- A second superset consumer (besides maggy) needs Tessera's distribution →
  consider promoting `install.sh` to a versioned, published artifact.
- The self-hosted Phase 0 check misses a real breakage `validate-structure.sh`
  would have caught → port a minimal validator into Tessera.

---

## References

- ADR-0002 — model effort-tier routing (the work that surfaced the hidden dep)
- `install.sh` — the self-install entrypoint this ADR introduces
- `commands/initialize-project.md` Phase 0 / Step 7c — graceful self-hosted paths
- `docs/maggy-rfc.md`, `docs/claude-bootstrap-reference.md` — the prior, under-specified boundary
