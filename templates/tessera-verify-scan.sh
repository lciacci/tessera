#!/usr/bin/env bash
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

PROJECT_DIR="${CWD:-$PWD}"
SCAN="$PROJECT_DIR/scripts/verify/scan.py"
[ -f "$SCAN" ] || broken "scan missing at $SCAN"

cd "$PROJECT_DIR" 2>/dev/null || broken "cannot cd to $PROJECT_DIR"

# scan.py is stdlib-only by design, so any python3 works (doccheck enforces the
# stdlib-only split). scan.py itself exits 1 both when firing and when broken;
# either way the model must see it.
python3 "$SCAN" "$TRANSCRIPT_PATH" "$SESSION_ID" || exit 2
exit 0
