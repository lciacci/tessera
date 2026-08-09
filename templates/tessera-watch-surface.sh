#!/usr/bin/env bash

# Spec 11 / A5b: report "I could not do my job" instead of exiting 0 into the dark.
# Resolved BEFORE the anchoring cd so $0-relative resolution cannot be broken by it.
# Inlined rather than sourced: a shared lib is one more file that can go missing on the
# very path that exists to report missing files (pattern #1).
_HOOKDIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd)
degraded() {
  for _c in "$_HOOKDIR/../../bin/tessera-degraded" "$_HOOKDIR/../../scripts/tessera-degraded"; do
    if [ -x "$_c" ]; then "$_c" "$@" >/dev/null 2>&1 || true; return 0; fi
  done
  command -v tessera-degraded >/dev/null 2>&1 && tessera-degraded "$@" >/dev/null 2>&1
  return 0
}

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

        # The standing patterns USED TO BE PRINTED HERE, and that is why 11 of 12 of them
        # never reached the model (2026-08-06). Claude Code caps hook output at 10,000
        # characters; this script emitted 10,878 and the harness replaced everything past
        # ~2KB with a file path. doccheck was green throughout — it asserted the block was
        # extracted, which was true, and could not see the truncation one layer later.
        # Emission was never the property; ARRIVAL is.
        #
        # They now live in `tessera-patterns-surface.sh`, registered TWICE in settings.json
        # so each part gets its own 10,000-character budget, and guarded by doccheck's
        # `standing-patterns-fit-the-cap`, which runs the parts and measures what they
        # actually emit. Do not move them back into this output "for cohesion" — the
        # cohesion is what broke them.
        # See docs/observatory.md → "11 of the 12 standing patterns never reach the model".
    fi
fi

# Observatory triggers. Silent when nothing fires; --log appends every run to the fire-log
# (which G-a reads), so the log stays honest whether or not anything printed.
# A5b (2026-07-27): these two lines used to be bare `|| exit 0`, and the audit's probes
# proved what that meant — DELETE `bin/tessera-watch`, or make it crash, and SessionStart
# prints a perfectly normal handoff and says NOTHING. Every predicate goes quiet at once
# (P3, P4, P9, P13, P14, P15), and the thing that would tell you is the thing that broke.
# Standing pattern #1 in its purest form, in the repo's own watcher.
#
# The settings.json trailing branch cannot cover this: it reports THIS SCRIPT missing, not
# the runner this script calls.
if [ ! -x "bin/tessera-watch" ]; then
  degraded --component tessera-watch --reason runner-missing \
    --detail "bin/tessera-watch is absent or not executable; NO observatory predicate can fire"
  exit 0
fi
out=$(bin/tessera-watch --log 2>/dev/null)
rc=$?
# rc 1 = something fired, 0 = nothing fired (correct silence). Anything else is a CRASH,
# and conflating it with 0 is how a broken watcher reads as a clean session.
if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
  degraded --component tessera-watch --reason runner-crashed \
    --detail "bin/tessera-watch exited $rc; at least one predicate crashed or the run failed outright — this session's observatory coverage is INCOMPLETE, not clean"
  exit 0
fi
[ "$rc" -eq 1 ] || exit 0
echo "=== OBSERVATORY WATCH (silent+checkable triggers past threshold) ==="
echo "$out"
exit 0
