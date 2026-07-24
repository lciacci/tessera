#!/usr/bin/env bash

# Anchor to the project root: hook commands inherit the SESSION cwd, which may be
# another repo entirely (2026-07-24 — a cd into a downstream split this repo's gate
# log 4/2 and silently no-op'd twelve hooks). $0 is a fact this script always has.
case "$(dirname "$0")" in
  */.claude/scripts) cd "$(dirname "$0")/../.." 2>/dev/null || exit 0 ;;
esac
# Guarded: this script is ALSO installed to ~/.claude/templates/ as the ADR-0004
# global fallback, where ../.. is $HOME, not a repo. Anchoring there would cd every
# downstream hook to $HOME and silently no-op it. In the global tier the session cwd
# IS the right signal — that copy has no repo of its own.
# Surface the downstream findings backlog at session start — no human recall.
# Silent when nothing is open; prints the backlog only when tessera-findings
# reports open items (exit 1). Fails open on any error.
[ -x "bin/tessera-findings" ] || exit 0
out=$(bin/tessera-findings 2>/dev/null)
[ $? -eq 1 ] || exit 0
echo "=== TESSERA FINDINGS BACKLOG (downstream → framework, un-transferred) ==="
echo "$out"
exit 0
