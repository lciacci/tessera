#!/bin/bash
# iCPG PreToolUse Hook — injects intent context before Edit/Write operations.
#
# Shows the agent: what intents exist for this file, what invariants apply,
# and the risk profile of symbols being modified.
#
# Install: add to .claude/settings.json under hooks.PreToolUse
# Timeout: 3 seconds max — never blocks

# Skip if icpg not installed or no DB

# ── Toolchain interpreter: a PATH, never a NAME. (F-001) ──────────────────────────────────
# This hook used bare `python3`. With sys.path/PYTHONPATH pointed at scripts/, ANY interpreter
# imports mnemos/icpg straight from source — so that did NOT fail, it SILENTLY SUCCEEDED on
# whatever Homebrew currently owns the `python3` name. The original F-001 failed silently
# (import error → no-op); this one *worked*, on an interpreter brew can re-point or delete.
# A silent success is strictly harder to detect than a silent failure.
# No toolchain → this hook goes QUIET. tessera-watch P9 makes that visible.
TOOLCHAIN_PY=""
if [ -x ".venv/bin/python" ]; then
    TOOLCHAIN_PY=".venv/bin/python"
elif command -v mnemos >/dev/null 2>&1; then
    TOOLCHAIN_PY="$(sed -n '1s/^#!//p' "$(command -v mnemos)" 2>/dev/null | awk '{print $1}')"
fi
[ -n "$TOOLCHAIN_PY" ] && [ -x "$TOOLCHAIN_PY" ] || exit 0
# ──────────────────────────────────────────────────────────────────────────────────────────
if ! command -v icpg &>/dev/null && ! "$TOOLCHAIN_PY" -m icpg --version &>/dev/null 2>&1; then
    exit 0
fi

if [ ! -f ".icpg/reason.db" ]; then
    exit 0
fi

# Extract file path from tool input
# Claude Code passes tool input as JSON via stdin for PreToolUse hooks
FILE_PATH=""
if [ -n "$CLAUDE_TOOL_INPUT" ]; then
    FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | "$TOOLCHAIN_PY" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', data.get('path', '')))
except:
    pass
")
fi

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Run icpg binary or module
ICPG_CMD="icpg"
if ! command -v icpg &>/dev/null; then
    ICPG_CMD=""$TOOLCHAIN_PY" -m icpg"
fi

# Query context, constraints, and drift (file-scoped fast check)
CONTEXT=$($ICPG_CMD query context "$FILE_PATH")
CONSTRAINTS=$($ICPG_CMD query constraints "$FILE_PATH")
DRIFT=$($ICPG_CMD drift file "$FILE_PATH")

# Only output if we have something
if [ -n "$CONTEXT" ] || [ -n "$CONSTRAINTS" ] || [ -n "$DRIFT" ]; then
    echo "═══ iCPG CONTEXT ═══"
    [ -n "$CONTEXT" ] && echo "$CONTEXT"
    [ -n "$CONSTRAINTS" ] && echo -e "\n$CONSTRAINTS"
    [ -n "$DRIFT" ] && echo -e "\n$DRIFT"
    echo "PRESERVE function signatures unless your task requires changing them."
    echo "═══════════════════"
fi

exit 0
