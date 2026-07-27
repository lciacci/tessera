#!/bin/bash
# Does changing output_config.effort invalidate the prompt cache the way /model does?
#
# Undocumented: the invalidation hierarchy in the prompt-caching docs lists model switch
# (invalidates all three tiers) and `thinking` enable/disable (preserves tools+system,
# invalidates messages) — but NOT effort. So we measure instead of inferring.
#
# THE CONTROL IS LOAD-BEARING. Request 2 repeats request 1 verbatim. If it does not show a
# cache read, then caching never engaged at all and requests 1 and 3 tell you nothing —
# a zero read on request 3 would be indistinguishable from "effort invalidated it".
#
# Cost: 3 requests, ~1.5k input tokens each, 16 output. Roughly two cents.

set -uo pipefail

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  cat >&2 <<'EOF'
ANTHROPIC_API_KEY is not set.

  export ANTHROPIC_API_KEY='sk-ant-...'      # then re-run this script

(Or `brew install anthropics/tap/ant && ant auth login`, then
 export ANTHROPIC_API_KEY="$(ant auth print-credentials --access-token)" —
 note that path needs an extra `anthropic-beta: oauth-2025-04-20` header,
 so the plain API key is the simpler route for a one-off probe.)
EOF
  exit 1
fi

command -v jq >/dev/null || { echo "jq not found — brew install jq" >&2; exit 1; }

# >512 tokens (Claude Opus 5's cacheable minimum). Byte-identical across all three requests:
# any difference here and the prefix match fails for reasons that have nothing to do with effort.
FILLER=$(python3 -c "print('The quick brown fox jumps over the lazy dog. ' * 120, end='')")

probe() {
  local effort="$1" label="$2"
  local body
  body=$(jq -n --arg sys "$FILLER" --arg effort "$effort" '{
    model: "claude-opus-5",
    max_tokens: 16,
    system: [{type: "text", text: $sys, cache_control: {type: "ephemeral"}}],
    output_config: {effort: $effort},
    messages: [{role: "user", content: "Say OK."}]
  }')

  local resp
  resp=$(curl -sS https://api.anthropic.com/v1/messages \
    -H "content-type: application/json" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -d "$body")

  if echo "$resp" | jq -e '.type == "error"' >/dev/null 2>&1; then
    printf '%-34s ERROR: %s\n' "$label" "$(echo "$resp" | jq -r '.error.message')"
    return 1
  fi

  echo "$resp" | jq -r --arg l "$label" \
    '"\($l | .[0:34] | . + (" " * (34 - length)))write=\(.usage.cache_creation_input_tokens // 0 | tostring | (" " * (6 - length)) + .)  read=\(.usage.cache_read_input_tokens // 0 | tostring | (" " * (6 - length)) + .)"'
}

reads() { grep -oE 'read= *[0-9]+' <<<"$1" | grep -oE '[0-9]+'; }

echo "effort vs prompt cache — claude-opus-5"
echo "──────────────────────────────────────────────────────────────"
# Capture each row so the verdict can read its number, then echo it so you see the table.
# (Capturing without echoing is how row 3 vanished in the first draft; three requests, not four.)
ROW1=$(probe high "1. effort=high  (writes cache)");    echo "$ROW1"
ROW2=$(probe high "2. effort=high  (CONTROL: reads)");  echo "$ROW2"
ROW3=$(probe low  "3. effort=low   (the question)");    echo "$ROW3"
echo "──────────────────────────────────────────────────────────────"

CONTROL_READ=$(reads "$ROW2")
READ3=$(reads "$ROW3")

if [ "${CONTROL_READ:-0}" -eq 0 ]; then
  echo "VOID — the control never read from cache, so rows 1 and 3 mean nothing."
  echo "Something else is invalidating (check the prefix is byte-identical, and that"
  echo "the system block clears 512 tokens). Do not draw a conclusion from this run."
elif [ "${READ3:-0}" -gt 0 ]; then
  echo "RESULT: effort did NOT invalidate the cache (row 3 read ${READ3} tokens)."
  echo "Effort is a cheap knob — unlike /model, it can be changed mid-session."
else
  echo "RESULT: effort DID invalidate the cache (row 3 read 0 while the control read ${CONTROL_READ})."
  echo "Treat effort like /model: batch the changes, or change at a session boundary."
fi
