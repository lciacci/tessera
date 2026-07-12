# Getting started with Tessera

Tessera is a personal agentic coding framework for Claude Code. It is
**self-hosting**: cloning this repo and running `./install.sh` is the whole
install. You do not need to clone [Maggy](https://github.com/alinaqi/maggy), the
project Tessera was forked from — see [NOTICE](NOTICE) and ADR-0003.

## Install

```bash
git clone https://github.com/lciacci/tessera.git
cd tessera
./install.sh
```

`install.sh` is idempotent; re-run it anytime to refresh. Copies are overwrites,
not merges.

It:

- copies `skills/`, `commands/`, and `hooks/` into `~/.claude/`
- populates the `~/.claude/templates/` script-fallback from `.claude/scripts/`
- installs `templates/settings.json` + `install_session_hooks.py` as the scaffold
  source for new projects
- writes `~/.claude/.bootstrap-dir` pointing at **this** clone

The installer's own `verify()` is the machine-known-good check — if it prints a
clean run, the install landed.

Then, in any project:

```bash
cd your-project
claude
> /initialize-project
```

## Working in Tessera itself

If you are developing the framework rather than using it, read
[`CLAUDE.md`](CLAUDE.md) — it carries the working conventions — and then:

| Command | What it does |
|---|---|
| `tessera-test` | Run the full suite. Reads `test:` from `.tessera/config.yml` — never guess the test command. |
| `tessera-watch` | Evaluate the observatory's machine-checkable triggers. Also runs at SessionStart. |
| `python3 scripts/doccheck.py` | Assert the docs' checkable claims. Enforced by `.githooks/pre-commit`. |
| `tessera-authorize` | Grant a run-scoped external-spend envelope. Required before any spend-committing command. |
| `tessera-escalate` | Raise an escalation packet when blocked and no human is available. |

Note: bare `python3` here is Homebrew 3.14, which has no pytest — the toolchain
lives in 3.13. See [`docs/install.md`](docs/install.md).

## Where to read next

- [`docs/design-principles.md`](docs/design-principles.md) — the design rationale. Start here.
- [`docs/adr/`](docs/adr/) — the decisions, with their reasoning and re-evaluate triggers.
- [`docs/observatory.md`](docs/observatory.md) — what is still undecided.
- [`docs/contracts/`](docs/contracts/) — the contracts Tessera's mechanisms must honor.
- [`docs/install.md`](docs/install.md) — fresh-machine setup, including the Python toolchain caveat.
