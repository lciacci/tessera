#!/usr/bin/env bash
# Surface fired Observatory triggers at session start — no human recall (principle #17).
# Silent when nothing fires; prints only when tessera-watch reports fired triggers
# (exit 1). Appends every run to the fire-log via --log. Fails open on any error.
[ -x "bin/tessera-watch" ] || exit 0
out=$(bin/tessera-watch --log 2>/dev/null)
[ $? -eq 1 ] || exit 0
echo "=== OBSERVATORY WATCH (silent+checkable triggers past threshold) ==="
echo "$out"
exit 0
