#!/bin/bash
# iCPG Stop Hook Extension — auto-records symbols after implementation.
#
# Reads .icpg/.current-intent to know which ReasonNode is active.
# If set, records symbols from git diff to that intent.
#
# Chain this AFTER tdd-loop-check.sh in the Stop hook:
#   tdd-loop-check runs first → if tests pass → this records symbols

# Skip if no active intent

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
CURRENT_INTENT=$(cat .icpg/.current-intent 2>/dev/null)
if [ -z "$CURRENT_INTENT" ]; then
    exit 0
fi

# Skip if icpg not available
ICPG_CMD=""
if command -v icpg &>/dev/null; then
    ICPG_CMD="icpg"
elif "$TOOLCHAIN_PY" -m icpg --version &>/dev/null 2>&1; then
    ICPG_CMD=""$TOOLCHAIN_PY" -m icpg"
else
    exit 0
fi

# Record symbols from current diff
OUTPUT=$($ICPG_CMD record --reason "$CURRENT_INTENT" --base main 2>&1)
if [ $? -eq 0 ]; then
    echo "iCPG: $OUTPUT" >&2
fi

exit 0
