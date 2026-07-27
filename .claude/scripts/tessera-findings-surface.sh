#!/usr/bin/env bash

# Spec 11 / A5b: report "I could not do my job" instead of exiting 0 into the dark.
# Resolved BEFORE the anchoring cd so $0-relative resolution cannot be broken by it.
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
# Surface the downstream findings backlog at session start — no human recall.
# Silent when nothing is open; prints the backlog only when tessera-findings
# reports open items (exit 1). Fails open on any error.
# A5b (2026-07-27): both lines were bare `|| exit 0`. Probed: delete bin/tessera-findings
# and SessionStart looks completely normal while the downstream findings backlog silently
# stops surfacing. The settings.json trailing branch reports THIS SCRIPT missing, never the
# runner it calls.
if [ ! -x "bin/tessera-findings" ]; then
  degraded --component tessera-findings --reason runner-missing \
    --detail "bin/tessera-findings is absent or not executable; the downstream findings backlog cannot surface"
  exit 0
fi
out=$(bin/tessera-findings 2>/dev/null)
rc=$?
# 1 = open findings, 0 = none (correct silence). Anything else is a crash, and treating it
# as 0 is how "nothing is open" and "I could not look" become the same sentence.
if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
  degraded --component tessera-findings --reason runner-crashed \
    --detail "bin/tessera-findings exited $rc; the backlog was not read this session"
  exit 0
fi
[ "$rc" -eq 1 ] || exit 0
echo "=== TESSERA FINDINGS BACKLOG (downstream → framework, un-transferred) ==="
echo "$out"
exit 0
