State an iCPG intent (ReasonNode) before implementing — step 0 of the loop.

Usage:
```
/icpg-intent "Add OAuth2 PKCE flow" --scope src/auth.py
/icpg-intent "Extract routing middleware" --scope src/api/ src/middleware.py \
    --invariant 'file_exists("src/middleware.py")'
```

Runs `icpg create`, which:
- opens the intent as **`executing`**, so the Stop hook can attribute work to it
- accepts repeatable `--invariant` / `--precondition` / `--postcondition`, each a
  **predicate**, not prose: `file_exists("p")`, `test_exists("p")`,
  `symbol_count("dir") <= 15`, `function_signature("name") == "..."`
- unions hand-authored contracts with `--infer-contracts` rather than replacing them

These are the real CLI's flags. This file previously documented `--file` and a prose
`--invariants`; neither has ever existed. The distinction matters beyond typing — the
`decision` drift dimension evaluates these, so prose is silently unevaluable.

**Close it when done** — not optional bookkeeping:
```
icpg fulfil <id> --note "what shipped"
```
`icpg-stop-record.sh` attributes symbols only when exactly **one** intent is
executing. At zero it records nothing; at two or more it goes quiet and emits a
`degraded` event rather than guess which intent a change belongs to. Leaving intents
open is precisely what makes the recorder go silent.

To see existing intents:
```
/icpg-why src/auth.py
```
