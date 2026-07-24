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
# Claude Code Stop hook: gate-scan backstop (principle #17).
#
# The surface-decisions *record* (scripts/gate/emit.py) rides model recall and
# misses ~85% of gates under real work. This makes the harness the trigger: count
# gate-shaped turns in the transcript, diff against the session's gate log, and
# exit 2 on a gap so the model must adjudicate before it can finish.
#
# Stdin: JSON with session_id, transcript_path, cwd, stop_hook_active.
# Exit 0 = quiet. Exit 2 = stderr fed back to the model, turn continues.
#
# Fails open on every error path — a backstop must never wedge a session.
set -u

HOOK_INPUT=$(cat 2>/dev/null || true)
[ -z "$HOOK_INPUT" ] && exit 0

command -v jq >/dev/null 2>&1 || exit 0

# Already mid-continuation from a Stop hook: never re-fire into a loop.
ACTIVE=$(printf '%s' "$HOOK_INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)
[ "$ACTIVE" = "true" ] && exit 0

SESSION_ID=$(printf '%s' "$HOOK_INPUT" | jq -r '.session_id // empty' 2>/dev/null)
TRANSCRIPT_PATH=$(printf '%s' "$HOOK_INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
CWD=$(printf '%s' "$HOOK_INPUT" | jq -r '.cwd // empty' 2>/dev/null)

[ -z "$SESSION_ID" ] && exit 0
[ -z "$TRANSCRIPT_PATH" ] && exit 0

PROJECT_DIR="${CWD:-$PWD}"
SCAN="$PROJECT_DIR/scripts/gate/scan.py"
[ -f "$SCAN" ] || exit 0

# scan.py is stdlib-only, so any python3 works (no mnemos-style interpreter pin
# needed — the F-003 bare-python3 trap only bites hooks importing a package).
command -v python3 >/dev/null 2>&1 || exit 0

cd "$PROJECT_DIR" 2>/dev/null || exit 0
python3 "$SCAN" "$TRANSCRIPT_PATH" "$SESSION_ID" || exit 2
exit 0
