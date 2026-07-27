#!/bin/bash
# iCPG Stop Hook — link the symbols this session touched to the intent it stated.
#
# Step 6 (RECORD) of the nine-step loop in skills/icpg/SKILL.md. Without it
# there is nothing to drift-check against, so steps 6 and 7 only close together.
#
# This records ONLY. It never creates an intent: step 0 is a judgement, and a
# hook authoring it would make "does the agent state intent?" unanswerable by
# answering it automatically. The prompt lives in icpg-inject-context.sh.
#
# Replaces templates/icpg-stop-record.sh (2026-07-12), which was never installed
# or wired and could not have worked: it read `.icpg/.current-intent` — written
# by hooks/icpg-record-intent as a FILE PATH, not a ReasonNode id — and the
# writer called `icpg record --file X --auto-invariants`, flags the CLI has never
# had. Both are deleted. The graph already knows the active intent
# (status='executing'); a marker file was a second source of truth for a fact the
# database holds.

# Anchor to the project root: hook commands inherit the SESSION cwd, which may be
# another repo entirely. $0 is a fact this script always has.
case "$(dirname "$0")" in
  */.claude/scripts) cd "$(dirname "$0")/../.." 2>/dev/null || exit 0 ;;
esac
# Guarded: this script is ALSO installed to ~/.claude/templates/ as the ADR-0004
# global fallback, where ../.. is $HOME, not a repo.

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

# ── Toolchain interpreter: a PATH, never a NAME. (F-001) ──────────────────────
TOOLCHAIN_PY=""
if [ -x ".venv/bin/python" ]; then
    TOOLCHAIN_PY=".venv/bin/python"
elif command -v mnemos >/dev/null 2>&1; then
    TOOLCHAIN_PY="$(sed -n '1s/^#!//p' "$(command -v mnemos)" 2>/dev/null | awk '{print $1}')"
fi
if [ -z "$TOOLCHAIN_PY" ] || [ ! -x "$TOOLCHAIN_PY" ]; then
    degraded --component icpg-stop-record --reason toolchain-unavailable \
      --detail "no .venv/bin/python and no mnemos on PATH; session symbols were not recorded to any intent"
    exit 0
fi

BASE=$(cat .icpg/.session-base 2>/dev/null)
if [ -z "$BASE" ]; then
    degraded --component icpg-stop-record --reason no-session-base \
      --detail ".icpg/.session-base absent; icpg-session-base.sh did not run, so there is no anchor to diff from"
    exit 0
fi

# The base can vanish: a rebase or a reset rewrites history and the stored SHA
# becomes unreachable. GO QUIET AND SAY SO — never fall back to HEAD~1. A
# recorder that guesses its own scope writes false intent links, and drift then
# measures against fiction, which is worse than an empty graph.
if ! git cat-file -e "${BASE}^{commit}" 2>/dev/null; then
    degraded --component icpg-stop-record --reason session-base-unreachable \
      --detail "base ${BASE} is no longer in the object graph (rebase/reset); refusing to guess a base, nothing recorded"
    exit 0
fi

# The graph is the marker: exactly one executing intent is unambiguous.
EXECUTING=$("$TOOLCHAIN_PY" -c "
from icpg.store import ICPGStore
print('\n'.join(r.id for r in ICPGStore('.').list_reasons(status='executing')))
" 2>/dev/null)
# ZERO is not a failure — it is the honest state when no intent was stated. Step
# 0's prompt (icpg-inject-context.sh) is what addresses that; reporting degraded
# here would fire on every session of a project that does not use intents.
#
# Tested empty-first on purpose. The first version counted with
# `grep -c . || echo 0`, and on empty input grep prints 0 AND exits 1 — so the
# fallback fired too and COUNT became "0\n0", which made both numeric guards throw
# `integer expression expected` and fall through to the record call. It exited 0 by
# luck rather than by logic, which is the shape that ships as "working".
[ -z "$EXECUTING" ] && exit 0
COUNT=$(printf '%s\n' "$EXECUTING" | wc -l | tr -d ' ')

# TWO OR MORE: go quiet rather than guess which intent a change belongs to — but
# REPORT it, because "recorded nothing" must not be indistinguishable from
# "nothing to record". Close one with `icpg fulfil <id>`.
if [ "$COUNT" -gt 1 ]; then
    degraded --component icpg-stop-record --reason ambiguous-intent \
      --detail "$COUNT executing intents; refusing to attribute this session's symbols to one of them. Close finished intents with 'icpg fulfil <id>'"
    exit 0
fi

OUTPUT=$("$TOOLCHAIN_PY" -m icpg record --reason "$EXECUTING" --base "$BASE" 2>&1)
if [ $? -eq 0 ]; then
    printf 'iCPG: %s\n' "$OUTPUT" >&2
else
    degraded --component icpg-stop-record --reason record-failed \
      --detail "icpg record --reason ${EXECUTING} --base ${BASE} failed: $(printf '%s' "$OUTPUT" | head -1)"
fi

exit 0
