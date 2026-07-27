#!/bin/bash
# iCPG PreToolUse Hook — injects intent context before tool use.
#
# Shows the agent: what ReasonNodes exist for affected files,
# what invariants apply, and drift status.
# Works with icpg-record-intent hook — intents are auto-created on first edit.
#
# Install: add to .claude/settings.json under hooks.PreToolUse
# Timeout: 2 seconds — never blocks


# ── Toolchain interpreter: a PATH, never a NAME. (F-001) ──────────────────────────────────
# This hook used bare `python3`. With sys.path/PYTHONPATH pointed at scripts/, ANY interpreter
# imports mnemos/icpg straight from source — so that did NOT fail, it SILENTLY SUCCEEDED on
# whatever Homebrew currently owns the `python3` name. The original F-001 failed silently
# (import error → no-op); this one *worked*, on an interpreter brew can re-point or delete.
# A silent success is strictly harder to detect than a silent failure.
# No toolchain → this hook goes QUIET. tessera-watch P9 makes that visible.

# Anchor to the project root: hook commands inherit the SESSION cwd, which may be
# another repo entirely (2026-07-24 — a cd into a downstream split this repo's gate
# log 4/2 and silently no-op'd twelve hooks). $0 is a fact this script always has.
# Every path below is relative (.venv, .icpg), so from a foreign cwd this hook finds
# no toolchain and exits 0 — indistinguishable from "no intents for this file".
case "$(dirname "$0")" in
  */.claude/scripts) cd "$(dirname "$0")/../.." 2>/dev/null || exit 0 ;;
esac
# Guarded, and the guard is load-bearing: this script is ALSO installed to
# ~/.claude/templates/ as the ADR-0004 global fallback, where ../.. is $HOME, not a
# repo. Anchoring unconditionally would cd every downstream hook to $HOME and silently
# no-op it — a fix that ships the bug it fixes.

TOOLCHAIN_PY=""
if [ -x ".venv/bin/python" ]; then
    TOOLCHAIN_PY=".venv/bin/python"
elif command -v mnemos >/dev/null 2>&1; then
    TOOLCHAIN_PY="$(sed -n '1s/^#!//p' "$(command -v mnemos)" 2>/dev/null | awk '{print $1}')"
fi
if [ -z "$TOOLCHAIN_PY" ] || [ ! -x "$TOOLCHAIN_PY" ]; then
    # COULD NOT DO ITS JOB — say so. A silent exit 0 here reads as "no intents", which is the
    # fail-open shape spec 11 exists to catch.
    for d in bin scripts; do
        r="${CLAUDE_PROJECT_DIR:-.}/$d/tessera-degraded"
        [ -x "$r" ] && exec "$r" --component icpg-inject-context --reason toolchain-unavailable \
            --detail "no .venv/bin/python and no mnemos on PATH; iCPG intent context is not being injected"
    done
    exit 0
fi
# ──────────────────────────────────────────────────────────────────────────────────────────
INPUT=$(cat 2>/dev/null || true)
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty' 2>/dev/null || echo "")

# Check icpg available
ICPG_CMD=""
if command -v icpg &>/dev/null; then
  ICPG_CMD="icpg"
elif "$TOOLCHAIN_PY" -c "import icpg" 2>/dev/null; then
  ICPG_CMD=""$TOOLCHAIN_PY" -m icpg"
else
  exit 0
fi

# Extract file path from tool input (supports multiple formats)
FILE_PATH=""
if [ -n "$TOOL_INPUT" ]; then
  FILE_PATH=$(echo "$TOOL_INPUT" | "$TOOLCHAIN_PY" -c "
import sys, json
try:
    d = json.loads(sys.stdin.read()) if hasattr(sys.stdin, 'read') else json.loads(sys.stdin)
    print(d.get('file_path', d.get('path', '')))
except:
    pass" 2>/dev/null | head -1)
fi

[ -z "$FILE_PATH" ] && exit 0
[ ! -f "$FILE_PATH" ] && exit 0

# Query existing intents
INTENTS=$($ICPG_CMD query context "$FILE_PATH" 2>/dev/null)
if [ -z "$INTENTS" ]; then
  exit 0
fi

# Build context message.
# REAL newlines via $'\n', not the literal backslash-n the inherited version used: bash does not
# interpret "\n" inside a plain assignment, so the injected block reached the model as one line
# with visible \n escapes. It "worked" — valid JSON, hook exit 0, content present — while being
# markedly harder to read. The channel was right and the payload was mangled.
CTX="iCPG Intent Context for ${FILE_PATH}:"
CTX="$CTX"$'\n'"${INTENTS}"

# Also check for drift
DRIFT=$($ICPG_CMD drift file "$FILE_PATH" 2>/dev/null)
if [ -n "$DRIFT" ] && [ "$DRIFT" != "No drift detected" ]; then
  CTX="$CTX"$'\n\n'"⚠️ DRIFT: ${DRIFT}"
fi

# Inject as additional context
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": $(echo "$CTX" | "$TOOLCHAIN_PY" -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo "\"$CTX\"")
  }
}
EOF
exit 0
