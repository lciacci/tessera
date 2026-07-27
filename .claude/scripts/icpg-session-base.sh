#!/bin/bash
# iCPG SessionStart Hook — stamp the commit this session starts from.
#
# `icpg record` diffs against a base to decide which symbols a session touched.
# HEAD-relative bases (HEAD, HEAD~1) are relative to GIT's state, not the
# SESSION's, and they are wrong in three ordinary cases:
#   - the session makes several commits  -> HEAD~1 catches only the last
#   - a rebase or merge lands            -> HEAD~1 is a different lineage, and
#                                           conflict-resolution files get
#                                           attributed to the session's intent
#   - a branch switch                    -> a different tree entirely
# A false intent link is worse than none: drift then measures against fiction.
# So the anchor is the SHA at session start, written here, read by
# icpg-stop-record.sh.

# Anchor to the project root: hook commands inherit the SESSION cwd, which may be
# another repo entirely. $0 is a fact this script always has.
case "$(dirname "$0")" in
  */.claude/scripts) cd "$(dirname "$0")/../.." 2>/dev/null || exit 0 ;;
esac
# Guarded: this script is ALSO installed to ~/.claude/templates/ as the ADR-0004
# global fallback, where ../.. is $HOME, not a repo. Anchoring unconditionally
# would cd every downstream hook to $HOME and silently no-op it.

# QUIET: no .icpg/ means this project does not use iCPG. Genuinely nothing to do.
[ -d .icpg ] || exit 0

# Read the hook payload BEFORE anything else consumes stdin — `source` below
# distinguishes a new session from a mid-session compaction, and without it this
# hook re-anchors the base on every compaction.
#
# `[ -t 0 ]` guard added by review: bare `cat` reads to EOF, and `2>/dev/null ||
# true` suppresses errors, not BLOCKING. Run from a terminal — which is how these
# hooks get debugged and how a chaos probe would exercise this one — the previous
# form hung forever with no output. A hook that wedges is worse than one that
# fails, because a wedge looks like the session is working.
INPUT=""
[ -t 0 ] || INPUT=$(cat 2>/dev/null || true)

degraded() {
  for d in bin scripts; do
    r="${CLAUDE_PROJECT_DIR:-.}/$d/tessera-degraded"
    [ -x "$r" ] && { "$r" "$@" >/dev/null 2>&1 || true; return 0; }
  done
  command -v tessera-degraded >/dev/null 2>&1 && tessera-degraded "$@" >/dev/null 2>&1
  return 0
}

# No git, or no commits yet. LOUD: .icpg/ exists, so recording was expected to
# work this session and now cannot. A silent exit reads as "nothing changed".
if ! BASE=$(git rev-parse HEAD 2>/dev/null); then
  degraded --component icpg-session-base --reason no-git-head \
    --detail "git rev-parse HEAD failed; icpg-stop-record has no base and will record nothing this session"
  exit 0
fi

# A COMPACTION MUST NOT RE-ANCHOR THE BASE (found by review, 2026-07-27, hours
# after this hook was written). SessionStart carries NO matcher, so it fires on
# `startup`, `resume` AND `compact` — and compaction happens MID-session. The first
# version overwrote unconditionally, with a comment claiming "per session on
# purpose". It was per EVENT, not per session: a compaction would re-anchor to the
# current HEAD and every symbol touched before it would never be attributed to the
# intent that was open the whole time. Silent, and worse on long sessions — exactly
# the ones where losing the record costs most.
#
# RE-ANCHOR ONLY ON `startup`. Everything else keeps the existing base.
#
# The first fix guarded `compact` alone and re-anchored on `resume`, reasoning that
# a resume is "a genuinely new session". Review refuted that: a resume after an
# abnormal end (terminal closed, crash, kill mid-turn) is exactly the case where
# the per-turn Stop recorder never ran for the last turn — so re-anchoring there
# destroys the record of the very work the resume exists to continue. Same loss,
# same silence, same permanence as the compaction bug.
#
# Inverted to a WHITELIST rather than a blacklist of known-bad sources: an unknown
# or future source now preserves instead of destroying.
SOURCE=""
if command -v jq >/dev/null 2>&1; then
    SOURCE=$(printf '%s' "$INPUT" | jq -r '.source // empty' 2>/dev/null)
fi
# jq absent, or present and silent: scan the raw payload. `jq` was a NEW hard
# dependency this hook did not previously have, and losing it silently reinstated
# the exact defect the guard was written to prevent.
if [ -z "$SOURCE" ]; then
    case "$INPUT" in
        *'"source"'*'"startup"'*) SOURCE=startup ;;
        *'"source"'*'"resume"'*)  SOURCE=resume ;;
        *'"source"'*'"compact"'*) SOURCE=compact ;;
    esac
fi

if [ -z "$SOURCE" ] && [ -s .icpg/.session-base ]; then
    # CANNOT TELL, AND THERE IS SOMETHING TO LOSE. Preserve, and say so.
    #
    # This repo has MEASURED its harness sending an empty `{}` payload on another
    # event (CLAUDE.md: "no trigger, no session_id, nothing"), so an absent
    # `source` is a real state, not a hypothetical. Preserving over-attributes at
    # worst — `record` diffs from an older base and links MORE symbols than this
    # session touched, which is visible in the count. Re-anchoring under-attributes
    # SILENTLY and unrecoverably. Between a loud wrong number and a quiet missing
    # one, take the loud one.
    degraded --component icpg-session-base --reason source-unknown \
      --detail "SessionStart payload carried no readable .source (jq missing or empty payload); preserving the existing base rather than re-anchoring, so this session may over-attribute rather than lose symbols"
    exit 0
fi

# A known non-startup source with a base already stamped: same session continuing.
if [ -n "$SOURCE" ] && [ "$SOURCE" != "startup" ] && [ -s .icpg/.session-base ]; then
    exit 0
fi

printf '%s\n' "$BASE" > .icpg/.session-base 2>/dev/null || \
  degraded --component icpg-session-base --reason base-unwritable \
    --detail ".icpg/.session-base could not be written; auto-recording is disabled this session"

exit 0
