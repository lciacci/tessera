#!/bin/bash

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
# Mnemos Stop Hook — writes incremental checkpoint when agent stops.
# Captures final session state so the next session can resume cleanly.
# No set -euo pipefail: hook scripts must be defensive, not strict.

# Spec 11: report "I could not do my job". Binary lookup only — the destination comes from
# the hook JSON, so the ADR-0004 global tier ($HOME) is harmless here. Resolved from $0
# captured before any cd. Inlined, not sourced: a shared lib is one more file that can go
# missing on the path whose job is reporting missing files (pattern #1).
_HOOKDIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd)
degraded() {
  for _c in "$_HOOKDIR/../../bin/tessera-degraded" "$_HOOKDIR/../../scripts/tessera-degraded"; do
    if [ -x "$_c" ]; then "$_c" "$@" >/dev/null 2>&1 || true; return 0; fi
  done
  command -v tessera-degraded >/dev/null 2>&1 && tessera-degraded "$@" >/dev/null 2>&1
  return 0
}

INPUT=$(cat 2>/dev/null || true)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || echo ".")
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || echo "")

# Anchor to the PROJECT ROOT, not the session cwd (2026-07-26). Any Bash `cd` moves `.cwd`,
# and the check below reads "$CWD/.mnemos". From a subdirectory that directory is absent, so
# this hook took the QUIET branch and wrote NO CHECKPOINT — while reporting the exact thing
# spec 11 forbids: "nothing to do" when the truth was "I could not do my job". The silence
# is the bug, not the miss. CLAUDE_PROJECT_DIR is preferred but EMPTY in some invocations,
# so it cannot carry this alone. Pure parameter expansion, no dirname/sed.
# Sets $_root. Returns via a VARIABLE, not stdout: a PreToolUse hook's bare stdout is a
# real channel, and doccheck's pretooluse-hooks-reach-the-model rightly cannot tell a
# function's `printf` from the hook writing to it. Also saves a subshell fork per call.
_anchor_root() {
    _d="$1"; _root="$1"      # fall back to the input; never yield empty
    while [ -n "$_d" ] && [ "$_d" != "/" ]; do
        if [ -e "$_d/.git" ] || [ -f "$_d/.tessera/project.yml" ]; then _root="$_d"; return 0; fi
        case "$_d" in */*) _d="${_d%/*}" ;; *) break ;; esac
    done
}
_anchor_root "${CLAUDE_PROJECT_DIR:-${CWD:-$PWD}}"; CWD="$_root"

# QUIET: no .mnemos/ means this project does not use Mnemos. Genuinely nothing to do.
if [ ! -d "$CWD/.mnemos" ]; then
  exit 0
fi

# Write checkpoint via Python module.
# NOTE: this MUST be the top-level `checkpoint` subcommand, not `_hook
# checkpoint` — the latter is not a registered hook event, so it errored and
# silently fell through to the thin Python fallback below (placeholder goal,
# empty subgoal/narrative/files). The top-level command runs write_checkpoint(),
# which captures active goal/constraint/result nodes + git branch + uncommitted.
cd "$CWD" 2>/dev/null || true

# Resolve a mnemos-capable runner the same way the sibling hooks do. The console
# script pins its own interpreter (mnemos installed for 3.13; bare `python3` may
# be a newer homebrew python with no mnemos) — prefer it, then `python3 -m mnemos`,
# then the inline sqlite fallback below (degraded: writes file only, no db row).
if [ -x ".venv/bin/mnemos" ]; then
  MNEMOS_CMD=".venv/bin/mnemos"
elif command -v mnemos >/dev/null 2>&1; then
  MNEMOS_CMD="mnemos"
fi

if [ -n "$MNEMOS_CMD" ]; then
  # --task-id carries the LIVE session so the checkpoint's goal is this session's,
  # not whichever goal happens to be newest. $SESSION_ID was already parsed above
  # and used only for `degraded` reporting; the checkpoint never received it, so
  # write_checkpoint had no way to tell "my task" from "some task" and fell back to
  # recency alone (2026-07-27: 44 bulk-imported goals then took all 8 slots).
  # Empty is fine — the flag is optional and selection degrades to recency.
  $MNEMOS_CMD checkpoint --force ${SESSION_ID:+--task-id "$SESSION_ID"} >/dev/null 2>&1 && exit 0
  # LOUD: the managed runner exists but could not write a checkpoint.
  degraded --component mnemos-checkpoint --reason checkpoint-failed --session "$SESSION_ID" \
    --project "$CWD" --detail "$MNEMOS_CMD checkpoint --force failed; falling back to the inline writer"
else
  # LOUD — and this is F-001's exact shape. No managed runner anywhere, so the inline
  # python3 block below writes a checkpoint ANYWAY, on an unmanaged interpreter. It does
  # not fail; it silently SUCCEEDS, which is strictly harder to detect. The whole Mnemos
  # trial was confounded by this once ("the graph is empty" read as unused, not
  # unreachable). Going quiet here — as this hook did until spec 11 — is what let that run
  # for weeks. tessera-watch P9 covers the interpreter separately; this covers the event.
  degraded --component mnemos-checkpoint --reason toolchain-unreachable --session "$SESSION_ID" \
    --project "$CWD" --detail "no .venv/bin/mnemos and no mnemos on PATH; the checkpoint took the unmanaged inline fallback"
fi

python3 -c "
import json, time, os, uuid

db_path = '.mnemos/mnemo.db'
cp_dir = '.mnemos/checkpoints'
latest = '.mnemos/checkpoint-latest.json'

if not os.path.exists(db_path):
    exit(0)

os.makedirs(cp_dir, exist_ok=True)

import sqlite3
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

nodes = conn.execute('SELECT type, content FROM mnemo_nodes WHERE status=\"active\"').fetchall()
node_types = {}
for n in nodes:
    t = n['type']
    node_types[t] = node_types.get(t, 0) + 1

# Get git state
import subprocess
branch = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
status = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True).stdout.strip()
uncommitted = [l.split()[-1] for l in status.split('\n') if l.strip()] if status else []

# Read fatigue
fatigue = 0.0
try:
    with open('.mnemos/fatigue.json') as f:
        fatigue = json.load(f).get('score', 0.0)
except: pass

cp_id = str(uuid.uuid4())
checkpoint = {
    'id': cp_id,
    'task_id': 'auto-stop',
    'goal': 'Session ended — auto-checkpoint',
    'active_constraints': [n['content'] for n in nodes if n['type'] == 'constraint'],
    'active_results': [n['content'] for n in nodes if n['type'] == 'result'],
    'current_subgoal': '',
    'working_memory': '',
    'task_narrative': '',
    'recent_files': [],
    'fatigue_at_checkpoint': fatigue,
    'git_state': {'branch': branch, 'uncommitted': uncommitted},
    'node_summary': {
        'total': len(nodes),
        'active': len(nodes),
        'compressed': 0,
        'by_type': node_types
    },
    'created_at': time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())
}

with open(os.path.join(cp_dir, cp_id + '.json'), 'w') as f:
    json.dump(checkpoint, f, indent=2)
with open(latest, 'w') as f:
    json.dump(checkpoint, f, indent=2)

conn.close()
" 2>/dev/null || true

exit 0
