#!/bin/bash

# Spec 11 reporter. `$_HOOKDIR` is captured BEFORE the anchoring cd below so a relative $0
# cannot be invalidated by it. Inlined rather than sourced, same reasoning as
# tessera-restore-scan.sh: a shared lib is one more file that can go missing on the path
# whose job is reporting missing files. Output is discarded because THIS hook's stdout is
# the context channel — a reporter must never be able to corrupt the restore it reports on.
#
# THE TWO PATH FAMILIES ANSWER TO OPPOSITE TIERS, and that is deliberate — flagged as an
# inconsistency in review (2026-07-29), so it is written down rather than left to be
# re-derived. Unlike every sibling, this is a SessionStart hook: it parses no stdin, so it
# has no hook-JSON `cwd` to anchor on and only these two signals.
#   PROJECT tier — the `case` below fires, $PWD becomes the repo root, and the $_HOOKDIR
#     entries resolve. The $PWD entries are then redundant, pointing at the same files.
#   GLOBAL tier — the `case` deliberately does NOT fire ($HOME is not a repo), so
#     $_HOOKDIR/../.. is $HOME and resolves nothing. The $PWD entries are LOAD-BEARING.
# So $PWD is read post-cd on purpose. That is consistent with the whole hook, not a lapse:
# the checkpoint probe and offer.py probe below are $PWD-relative too, because in the
# global tier the session cwd IS this hook's only notion of which project it is serving.
# Weakening the `case` guard breaks this function as well — which is why it says so here.
degraded() {
  for _c in "$_HOOKDIR/../../bin/tessera-degraded" "$_HOOKDIR/../../scripts/tessera-degraded" \
            "$PWD/bin/tessera-degraded" "$PWD/scripts/tessera-degraded"; do
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

# ── Toolchain resolution: a PATH, never a NAME, and NO bare-python3 fallback. (F-001) ──
# This block used to fall back to `python3 -m mnemos`. That fallback was the bug: with
# PYTHONPATH=scripts, ANY interpreter imports mnemos straight from source — so it did not
# fail, it silently SUCCEEDED on an unmanaged Python that Homebrew can re-point or delete.
# The original F-001 failed silently (import error → no-op); this one *worked*, on the wrong
# interpreter. A silent success is strictly harder to detect than a silent failure.
# If the toolchain is unreachable, this hook now goes QUIET. tessera-watch P9 catches that.
# Mnemos SessionStart Hook — loads checkpoint on session resume.
#
# Checks for .mnemos/checkpoint-latest.json and injects it into context.
# Also bridges iCPG state if available.
#
# Install: add to .claude/settings.json under hooks.SessionStart

# ─── Load checkpoint if exists ───

if [ -f ".mnemos/checkpoint-latest.json" ]; then
    MNEMOS_CMD=""
    if [ -x ".venv/bin/mnemos" ]; then
        MNEMOS_CMD=".venv/bin/mnemos"
    elif command -v mnemos &>/dev/null; then
        MNEMOS_CMD="mnemos"
    fi

    if [ -n "$MNEMOS_CMD" ]; then
        RESUME_OUTPUT=$($MNEMOS_CMD resume 2>/dev/null)
        if [ -n "$RESUME_OUTPUT" ]; then
            echo "=== MNEMOS SESSION RESUME ==="
            echo "$RESUME_OUTPUT"
            echo ""
            echo "You are resuming from a previous session checkpoint."
            echo "Review the goal and constraints above before proceeding."
            echo "============================="

            # T2 (ADR-0015): record that a restore was OFFERED. This is the harness side
            # of the receipt — the party that cannot mark its own homework. It claims only
            # what is mechanically true (bytes, fields); it does NOT claim delivery, which
            # is precisely the claim `restore_injected` was not entitled to make.
            # Silent by construction: this hook's stdout IS the context channel.
            # stdlib-only, so bare python3 is correct here (CLAUDE.md interpreter split).
            #
            # LOUD on fall-through (2026-07-29). This loop used to end with no `else`, and
            # that silence is the whole reason the T2 instrument sat dark in the fleet for
            # its entire life: `restore_offered` = 0 across 34 downstream sessions in 6
            # projects, 26 of them substantive. A checkpoint WAS delivered every one of
            # those times — the branch above ran — so the log of an uninstalled instrument
            # and the log of one with nothing to say were byte-identical. Pattern #1, in
            # the harness half of a design built specifically so no party marks its own
            # homework. In the GLOBAL tier path 1 resolves to $HOME and path 2 is the
            # project, which is the pairing that must hold; if neither does, say so.
            # PRESENT-BUT-BROKEN is a distinct failure from ABSENT, and the first draft of this
            # block conflated them: it set the found-flag on the same line as the interpreter
            # call, so a resolvable offer.py that CRASHED suppressed the very diagnostic this
            # block exists to emit. Pattern #1, aimed at the fix for pattern #1. Caught by
            # arbiter, not by me. So: only a clean exit counts as recorded, and a failing path
            # falls through to the next candidate rather than claiming the job is done.
            #
            # LIMIT, stated because it is not obvious: offer.py returns 0 on EVERY path,
            # including the ones where it deliberately writes nothing (no session id, no
            # checkpoint, unwritable log). So `$?` separates crashed from ran — it cannot
            # separate ran-and-wrote from ran-and-declined. Closing that needs the caller to
            # check the log, which duplicates offer.py's own session-keyed anchoring. The
            # honest boundary: this reports the toolchain, `tessera-restore-scan` reports the
            # missing offer at Stop, and neither claims to be the other.
            _off_found=""; _off_seen=""
            for _off in "$_HOOKDIR/../../scripts/restore/offer.py" \
                        "$PWD/scripts/restore/offer.py"; do
                [ -f "$_off" ] || continue
                _off_seen=1
                python3 "$_off" >/dev/null 2>&1 && { _off_found=1; break; }
            done
            if [ -z "$_off_found" ]; then
                if [ -n "$_off_seen" ]; then
                    _off_reason=offer-failed
                    _off_detail="scripts/restore/offer.py resolved but exited non-zero; no restore_offered recorded. The module is present, so this is a toolchain fault (python3, imports), not a sync gap."
                else
                    _off_reason=offer-missing
                    _off_detail="a checkpoint was delivered but scripts/restore/offer.py resolved nowhere; no restore_offered recorded, so this session's receipt cannot be asked for. Run tessera-sync-harness."
                fi
                degraded --component restore-offer --reason "$_off_reason" --detail "$_off_detail"
            fi
        fi
    fi
fi

# ─── Bridge iCPG if available and Mnemos DB exists ───

if [ -f ".icpg/reason.db" ] && [ -f ".mnemos/mnemo.db" ]; then
    MNEMOS_CMD=""
    if [ -x ".venv/bin/mnemos" ]; then
        MNEMOS_CMD=".venv/bin/mnemos"
    elif command -v mnemos &>/dev/null; then
        MNEMOS_CMD="mnemos"
    fi

    if [ -n "$MNEMOS_CMD" ]; then
        # Bridge in background — don't block session start
        $MNEMOS_CMD bridge-icpg &>/dev/null &
    fi
fi

# ─── Show iCPG status if available ───

if [ -f ".icpg/reason.db" ]; then
    ICPG_CMD=""
    if [ -x ".venv/bin/icpg" ]; then
        ICPG_CMD=".venv/bin/icpg"
    elif command -v icpg &>/dev/null; then
        ICPG_CMD="icpg"
    fi

    if [ -n "$ICPG_CMD" ]; then
        STATUS=$($ICPG_CMD status 2>/dev/null)
        if [ -n "$STATUS" ]; then
            echo ""
            echo "=== iCPG STATUS ==="
            echo "$STATUS"
            echo "==================="
        fi
    fi
fi

exit 0
