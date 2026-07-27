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
# Claude Code Stop hook: verify-scan backstop (spec 12).
#
# If this session touched a safety path AND claimed done/fixed AND logged no
# verification event, exit 2 so the model must state its claims and run
# bin/tessera-verify (or record an auditable skip) before finishing.
#
# UNLIKE the other Tessera hooks, this one fails LOUD, not open (spec 12,
# ADR-0006 tier 4): an unverified safety change passing quietly is the exact
# failure class this hook exists to end. Every "cannot run" path below exits 2
# with a message instead of 0. The scan's per-session fire cap bounds the noise.
set -u

HOOK_INPUT=$(cat 2>/dev/null || true)

# Mid-continuation from a Stop hook: never re-fire into a loop. Checked with
# grep, not jq, so the loop guard survives even when jq is missing.
printf '%s' "$HOOK_INPUT" | grep -q '"stop_hook_active": *true' && exit 0

broken() {
    echo "VERIFY-SCAN BROKEN: $1" >&2
    echo "The verify backstop cannot run; an unverified safety change could pass silently." >&2
    echo "Verify manually (bin/tessera-verify) or fix the scan before finishing." >&2
    exit 2
}

command -v jq >/dev/null 2>&1 || broken "jq not found"
command -v python3 >/dev/null 2>&1 || broken "python3 not found"

SESSION_ID=$(printf '%s' "$HOOK_INPUT" | jq -r '.session_id // empty' 2>/dev/null)
TRANSCRIPT_PATH=$(printf '%s' "$HOOK_INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
CWD=$(printf '%s' "$HOOK_INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -z "$SESSION_ID" ] && broken "no session_id in hook input"
[ -z "$TRANSCRIPT_PATH" ] && broken "no transcript_path in hook input"

# Anchor to the PROJECT ROOT, not the session cwd: `.cwd` is the SESSION's working
# directory and any Bash `cd` moves it. Live case 2026-07-26 — `cd scripts` made the spend
# guard resolve scripts/scripts/spend/guard.py -> absent -> spend commands ALLOWED. Same
# root cause silenced 12 hooks on 07-24 and made gate/ratio.py report ZERO over ZERO.
# CLAUDE_PROJECT_DIR is preferred but is EMPTY in some invocations, so relying on it alone
# is a no-op fix. Pure parameter expansion — no dirname/sed, these hooks must survive a
# broken toolchain, which is precisely when they have to report. See ADR-0015 / observatory.
# Sets $_root. Returns via a VARIABLE, not stdout: a PreToolUse hook's bare stdout is a
# real channel, and doccheck's pretooluse-hooks-reach-the-model rightly cannot tell a
# function's `printf` from the hook writing to it. Also saves a subshell fork per call.
_anchor_root() {
    _d="$1"; _root="$1"      # fall back to the input; never yield empty
    while [ -n "$_d" ] && [ "$_d" != "/" ]; do
        if [ -e "$_d/.git" ] || [ -f "$_d/.tessera/project.yml" ]; then _root="$_d"; return 0; fi
        case "$_d" in */*) _d="${_d%/*}" ;; *) break ;; esac
    done
}
_anchor_root "${CLAUDE_PROJECT_DIR:-${CWD:-$PWD}}"; PROJECT_DIR="$_root"
SCAN="$PROJECT_DIR/scripts/verify/scan.py"
[ -f "$SCAN" ] || broken "scan missing at $SCAN"

cd "$PROJECT_DIR" 2>/dev/null || broken "cannot cd to $PROJECT_DIR"

# scan.py is stdlib-only by design, so any python3 works (doccheck enforces the
# stdlib-only split). scan.py itself exits 1 both when firing and when broken;
# either way the model must see it.
python3 "$SCAN" "$TRANSCRIPT_PATH" "$SESSION_ID" || exit 2
exit 0
