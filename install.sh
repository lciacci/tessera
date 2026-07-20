#!/bin/bash
# Tessera self-install — make this clone the source of truth for ~/.claude.
#
# Decouples Tessera's scaffolding from the external maggy/claude-bootstrap repo
# (ADR-0003): after this runs, `/initialize-project` and the session-hook
# fallback path resolve against THIS repo, with zero maggy dependency.
#
# Idempotent: re-run anytime to refresh. Copies are overwrites, not merges.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE="$HOME/.claude"
TEMPLATES="$CLAUDE/templates"

say()  { printf "  %s\n" "$1"; }
ok()   { printf "  ✓ %s\n" "$1"; }
warn() { printf "  ! %s\n" "$1"; }
err()  { printf "  ✗ %s\n" "$1"; }

OLLAMA_BASE="${OLLAMA_BASE:-http://localhost:11434}"

install_skills() {
  # ADR-0010: repo is truth, global is a managed MIRROR — sync with delete, not
  # additive copy. The old install-skills.sh cp -r kept cut skills alive in
  # global forever (10 zombies, 2026-07-20); it stays for non-Claude targets
  # (~/.kimi, ~/.codex) but no longer serves ~/.claude.
  TESSERA_GLOBAL_SKILLS="$CLAUDE/skills" "$REPO/bin/tessera-sync-skills" >/dev/null
  say "skills      -> $CLAUDE/skills (mirror, ADR-0010)"
}

install_dir() {
  local name="$1" src="$REPO/$1" dst="$CLAUDE/$1"
  [ -d "$src" ] || return 0
  mkdir -p "$dst"
  cp -R "$src"/. "$dst"/
  say "$name -> $dst"
}

# Keystone: the session-hook commands in templates/settings.json resolve their
# scripts from a project's .claude/scripts/ OR this $HOME/.claude/templates/
# fallback. Populating it here is what lets downstream projects route without
# carrying the scripts themselves.
install_script_fallback() {
  mkdir -p "$TEMPLATES"
  cp "$REPO/.claude/scripts/"* "$TEMPLATES/" 2>/dev/null || true
  chmod +x "$TEMPLATES/"* 2>/dev/null || true
  say "hook scripts -> $TEMPLATES (fallback resolve path)"
}

install_scaffold_source() {
  mkdir -p "$TEMPLATES"
  cp "$REPO/templates/settings.json" "$TEMPLATES/settings.json"
  cp "$REPO/scripts/install_session_hooks.py" "$CLAUDE/install_session_hooks.py"
  say "scaffold src -> $TEMPLATES/settings.json + install_session_hooks.py"
}

write_marker() {
  echo "$REPO" > "$CLAUDE/.bootstrap-dir"
  say ".bootstrap-dir -> $REPO (self-hosted)"
}

# Point git at the TRACKED hook dir. .git/hooks/ is not tracked, so a hook installed there
# exists on one disk and nowhere else — a fresh clone would silently have no pre-commit gate.
# core.hooksPath is per-clone config, so it must be set by the installer and CHECKED by
# verify(); otherwise the gate is present in the repo and simply not wired, which is the
# worst state: it looks like coverage and enforces nothing.
install_git_hooks() {
  [ -d "$REPO/.githooks" ] || return 0
  chmod +x "$REPO/.githooks/"* 2>/dev/null || true
  git -C "$REPO" config core.hooksPath .githooks
  say "git hooks -> .githooks (pre-commit: doccheck)"
}

# Turn silent-success into loud-failure. Hard checks (✗) abort; soft checks (!)
# warn only. Audited against the four new-machine bootstrap steps (observatory:
# "New-machine bootstrap is tribal knowledge"). Does NOT install mnemos — that
# is docs/install.md Step 2 (maggy-source + flat-layout dependency) — but it
# verifies mnemos is healthy so a dead shebang (F-001) fails loud here.
# The toolchain lives in a uv-managed venv, NOT in a Homebrew python. This is the F-001 fix.
#
# F-001: hooks called the toolchain through a bare `python3` that Homebrew had silently
# re-pointed (3.13 → 3.14, because *ollama* wanted 3.14). Every checkpoint write no-op'd for
# weeks, invisibly, and it confounded the whole Mnemos trial — "the graph is empty" read as
# "unused" when it meant "unreachable".
#
# Migrating into 3.14 only resets the clock: brew re-points `python3` whenever a DEPENDENT
# formula moves, and 3.15 will do it again. A brew-based venv is better but still roots the
# interpreter in the package manager that caused the problem. uv owns its own interpreters
# under ~/.local/share/uv/python — brew cannot touch them — and `uv` itself is a static
# binary with no libpython linkage.
#
# Installed via uv's STANDALONE installer, deliberately not `brew install uv`: reintroducing
# the coupling in the first line of the fix would be absurd.
install_venv() {
  local root; root="$(cd "$(dirname "$0")" && pwd)"

  if ! command -v uv >/dev/null 2>&1; then
    say "installing uv (standalone binary — not via brew, that is the whole point)"
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || {
      err "uv install failed — see https://docs.astral.sh/uv/"; return 1
    }
    export PATH="$HOME/.local/bin:$PATH"
  fi

  local pyver; pyver=$(cat "$root/.python-version")
  uv python install "$pyver" >/dev/null 2>&1

  # Idempotent: install.sh is re-run constantly, and `uv venv` refuses to clobber. Only
  # create when absent. A venv that exists but is rooted in a package manager is NOT silently
  # rebuilt here — verify() reports it and tells you to `rm -rf .venv`. Destroying an
  # environment someone may be mid-debug in is not install.sh's call to make.
  if [ ! -x "$root/.venv/bin/python" ]; then
    uv venv "$root/.venv" --python "$pyver" --python-preference only-managed >/dev/null 2>&1 || {
      err "uv venv failed"; return 1
    }
  fi
  uv pip install -q --python "$root/.venv/bin/python" \
     -e "$root/scripts/mnemos" -e "$root/scripts/icpg" \
     -e "$root/scripts/polyphony" -e "$root/scripts/skill_lint" pytest || {
    err "toolchain install into venv failed"; return 1
  }

  # Console scripts must WIN on PATH. ~/.local/bin precedes /opt/homebrew/bin; tessera/bin
  # does NOT (it sits at position ~17, behind brew) — a symlink there would be silently
  # shadowed by any leftover brew copy, and the hooks would keep resolving the old
  # interpreter while everything *looked* fixed. Verified 2026-07-12, the hard way.
  mkdir -p "$HOME/.local/bin"
  local c
  for c in mnemos icpg polyphony skill-lint; do
    [ -x "$root/.venv/bin/$c" ] && ln -sf "$root/.venv/bin/$c" "$HOME/.local/bin/$c"
  done
  ok "venv built (uv-managed python, toolchain installed, console scripts linked)"
}

verify() {
  echo ""
  say "Verify"
  say "──────"
  local fail=0

  # 1. Global layer actually populated (install_dir silently skips missing src).
  local d
  for d in skills commands templates; do
    if [ -n "$(ls -A "$CLAUDE/$d" 2>/dev/null)" ]; then
      ok "$d populated"
    else
      err "$CLAUDE/$d empty — source dir missing or install step skipped"
      fail=1
    fi
  done

  # 1b. tessera/bin on PATH. These are single-source tools reached by name (the F-003 trap
  # is copying them into every repo). Without PATH, downstream CLAUDE.md instructions like
  # `tessera-escalate raise` silently refer to a command that does not exist — and an
  # escalation channel that cannot be invoked is worse than none, because the docs claim it.
  #
  # It MUST be ~/.zshenv, not ~/.zshrc. `.zshrc` is sourced only for INTERACTIVE shells, so an
  # export there is invisible to the shell Claude Code runs its Bash tool in: the tools work
  # for the human and are "command not found" for the agent — the exact reader the docs are
  # written for. Found the hard way 2026-07-11. `.zshenv` is sourced for every zsh invocation.
  # This check runs non-interactively, so it verifies what the AGENT sees, not what you see.
  if ! command -v tessera-escalate >/dev/null 2>&1; then
    err "tessera/bin not on PATH — add to ~/.zshenv (NOT ~/.zshrc, which interactive-only):"
    err "    export PATH=\"\$HOME/Claude/tessera/bin:\$PATH\""
    fail=1
  fi

  # 2. mnemos on PATH, shebang resolves, runs (F-001 — the silent hook killer).
  #    AND the shebang must point INTO THE VENV. A live mnemos is not enough: before the venv
  #    landed, mnemos worked perfectly while resolving a Homebrew interpreter that brew was
  #    free to re-point out from under it. "It runs" was exactly the false comfort F-001 hid
  #    behind for six weeks — so check WHICH interpreter it runs on, not merely that it runs.
  local root; root="$(cd "$(dirname "$0")" && pwd)"
  if ! command -v mnemos >/dev/null 2>&1; then
    err "mnemos not on PATH — run ./install.sh (it builds the venv and links ~/.local/bin)"
    fail=1
  else
    local interp
    interp=$(head -1 "$(command -v mnemos)"); interp=${interp#\#!}; interp=${interp%% *}
    if [ -n "$interp" ] && [ ! -x "$interp" ]; then
      err "mnemos shebang dead ($interp missing, F-001) — re-run ./install.sh"
      fail=1
    elif ! mnemos --version >/dev/null 2>&1; then
      err "mnemos --version failed (bad interpreter?)"
      fail=1
    elif [ "$interp" != "$root/.venv/bin/python" ]; then
      err "mnemos resolves $interp, NOT the venv — a package manager owns your toolchain (F-001)"
      err "    expected: $root/.venv/bin/python"
      err "    re-run ./install.sh; if it persists, an older copy is shadowing ~/.local/bin"
      fail=1
    else
      ok "mnemos healthy on the venv ($(mnemos --version 2>/dev/null))"
    fi
  fi

  # 2b. mnemos must resolve in a PRISTINE NON-INTERACTIVE shell — what the hooks actually get.
  #
  #     THIS IS THE CHECK THAT WAS MISSING, and its absence cost us F-001 twice. `~/.zshrc` is
  #     interactive-only. uv's installer wrote the ~/.local/bin PATH export there, so `mnemos`
  #     was unresolvable non-interactively — and the Mnemos hooks then fell through to
  #     `python3 -m mnemos`, which (with PYTHONPATH=scripts) does not fail: it SILENTLY
  #     SUCCEEDS on whatever interpreter owns the `python3` name. Every checkpoint routed
  #     through a Python Homebrew can re-point or delete, while `mnemos status` looked healthy.
  #
  #     `.zshenv` already carried a long comment explaining exactly this trap, from the last
  #     time it happened. A prose lesson, written and read, did not prevent the recurrence —
  #     because a third-party installer wrote the line. Only this check does.
  #
  #     `env -i` is the point: it strips the inherited environment, so this measures what a
  #     fresh shell resolves, not what YOUR shell happens to have exported.
  if ! env -i HOME="$HOME" zsh -c 'command -v mnemos' >/dev/null 2>&1; then
    err "mnemos does NOT resolve in a pristine non-interactive shell — the hooks cannot find it"
    err "    Your interactive shell may work fine; the agent's does not. Add to ~/.zshenv"
    err "    (NOT ~/.zshrc, which is interactive-only):"
    err "        export PATH=\"\$HOME/.local/bin:\$PATH\""
    fail=1
  else
    ok "mnemos resolves non-interactively (what the hooks actually get)"
  fi

  # 3. The venv's base interpreter is uv-managed, not a package manager's. If brew (or any
  #    other manager) owns the base, the whole fix is cosmetic — brew moves, we break.
  if [ -x "$root/.venv/bin/python" ]; then
    local base; base=$("$root/.venv/bin/python" -c 'import sys; print(sys.base_prefix)' 2>/dev/null)
    case "$base" in
      *homebrew*|*Cellar*)
        err "venv is rooted in Homebrew ($base) — brew can re-point it. Rebuild: rm -rf .venv && ./install.sh"
        fail=1 ;;
      "") err "venv python is broken — rebuild: rm -rf .venv && ./install.sh"; fail=1 ;;
      *)  ok "venv base is manager-independent ($base)" ;;
    esac
  else
    err "no venv at $root/.venv — run ./install.sh"
    fail=1
  fi

  # 3. Routing deps — warn only; tier-classify-hook fails open to Sonnet.
  if curl -s --connect-timeout 2 "$OLLAMA_BASE/api/tags" 2>/dev/null | grep -q "qwen2.5-coder"; then
    ok "routing: ollama up, qwen model present"
  else
    warn "ollama/qwen2.5-coder absent — routing fails open to Sonnet (ollama pull qwen2.5-coder:3b)"
  fi

  # 3b. The pre-commit gate is actually WIRED. The hook being present in .githooks/ proves
  # nothing — core.hooksPath is per-clone config, and without it git runs .git/hooks/ instead
  # and the gate is inert. A gate that looks installed and enforces nothing is worse than no
  # gate. (This is the same shape as the 2026-07-11 trio: config.yml existed but was
  # gitignored; the PATH export existed but only for interactive shells.)
  if [ -d "$REPO/.githooks" ]; then
    if [ "$(git -C "$REPO" config core.hooksPath)" = ".githooks" ]; then
      ok "pre-commit gate wired (doccheck)"
    else
      err "core.hooksPath not set — the pre-commit doccheck gate is INERT"
      fail=1
    fi
  fi

  # 4. Scaffold source is valid JSON (a broken copy breaks every new project).
  if python3 -c "import json; json.load(open('$TEMPLATES/settings.json'))" 2>/dev/null; then
    ok "scaffold settings.json valid"
  else
    err "scaffold settings.json invalid or missing"
    fail=1
  fi

  if [ "$fail" -ne 0 ]; then
    echo ""
    err "Verify FAILED — machine is NOT known-good. Fix the ✗ items above."
    exit 1
  fi
  ok "all hard checks passed — machine known-good"
}

main() {
  echo ""
  say "Tessera self-install"
  say "────────────────────"
  mkdir -p "$CLAUDE"
  install_skills
  install_dir commands
  install_dir hooks
  chmod +x "$CLAUDE/hooks/"* 2>/dev/null || true
  install_script_fallback
  install_scaffold_source
  write_marker
  install_git_hooks
  install_venv
  verify
  echo ""
  say "Done. Tessera is now self-hosting — no maggy repo required."
  say "Next: run /initialize-project in any project to scaffold it."
  echo ""
}

main "$@"
