# Tessera

Personal agentic coding framework for Claude Code.

Tessera is **forked from [Maggy](https://github.com/alinaqi/maggy)** (MIT) — not
merely inspired by it. The repo was seeded by importing Maggy wholesale, and much
of the skill library, hook surface, and command set is still Maggy's. What Tessera
adds on top is a governing layer written from scratch: compounding design
principles, Architecture Decision Records, project profiles, an observatory of
undecided questions, and a set of mechanisms that hold the framework honest — a
suggestion-gate recorder, a doc-honesty checker, an escalation protocol, and
run-scoped external-spend authorization.

See [NOTICE](NOTICE) for the full provenance split — which files came from where.

Live descriptor page: [houseofyeti.com/tessera](https://houseofyeti.com/tessera/).

Status: active dogfood, not a finished product. See
[Known limitations](#known-limitations) below before assuming anything here is
production-grade.

## Getting started

Tessera is self-hosting. You do **not** need to clone Maggy.

```bash
git clone https://github.com/lciacci/tessera.git
cd tessera
./install.sh
```

`install.sh` is idempotent — re-run it anytime to refresh. See
[GETTING_STARTED.md](GETTING_STARTED.md) for what it installs and what to do next.

## Documentation

- [`docs/design-principles.md`](docs/design-principles.md) — the design doc. Why Tessera is what it is. Read first.
- [`docs/adr/`](docs/adr/) — Architecture Decision Records; numbered, dated, immutable once accepted.
- [`docs/observatory.md`](docs/observatory.md) — concepts on the radar but not yet decided.
- [`docs/contracts/`](docs/contracts/) — the contracts Tessera's own mechanisms must honor.
- [`docs/postmortem-2026-07-12.md`](docs/postmortem-2026-07-12.md) — a full account of the
  session that found Tessera cannot tell when it is broken. Read this before trusting any
  "it works" claim, including this README's.

## Known limitations

Tessera's own dogfooding turned up findings worth stating plainly rather than
burying:

- **Fail-open, not fail-loud, was the default.** A 2026-07-12 session (see the
  postmortem above) found eight silent failures in Tessera's own safety
  machinery, including a spend guard that failed *open* on Python 3.9 (an
  unauthorized spend could have proceeded) and a spend backstop that shipped
  disabled in every clone. None of the eight announced itself — each was found
  by a human getting suspicious or by an independent adversarial check, never
  by the framework itself. [ADR-0006](docs/adr/0006-instrumentation-not-control.md)
  retargets Tessera's goal accordingly: **instrumentation, not control** — it
  aims to make the agent's unreliability visible and bounded, not to make the
  agent reliable.
- **Mechanized checks held; prose rules didn't.** Every rule enforced by a hook
  or a script survived that session. Every rule that existed only as a sentence
  in a doc or a handoff — including ones the model wrote itself — failed at
  least once. This shaped the direction: prefer checks over conventions.
- **The Mnemos memory layer's trial is still inconclusive.** Months of dogfood
  have produced zero real, classifiable compaction-recovery events to judge it
  on ([`docs/observatory.md`](docs/observatory.md)).
- **56 skills ship, effectively none of them audited.** Most were inherited
  wholesale from Maggy; pruning on evidence is planned but not done.
- **Adversarial verification — the mechanism with the best track record in
  practice — is not yet built into the framework.** It currently depends on a
  human remembering to ask for it (spec 12, in progress).

## License

MIT. Copyright (c) 2025 Ali Naqi (Maggy); Copyright (c) 2026 Lorenzo Ciacci
(Tessera). See [LICENSE](LICENSE).
