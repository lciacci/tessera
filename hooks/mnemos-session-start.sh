#!/bin/bash
# Mnemos SessionStart hook — inject last checkpoint on resume/clear/compact.
# Also sets usage summary baseline for per-session decision counting.
# No set -euo pipefail: hook scripts must be defensive, not strict.

# Set usage summary baseline (decisions before this session started)

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
LOG="$HOME/.claude/routing-log.jsonl"
TODAY=$(date -u +%Y-%m-%d)
if [ -f "$LOG" ]; then
  grep -c "$TODAY" "$LOG" 2>/dev/null > "$HOME/.claude/usage-session-baseline" || true
fi

INPUT=$(cat 2>/dev/null || true)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || true)
SESSION_TYPE=$(echo "$INPUT" | jq -r '.type // empty' 2>/dev/null || true)

# Fallback: if jq failed (non-JSON input), extract from raw text
if [ -z "$CWD" ]; then
  CWD="."
fi
if [ -z "$SESSION_TYPE" ]; then
  case "${INPUT:-}" in
    *clear*)  SESSION_TYPE="clear" ;;
    *compact*) SESSION_TYPE="compact" ;;
    *resume*) SESSION_TYPE="resume" ;;
    *startup*) SESSION_TYPE="startup" ;;
    *) SESSION_TYPE="unknown" ;;
  esac
fi

if [ ! -d "$CWD/.mnemos" ]; then
  exit 0
fi

# Get checkpoint from mnemos
RESULT=$(echo "{\"cwd\":\"$CWD\"}" | \
  "$TOOLCHAIN_PY" -m mnemos _hook session_start 2>/dev/null || echo "")

if [ -z "$RESULT" ]; then
  exit 0
fi

# For clear/compact: append auto-announce instruction via Python
# For resume/startup: pass through unchanged
if [ "$SESSION_TYPE" = "clear" ] || [ "$SESSION_TYPE" = "compact" ]; then
  "$TOOLCHAIN_PY" -c "
import json, sys

session_type = sys.argv[1]
raw = sys.argv[2]

try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)

ctx = data.get('hookSpecificOutput', {}).get('additionalContext', '')
if not ctx:
    sys.exit(0)

announce = (
    '\n\nAUTO-ANNOUNCE: Context was just restored after /'
    + session_type
    + '. You MUST proactively tell the user what they were working on '
    'based on the checkpoint above. Start your response with a brief '
    'summary: goal, what was completed, current constraints, and '
    'immediate next steps. Do NOT wait for the user to ask.'
)
data['hookSpecificOutput']['additionalContext'] = ctx + announce
json.dump(data, sys.stdout)
" "$SESSION_TYPE" "$RESULT" 2>/dev/null || echo "$RESULT"
else
  echo "$RESULT"
fi

exit 0
