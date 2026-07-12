#!/usr/bin/env bash
# Surface, at session start, the two things a fresh session cannot afford to miss:
#   1. the handoff — where to pick up
#   2. any Observatory trigger past threshold
# No human recall, no model recall (principle #17). Fails open on any error.
#
# The handoff pointer was added 2026-07-11. Until then NOTHING mechanically pointed a new
# session at `_project_specs/todos/active.md` — it rode base-skill line 475 ("Check
# active.md"), i.e. pure model recall, on the single highest-value artifact in the repo: the
# doc that tells tomorrow what to do. That is the #17 violation we spent the day closing
# everywhere else, sitting on the handoff itself. It also explains how active.md was able to
# rot into three competing "pick up here" markers unnoticed — nothing ever made anyone look.
#
# Deliberately a POINTER, not a dump: printing 344 lines every session buys a context tax and
# teaches the model to skim. The date is included so a stale handoff is visible as stale.

# ── IT STITCHED THE NEW HEADING ONTO THE OLD PRIORITIES. Found 2026-07-12. ────────────────
#
# The heading came from `grep -m1` (the FIRST handoff block — correct). The priority list came
# from an awk that scanned the WHOLE FILE for `^## Next session` — so when the newest handoff
# didn't happen to use that exact heading, awk fell through to the PREVIOUS handoff's section,
# further down, and printed ITS priorities.
#
# The result was perfectly coherent: today's title over yesterday's todo list. A fresh session
# would have been told to go do "Spec 06 (BLOCKS unsupervised work)" and "the venv (P9 is
# firing)" — the two things that had just been finished. Neither half was wrong on its own.
#
# This is the fail-open pattern sitting on the one artifact that tells tomorrow what to do:
# **it did not break, it produced something plausible.** Nothing could have told us.
#
# Two fixes, and the second is the rule this repo just wrote for itself:
#   1. Extraction is SCOPED to the first handoff block. It cannot reach a previous handoff.
#   2. If the block has no priority list, SAY SO LOUDLY. A surfacer that silently prints
#      nothing is indistinguishable from a surfacer that has nothing to print — and that is
#      exactly the class of failure this session spent 90 minutes on.
#      (docs/observatory.md → "Fail-open everywhere": a mechanism that fails open needs a
#       paired signal that fails loud.)

HANDOFF="_project_specs/todos/active.md"

if [ -f "$HANDOFF" ]; then
    heading=$(grep -m1 '^## Handoff — pick up here' "$HANDOFF")
    if [ -n "$heading" ]; then
        echo "=== TESSERA HANDOFF ==="
        echo "${heading#\#\# }"
        echo "  → read the top section of $HANDOFF, then run bin/tessera-watch"

        # Scoped to the FIRST handoff block only: start at its heading, stop at the next
        # top-level `## ` (a `### ` subheading does not match, so it stays inside the block).
        items=$(awk '
            /^## Handoff — pick up here/ { blk=1; next }
            blk && /^## /               { exit }
            blk && /^#{3,} .*([Pp]ick up|[Nn]ext|[Pp]riorit)/ { want=1; next }
            blk && want && /^#{3,} /    { want=0 }
            blk && want && /^[0-9]+\. / { print "  " $0 }
        ' "$HANDOFF" | cut -c1-110)

        if [ -n "$items" ]; then
            echo "$items"
        else
            echo "  ⚠️  THE HANDOFF HAS NO PRIORITY LIST — read it directly, do not guess."
            echo "     (This line is deliberate: a silent surfacer is indistinguishable from a"
            echo "      working one. See docs/observatory.md → 'Fail-open everywhere'.)"
        fi
        echo ""
    fi
fi

# Observatory triggers. Silent when nothing fires; --log appends every run to the fire-log
# (which G-a reads), so the log stays honest whether or not anything printed.
[ -x "bin/tessera-watch" ] || exit 0
out=$(bin/tessera-watch --log 2>/dev/null)
[ $? -eq 1 ] || exit 0
echo "=== OBSERVATORY WATCH (silent+checkable triggers past threshold) ==="
echo "$out"
exit 0
