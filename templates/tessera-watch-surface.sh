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

HANDOFF="_project_specs/todos/active.md"

if [ -f "$HANDOFF" ]; then
    heading=$(grep -m1 '^## Handoff — pick up here' "$HANDOFF")
    if [ -n "$heading" ]; then
        echo "=== TESSERA HANDOFF ==="
        echo "${heading#\#\# }"
        echo "  → read the top section of $HANDOFF, then run bin/tessera-watch"
        # The priority list, so the next session knows the shape without reading 344 lines.
        awk '/^## Next session/{f=1;next} f&&/^## /{exit} f&&/^[0-9]+\. /{print "  " $0}' \
            "$HANDOFF" | cut -c1-110
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
