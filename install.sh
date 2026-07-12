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
  "$REPO/scripts/install-skills.sh" "$CLAUDE/skills" "$REPO/skills" >/dev/null
  say "skills      -> $CLAUDE/skills"
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

# Turn silent-success into loud-failure. Hard checks (✗) abort; soft checks (!)
# warn only. Audited against the four new-machine bootstrap steps (observatory:
# "New-machine bootstrap is tribal knowledge"). Does NOT install mnemos — that
# is docs/install.md Step 2 (maggy-source + flat-layout dependency) — but it
# verifies mnemos is healthy so a dead shebang (F-001) fails loud here.
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
  if ! command -v tessera-escalate >/dev/null 2>&1; then
    err "tessera/bin not on PATH — add: export PATH=\"\$HOME/Claude/tessera/bin:\$PATH\""
    fail=1
  fi

  # 2. mnemos on PATH, shebang resolves, runs (F-001 — the silent hook killer).
  if ! command -v mnemos >/dev/null 2>&1; then
    err "mnemos not on PATH — see docs/install.md Step 2"
    fail=1
  else
    local interp
    interp=$(head -1 "$(command -v mnemos)"); interp=${interp#\#!}; interp=${interp%% *}
    if [ -n "$interp" ] && [ ! -x "$interp" ]; then
      err "mnemos shebang dead ($interp missing, F-001) — reinstall via /opt/homebrew/bin/pip3.13"
      fail=1
    elif ! mnemos --version >/dev/null 2>&1; then
      err "mnemos --version failed (bad interpreter?) — see docs/install.md Step 2"
      fail=1
    else
      ok "mnemos healthy ($(mnemos --version 2>/dev/null))"
    fi
  fi

  # 3. Routing deps — warn only; tier-classify-hook fails open to Sonnet.
  if curl -s --connect-timeout 2 "$OLLAMA_BASE/api/tags" 2>/dev/null | grep -q "qwen2.5-coder"; then
    ok "routing: ollama up, qwen model present"
  else
    warn "ollama/qwen2.5-coder absent — routing fails open to Sonnet (ollama pull qwen2.5-coder:3b)"
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
  verify
  echo ""
  say "Done. Tessera is now self-hosting — no maggy repo required."
  say "Next: run /initialize-project in any project to scaffold it."
  echo ""
}

main "$@"
