# Tessera install guide

This is what it takes to get Tessera running on a fresh machine. Follow in order. The whole thing should take under 30 minutes.

## Prerequisites

You need:

- macOS or Linux (the framework assumes Unix shell conventions)
- Python 3.10+ on PATH (Homebrew Python 3.13 is what the original install used). **On Apple Silicon, use the native arm64 Homebrew at `/opt/homebrew`.** If a stale Intel Homebrew also exists at `/usr/local` and sits earlier on `PATH`, its `pip` builds a `mnemos` whose shebang points into the Intel keg — which breaks the moment that keg is cleaned, silently disabling every Mnemos hook. Confirm before installing: `file "$(command -v python3.13)"` must report `arm64`.
- Node.js 20.19+ or 22.12+ (for any downstream Tessera projects that scaffold from Vite)
- Git
- [Claude Code](https://docs.claude.com/claude-code) CLI installed and authenticated
- A reference clone of [maggy-main](https://github.com/alinaqi/maggy) at a known path. The original install used `/Users/lciacci/Claude/maggy-main`. Mnemos source lives inside it.

If you do not have maggy-main yet:

```bash
cd ~/Claude  # or wherever you keep reference clones
git clone https://github.com/alinaqi/maggy.git maggy-main
```

## Step 1 — Clone Tessera

```bash
cd ~/Claude  # or wherever you want the framework to live
git clone https://github.com/lciacci/tessera.git
cd tessera
```

## Step 2 — Install Mnemos

The Mnemos Python package backs Tessera hook scripts. It lives in `maggy-main/scripts/mnemos/` but ships with a flat-layout `pyproject.toml` that setuptools rejects on modern Python. The original install fixed this by copying source into a proper package layout in `/tmp`.

```bash
mkdir -p /tmp/mnemos-install/mnemos
cp /path/to/maggy-main/scripts/mnemos/*.py /tmp/mnemos-install/mnemos/
cp /path/to/maggy-main/scripts/mnemos/pyproject.toml /tmp/mnemos-install/
/opt/homebrew/bin/pip3.13 install --break-system-packages /tmp/mnemos-install
```

Replace `/path/to/maggy-main` with the actual path. **On Apple Silicon keep `/opt/homebrew/bin/pip3.13` explicit — do not substitute "whatever pip is on PATH". A stale Intel `/usr/local` pip produces a `mnemos` shebang that later breaks (see Prerequisites).** On Linux or Intel Macs, use your Python 3.10+ pip.

Verify:

```bash
which mnemos
mnemos --help
# Critical on Apple Silicon — confirm the console-script shebang resolves:
head -1 "$(command -v mnemos)"   # the path after #! must exist on disk
mnemos --version                 # must run, NOT "bad interpreter: ... no such file"
```

If `mnemos --help` prints the subcommand list (init, status, fatigue, checkpoint, resume, etc.) **and `mnemos --version` runs without a `bad interpreter` error**, Mnemos is installed. A dead shebang is the silent-failure mode the hooks' graceful degradation otherwise masks — if `mnemos --version` fails, reinstall with the arm64 `/opt/homebrew/bin/pip3.13` and remove any stale `/usr/local/bin/mnemos`.

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

- **`pip: command not found`** — your default `pip` is too old or missing. Use `/opt/homebrew/bin/pip3.13` (or whatever your Homebrew Python ships).
- **`no such option: --break-system-packages`** — same cause as above. Modern pip needs this flag on macOS due to PEP 668; older pips do not recognize it.
- **`Multiple top-level modules discovered in a flat-layout`** during Mnemos install — you skipped the `/tmp/mnemos-install/mnemos/` restructuring. The flat layout in `maggy-main/scripts/mnemos/` needs the modules nested one level deeper for setuptools to accept it.
- **`/status` shows `cwd:` as a parent directory** — you have a `claude` shell alias that is `cd`ing somewhere before launching. Remove it (see Step 5).
- **Hooks show in `/hooks` but `.mnemos/` is never created** — Mnemos CLI is not on PATH. Run `which mnemos` to check, reinstall if missing.
- **First session works, second session does not** — you may have a stale `claude` process bound to the old cwd. `ps aux | grep claude` and kill any stragglers.

## What is not in this guide

- Setting up downstream Tessera projects (the dashboard, the decibel meter app). Each has its own `README.md` and `CLAUDE.md`.
- Installing iCPG (referenced in some hooks but not required for the framework to function).
- Configuring LiteLLM for multi-model routing — deferred per design principles, not part of v1.

## When this guide goes stale

Update it when:

- The Mnemos packaging issue gets fixed upstream (will simplify Step 2 to a one-liner)
- Tessera adds its own setup script (`scripts/install.sh` or similar)
- A new platform is added (Linux specifics, Windows WSL, etc.)
- The plugin install procedure changes
