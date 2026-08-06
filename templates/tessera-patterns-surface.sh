#!/usr/bin/env bash

# Surface the standing patterns at SessionStart — the lessons paid for more than once.
#
# WHY THIS IS ITS OWN SCRIPT, AND WHY IT TAKES A PART INDEX (2026-08-06).
#
# Claude Code caps hook output at 10,000 characters (code.claude.com/docs/en/hooks:
# "Hook output strings, including additionalContext, systemMessage, and plain stdout,
# are capped at 10,000 characters. Output that exceeds this limit is saved to a file
# and replaced with a preview and file path"). The preview is ~2KB.
#
# `tessera-watch-surface.sh` emitted the handoff pointer AND this block in one output.
# Measured 2026-08-06: 10,878 characters, 12 standing patterns emitted, ONE survived the
# preview.
#
# THE SPILL WAS INTERMITTENT, AND THAT IS THE INTERESTING PART (refuted a flat claim,
# `bin/tessera-verify`, same day). At HEAD with no observatory trigger firing the same
# script emits 9,880 characters — UNDER the cap. Decomposition: handoff 927 + patterns
# 8,950 + observatory 70, against ~1,001 for observatory in the measured run, where P3 and
# the G-a graduation were both red. So the cross-cutting lessons stopped arriving EXACTLY
# when the observatory had something to report: a quiet repo got all 12, a repo with fired
# triggers got one. Coupled, state-dependent, and invisible to any single measurement.
#
# doccheck's `standing-patterns-are-surfaced` was green throughout — it asserted the block
# existed and that the surfacer extracted it, both true, and could not see the harness drop
# 92% of it one layer later. The mechanism
# built to stop lessons riding model recall was delivering one lesson and leaving eleven
# to model recall. Standing pattern #1, aimed at the artifact that carries pattern #1 —
# which was the one pattern that still arrived.
#
# Splitting the block out is not enough on its own: alone it is 8,950 characters against a
# 10,000 cap, and pattern 12 is 2,378 of them — one added pattern re-breaks it silently,
# and silently is the whole complaint. Hence PARTS: each registered hook entry gets
# its own 10,000-character budget, and doccheck asserts every part is under 9,000 AND
# that the union of parts covers every pattern. Emission was never the property; ARRIVAL
# is. See docs/observatory.md → "11 of the 12 standing patterns never reach the model".
#
# Registered TWICE in .claude/settings.json (--part 1 --of 2, --part 2 --of 2). If the
# block grows past what 2 parts can carry, doccheck `standing-patterns-fit-the-cap` fails
# and the fix is to add a part — it cannot go quiet.

_HOOKDIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd)
degraded() {
  for _c in "$_HOOKDIR/../../bin/tessera-degraded" "$_HOOKDIR/../../scripts/tessera-degraded"; do
    if [ -x "$_c" ]; then "$_c" "$@" >/dev/null 2>&1 || true; return 0; fi
  done
  command -v tessera-degraded >/dev/null 2>&1 && tessera-degraded "$@" >/dev/null 2>&1
  return 0
}

# Same anchoring contract as tessera-watch-surface.sh: hook commands inherit the SESSION
# cwd, which may be another repo. Guarded so the ~/.claude/templates global copy, where
# ../.. is $HOME, does not cd every downstream hook to $HOME.
case "$(dirname "$0")" in
  */.claude/scripts) cd "$(dirname "$0")/../.." 2>/dev/null || exit 0 ;;
esac

PART=1
OF=1
while [ $# -gt 0 ]; do
  case "$1" in
    --part) PART=$2; shift 2 ;;
    --of)   OF=$2;   shift 2 ;;
    *)      shift ;;
  esac
done

HANDOFF="_project_specs/todos/active.md"
[ -f "$HANDOFF" ] || exit 0
grep -q '^## Handoff — pick up here' "$HANDOFF" || exit 0

# Extraction is identical to the one this replaced: scoped to the FIRST handoff block so a
# stale copy further down cannot win, with the italic load-bearing note skipped
# STRUCTURALLY (`*(` → `)*`) rather than by enumerating its first words, which leaked the
# moment the paragraph was re-wrapped.
#
# Then greedy-packed into OF parts on PATTERN boundaries by cumulative size, and only part
# PART is printed. Splitting on a boundary matters: half a lesson is worse than none,
# because it reads as complete.
out=$(awk -v part="$PART" -v of="$OF" '
    /^## Handoff — pick up here/ { blk=1; next }
    blk && /^## /                { exit }
    blk && /^### Standing patterns/ { want=1; next }
    blk && want && /^### /       { want=0 }
    blk && want && /\*\(/        { skip=1 }
    blk && want && skip          { if (/\)\*/) skip=0; next }
    blk && want {
        # Line truncation is the `cut -c1-116` BELOW, not substr() here. awk substr() on
        # macOS counts BYTES where `cut -c` counts CHARACTERS, and this block is full of
        # em-dashes — substr(1,116) can sever one mid-sequence. Both produce identical
        # output today; `cut` is kept because it is what the original pipeline used and it
        # cannot corrupt a multi-byte character. Precaution, not a measured regression.
        if ($0 ~ /^[0-9]+\. \*\*/) n++             # a new pattern starts here
        idx = (n ? n : 0)                          # 0 = preamble before pattern 1
        buf[idx] = buf[idx] $0 "\n"
        len[idx] += length($0) + 1
        if (idx > max) max = idx
        total += length($0) + 1
    }
    END {
        if (max == 0) exit 0
        target = total / of
        p = 1; run = 0
        for (i = 0; i <= max; i++) {
            # Assign greedily, but never open a part we have no room left to fill:
            # the last part takes everything remaining, so nothing can fall off the end.
            if (p < of && run > 0 && run + len[i] > target) { p++; run = 0 }
            owner[i] = p
            run += len[i]
        }
        for (i = 0; i <= max; i++) if (owner[i] == part) printf "%s", buf[i]
    }
' "$HANDOFF" | cut -c1-116)

if [ -z "$out" ]; then
    # Fail LOUD. A silent surfacer is indistinguishable from one with nothing to say —
    # which is the exact failure this whole file exists to correct.
    [ "$PART" -eq 1 ] || exit 0
    echo "  ⚠️  NO STANDING-PATTERNS BLOCK IN THE HANDOFF — the cross-cutting lessons"
    echo "     are not being surfaced. Restore '### Standing patterns' in active.md."
    degraded --component standing-patterns --reason block-missing \
      --detail "no '### Standing patterns' in the newest handoff block; lessons are not surfaced"
    exit 0
fi

# Each part is its own hook output with its own header, so the delivered form is NOT
# byte-identical to the old single block and cannot be: `bin/tessera-verify` measured the
# difference at exactly one blank line at the seam (part 1's trailing echo) plus the per-part
# headers. Pattern text, order and count are unchanged — that is the property that matters.
if [ "$OF" -gt 1 ]; then
    echo "=== STANDING PATTERNS ($PART/$OF — paid for more than once, do not re-learn) ==="
else
    echo "=== STANDING PATTERNS (paid for more than once — do not re-learn) ==="
fi
echo "$out"
echo ""
exit 0
