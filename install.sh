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

say() { printf "  %s\n" "$1"; }

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
  echo ""
  say "Done. Tessera is now self-hosting — no maggy repo required."
  say "Next: run /initialize-project in any project to scaffold it."
  echo ""
}

main "$@"
