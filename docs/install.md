# Tessera install guide

This is what it takes to get Tessera running on a fresh machine. Follow in order. The whole thing should take under 30 minutes.

## Prerequisites

You need:

- macOS or Linux (the framework assumes Unix shell conventions)
- `curl` — `install.sh` uses it to fetch [uv](https://docs.astral.sh/uv/), which brings its own Python
- Node.js 20.19+ or 22.12+ (for any downstream Tessera projects that scaffold from Vite)
- Git
- [Claude Code](https://docs.claude.com/claude-code) CLI installed and authenticated

**You do NOT need to install Python.** This section used to demand "Python 3.10+ on PATH (Homebrew 3.13)" and carried a long warning about arm64 vs Intel Homebrew kegs producing a `mnemos` whose shebang breaks silently. All of that is obsolete, and its obsolescence is the point: **Tessera no longer lets a package manager own its interpreter.** The toolchain lives in a `uv`-managed venv (`.venv/`, pinned by `.python-version`), whose base sits under `~/.local/share/uv/python/` where Homebrew cannot reach it. See F-001 in [the observatory](observatory.md).

You do **not** need a clone of [Maggy](https://github.com/alinaqi/maggy), the project Tessera was forked from. Earlier revisions of this guide told you to clone `maggy-main` because "Mnemos source lives inside it" — that was never true of *this* repo: Tessera vendors its own `scripts/mnemos/`, and that is what a working install actually imports. ADR-0003 decided Tessera owns its distribution; this guide now matches. See [NOTICE](../NOTICE) for provenance.

## Step 1 — Clone Tessera

```bash
cd ~/Claude  # or wherever you want the framework to live
git clone https://github.com/lciacci/tessera.git
cd tessera
```

## Step 2 — Install the toolchain

```bash
./install.sh
```

That is the whole step. It is idempotent — re-run it any time.

It installs `uv` (via its **standalone installer**, deliberately *not* `brew install uv` — reintroducing a package-manager coupling in the first line of the fix would be absurd), provisions the Python pinned in `.python-version`, builds `.venv/`, installs the toolchain (`mnemos`, `icpg`, `polyphony`, `skill-lint`, `pytest`) into it as editable, and symlinks the console scripts into `~/.local/bin`.

> **Why `~/.local/bin` and not `tessera/bin`?** Because `~/.local/bin` precedes `/opt/homebrew/bin` on PATH and `tessera/bin` does not — it sits far behind it. A symlink in `tessera/bin` would be silently shadowed by any leftover Homebrew copy, and your hooks would keep resolving the old interpreter while everything *looked* fixed.

### What this replaces, and why it matters

This step used to be a ritual: restructure the source into `/tmp`, then `/opt/homebrew/bin/pip3.13 install --break-system-packages`, with warnings about arm64-vs-Intel kegs producing a `mnemos` whose shebang silently dies. **That ritual installed the toolchain into a Python that Homebrew owns and re-points at will** — and Homebrew *did* re-point it (to 3.14, because `ollama` wanted it). Every Mnemos checkpoint write no-op'd for weeks, invisibly. That is **F-001**, and it confounded the whole Mnemos trial: "the graph is empty" read as *unused* when it meant *unreachable*.

**An interpreter is a path, not a name.** A name (`python3`, `python3.13`) is a lookup through a mutable, ordered PATH that several package managers write to; any of them can win, at any time, without telling you. Nothing in Tessera resolves an interpreter by name any more, and there is no fallback to `python3` — a silent fallback to a toolchain-less interpreter is *how F-001 stayed invisible*.

Verify:

```bash
./install.sh                     # its verify() is the machine-known-good check
bin/tessera-watch                # P9 asserts the toolchain interpreter is reachable
                                 # AND that its base is not a package manager's
head -1 "$(command -v mnemos)"   # must point into <tessera>/.venv/bin/python
```

`install.sh` fails loudly if `mnemos` resolves an interpreter that is *not* the venv, or if the venv's base is rooted in Homebrew. "It runs" is not enough — that was exactly the false comfort F-001 hid behind. Check *which* interpreter it runs on.

## Step 3 — Initialize Mnemos in Tessera

```bash
cd ~/Claude/tessera  # or wherever you cloned to
mnemos init
mnemos status
```

`mnemos status` should report zero active nodes, zero checkpoints — that is the correct initial state.

## Step 4 — Install plugins

Per the design doc, Tessera relies on two Claude Code plugins at full mode during dogfood:

- `caveman` (juliusbrussee) — token-compression mode
- `ponytail` (DietrichGebert) — over-engineering reducer

Inside Claude Code:

```
/plugin install caveman
/plugin install ponytail@ponytail
```

For ponytail, also open `/hooks` once after install, review the two lifecycle hooks, and trust them. Without this step ponytail's hooks are silently skipped.

## Step 5 — Avoid the shell alias trap

**Do not** create a shell alias for `claude` that changes directory. Specifically, this line in `.zshrc` will break project-local settings loading:

```bash
# BAD — do not do this:
alias claude='cd /Users/lciacci/Claude; command claude'
```

The original install spent two hours debugging hook activation before discovering this alias was forcing `cwd` to a parent directory, which prevented `.claude/settings.json` from loading. Documented in `docs/observatory.md` under "Tessera hook activation in project-local config."

If you want a convenience launcher that does cd-and-launch, name it something other than `claude`:

```bash
# OK:
alias tessera='cd ~/Claude/tessera && claude'
```

## Step 6 — Verify hooks fire

From inside `tessera/`:

```bash
cd ~/Claude/tessera
claude
```

Inside the session:

```
/status
```

Confirm `cwd:` shows your tessera path and `Setting sources:` includes "Shared project settings."

Then:

```
/hooks
```

Drill into PreToolUse. Should show two project hooks (`[Project] (all)` and `[Project] Edit|Write`). If you see those, hooks are wired and active.

Exit the session. From the shell:

```bash
ls -la .mnemos/
cat .mnemos/fatigue.json 2>/dev/null | head -5
```

If `.mnemos/fatigue.json` exists with JSON content, the statusline hook fired during your session. The runtime layer is alive.

## Step 7 — Optional: GitHub authentication

To push commits back to the Tessera repo, the GitHub CLI needs to be authenticated:

```bash
gh auth status
gh auth login  # if not already authenticated
```

## Common gotchas

- **Anything involving `pip`, `--break-system-packages`, or a flat-layout setuptools error** — you are following an old copy of this guide. **There is no `pip` step any more.** `./install.sh` does everything through `uv`. Those three gotchas existed only because the toolchain was being forced into a Homebrew Python it never should have been in; that is F-001, and the whole install was rebuilt to make them impossible.
- **`/status` shows `cwd:` as a parent directory** — you have a `claude` shell alias that is `cd`ing somewhere before launching. Remove it (see Step 5).
- **Hooks show in `/hooks` but `.mnemos/` is never created** — the Mnemos CLI is not resolving. `./install.sh` and check `head -1 "$(command -v mnemos)"` points into `<tessera>/.venv/bin/python`. **Do not stop at "`mnemos --help` works"** — it worked throughout F-001, on the wrong interpreter, for six weeks. Check *which* interpreter.
- **`ModuleNotFoundError` from a script that ran fine yesterday** — something re-pointed an interpreter *name* out from under you. This is not hypothetical: `uv python install` shims `python3.13` into `~/.local/bin`, ahead of Homebrew. Never invoke the toolchain by name; use `.venv/bin/python`. `bin/tessera-watch` **P9** exists to catch exactly this.
- **`tessera-escalate: command not found` — but only for Claude, never for you.** The PATH export is in `~/.zshrc`, which zsh sources **only for interactive shells**. Claude Code's Bash tool runs a *non-interactive* shell, so it never reads it: the tools work perfectly at your terminal and do not exist for the agent — the exact reader `CLAUDE.md` writes those instructions for. Put the export in **`~/.zshenv`** (sourced for *every* zsh invocation) instead:
  ```sh
  # ~/.zshenv
  if [[ ":$PATH:" != *":$HOME/Claude/tessera/bin:"* ]]; then
    export PATH="$HOME/Claude/tessera/bin:$PATH"
  fi
  ```
  Verify the way the agent sees it, not the way you do — `zsh -c 'command -v tessera-escalate'` (non-interactive), not `which`. `install.sh`'s verify step checks this correctly. Found 2026-07-11: an escalation channel that cannot be invoked is worse than none, because the docs claim it.
- **First session works, second session does not** — you may have a stale `claude` process bound to the old cwd. `ps aux | grep claude` and kill any stragglers.

## What is not in this guide

- Setting up downstream Tessera projects (the dashboard, the decibel meter app). Each has its own `README.md` and `CLAUDE.md`.
- Installing iCPG (referenced in some hooks but not required for the framework to function).
- Configuring LiteLLM for multi-model routing — deferred per design principles, not part of v1.

## When this guide goes stale

Update it when:

- The Mnemos packaging issue gets fixed upstream (will simplify Step 2 to a one-liner)
- Tessera adds its own setup script (`install.sh`, at the repo root)
- A new platform is added (Linux specifics, Windows WSL, etc.)
- The plugin install procedure changes
