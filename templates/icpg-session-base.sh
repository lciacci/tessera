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

# Overwrite per session on purpose: the base is "where THIS session started",
# not the oldest unrecorded point. A session that records mid-way and continues
# would otherwise re-record everything from the original base on every Stop.
printf '%s\n' "$BASE" > .icpg/.session-base 2>/dev/null || \
  degraded --component icpg-session-base --reason base-unwritable \
    --detail ".icpg/.session-base could not be written; auto-recording is disabled this session"

exit 0
