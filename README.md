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

Status: in development.

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

## License

MIT. Copyright (c) 2025 Ali Naqi (Maggy); Copyright (c) 2026 Lorenzo Ciacci
(Tessera). See [LICENSE](LICENSE).
