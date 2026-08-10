# Calibration fixtures (ADR-0020)

`correction_cases.jsonl` is the fixture matrix ADR-0020 adopted from Agent Behavior:
five case types — `positive`, `negative`, **`lucky_correct_negative`**, `outside_scope`,
`allowed_boundary` — against the spec-13 correction rubric.

## Why this is TRACKED, deviating from ADR-0020 §152

The ADR says *"Add the five case types … to the silver-label set."* The silver-label set is
`.mnemos/silver-corrections.jsonl`, and `.gitignore:18` ignores `.mnemos/` entirely. Following that
literally would put hand-authored test cases in per-machine runtime state, where they would:

- vanish on a clean clone — the blind spot that produced two bugs in one day on 2026-08-09
- be unreviewable, since nothing untracked reaches a diff
- be unable to back a regression test in `tessera-test`

So the fixtures are tracked and the silver set is untouched. **The two are different kinds of
artifact and the ADR conflated them:** the silver set is 125 *observed* turns judged after the
fact; this file is *authored* cases with intended verdicts. Only the second is a fixture.
Recorded as a deliberate deviation, not an oversight — see ADR-0020's `Executed:` line.

## The rule that makes this file worth having

**Ground truth here is authored from the rubric, never from what a detector returns.** When a
detector disagrees with a fixture, the fixture is not the default suspect — record which layer
owns the disagreement (below) and fix that layer. Tuning fixtures until the detector passes is
the eval-shaped form of standing pattern #1, and it is the specific failure ADR-0020 adopted
the five-layer diagnosis to prevent.

## The lucky-correct negative, and why it is a PAIR

ADR-0020 calls this "the load-bearing one": a case where *the outcome is right and the required
process was not followed*. For a classifier that means **the right answer via a mechanism that
does not generalize** — and a single case cannot show that. Only a twin can.

Each `lucky_correct_negative` pair shares a surface `cue` and is scored as one unit:

> **Credit requires BOTH members correct.** Getting the `lucky` member right on its own earns
> nothing — that is what "stays negative" means here.

Two pair shapes, both present:

| shape | members | what it exposes |
|---|---|---|
| opposite truth | `lead-no`, `lead-wait`, `lead-actually`, `lead-stop`, `phrase-instead`, `lead-revert` | the cue fires on a turn that is not a correction |
| same truth | `orthographic-dont` | the cue is *absent* from an equivalent turn, so it is missed |

`orthographic-dont` is the sharpest: `"don't merge that yet"` and `"do not merge that yet"` are
the same sentence, and `regex_match` splits them on the apostrophe.

## Five-layer disagreement diagnosis

When a fixture and a detector disagree, name the owning layer before changing anything:

| layer | means | fix |
|---|---|---|
| `wording` | the rubric/prompt text is ambiguous or wrong | edit `_PROMPT` in `correction_detect.py` |
| `fixture` | this case is genuinely mislabeled or ambiguous | edit the fixture, and say why |
| `judge` | the detector mechanism is too shallow | change the detector — the usual answer for cue-keyed misses |
| `telemetry` | the trace does not carry enough to judge (e.g. the 200-char preview, or eligibility that is structural rather than textual) | improve capture |
| `policy` | the definition of "correction" should change | that is a spec-13 decision, not an eval fix |

## Known coverage limit, stated rather than discovered later

`outside_scope` here covers only **carrier rows** (interrupt markers, bash stdout). The other
out-of-scope class — *a user turn that does not follow an agent action* — is **structural, not
textual**: eligibility depends on turn position, which a text-only fixture cannot express. That
is a `telemetry`-layer limit and it is why this file cannot be the whole matrix.

## Running it

```bash
.venv/bin/python -m scripts.mnemos.eval_correction --fixtures   # live classifier (needs Ollama)
bin/tessera-test                                                 # deterministic, regex only
```
