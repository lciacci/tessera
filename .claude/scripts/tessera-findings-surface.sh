#!/usr/bin/env bash
# Surface the downstream findings backlog at session start — no human recall.
# Silent when nothing is open; prints the backlog only when tessera-findings
# reports open items (exit 1). Fails open on any error.
[ -x "bin/tessera-findings" ] || exit 0
out=$(bin/tessera-findings 2>/dev/null)
[ $? -eq 1 ] || exit 0
echo "=== TESSERA FINDINGS BACKLOG (downstream → framework, un-transferred) ==="
echo "$out"
exit 0
