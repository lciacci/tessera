"""The spend guard's tokenisation ceilings, PINNED (ADR-0028).

This file asserts what the guard gets WRONG, on purpose. It is the harvested residue of a
fix that was attempted over three review rounds and reverted — see ADR-0028 §1.

WHY PIN THE DEFECTS RATHER THAN DELETE THE TESTS. `_segments()` splits on shell separators
BEFORE quotes are stripped, which tears a quoted span containing a separator into fragments
with unbalanced quotes; `QUOTED` can no longer match them and the text inside reaches
`COMMITTING`. That produces false positives on read-only work — five-plus in one session,
all of them while maintaining or verifying this control.

Fixing it correctly requires real shell parsing. Three rounds of a hand-rolled state machine
produced TWO block→allow regressions on a deny-by-default control, both invisible to a green
suite and both found only by a reviewer diffing classifications against the original:

  round 1  quote-aware split         wrapper after a separator stopped being caught
  round 2  per-segment WRAPPER       three new false positives, incl. writing docs about the guard
  round 3  (found)                   an ordinary APOSTROPHE + a teardown token => `reducing`
                                     => allowed UNCONDITIONALLY, e.g.
                                     echo don't run terraform destroy || terraform apply

The false positive is the SAFE direction: it never allows spend, and a human `dismiss` verb
exists for it. Every fix was the UNSAFE direction. So the defect stays, and these tests make
it a *decided* ceiling rather than an undiscovered one — if any of them starts failing,
somebody has changed tokenisation, and ADR-0028 is what they must read first.

**Do not "fix" a test in this file by changing the guard.** Read ADR-0028 §1, then decide.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import guard  # noqa: E402


def _c(command: str) -> str:
    return guard.classify(command)


# ── CEILINGS: false positives. Safe direction — read-only work denied. ──────────────────
def test_ceiling_a_quoted_alternation_is_denied():
    """THE ORIGINAL COMPLAINT, and the one an escalation was raised about. The `|` inside
    the quotes splits the command, leaving `aws ec2 run-instances" notes.txt` — unbalanced,
    unstrippable, read as a boot. Dispose with `tessera-authorize dismiss` (human-only)."""
    assert _c('grep -E "terraform apply|aws ec2 run-instances" notes.txt') == "committing"


def test_ceiling_a_wrapper_led_heredoc_discussing_the_verb_is_denied():
    """Named in docs/contracts/spend-authorization.md before it was ever hit. A heredoc fed
    to an interpreter is code, so a body *listing* the verb is indistinguishable from one
    invoking it. Hit 3x in one session, including by the independent reviewer."""
    assert _c("python3 - <<'PY'\nprint('terraform apply')\nPY") == "committing"


def test_ceiling_an_invoked_script_is_read_for_its_contents():
    """`INVOKED_SCRIPT` reads one level down into a local .py/.sh it invokes and classifies
    the FILE. A probe script that merely *mentions* the verb as test data is therefore
    denied — a third false-positive class, catalogued 2026-08-18."""
    here = Path(__file__).resolve().parent
    probe = here / "_ceiling_probe.py"
    probe.write_text("CASES = ['terraform apply']\n")
    try:
        assert _c(f"python3 {probe}") == "committing"
    finally:
        probe.unlink()


# ── CEILINGS: holes. Unsafe direction, pre-existing, bounded by layer 3. ────────────────
def test_ceiling_a_piped_interpreter_is_not_caught():
    """`echo … | bash` splits to a bare, neutral `bash` segment. Documented in the contract
    as never having been caught. Layer 3 is the bound."""
    assert _c('echo "terraform apply" | sh') == "neutral"


def test_ceiling_a_wrapper_payload_with_no_separator_is_not_caught():
    """`WRAPPER`'s bare-`eval|bash|sh` alternative is anchored `^\\s*` against the WHOLE
    command, so a wrapper after a separator is invisible unless the naive split happens to
    tear its payload. With no separator inside the payload, nothing tears and nothing
    catches it."""
    assert _c('cd /x && eval "terraform apply"') == "neutral"


# ── The property every future tokenisation change must preserve ────────────────────────
def test_an_apostrophe_must_never_turn_a_boot_into_a_teardown():
    """THE REGRESSION THAT ENDED THE FIX ATTEMPT, kept as a forward-facing guard.

    A quote-aware splitter refuses to split while a quote is open, so an ordinary
    apostrophe swallows the rest of the command. `_classify_one` checks `REDUCING` FIRST,
    so a teardown token anywhere in the swallowed span makes the whole command `reducing`
    — which is allowed UNCONDITIONALLY, because the exit must never be blocked. An English
    apostrophe is not adversarial input.
    """
    assert _c("echo don't run terraform destroy || terraform apply") == "committing"
    assert _c("echo it's done; terraform destroy; terraform apply") == "committing"


# ── The invariants that hold today and must survive anything ───────────────────────────
def test_committing_wins_across_separators():
    assert _c("terraform destroy && terraform apply") == "committing"


def test_the_exit_is_never_blocked():
    assert _c("terraform destroy") == "reducing"
    assert _c("terraform apply -var enable_gpu=false") == "reducing"


def test_wrapper_led_quotes_are_code():
    assert _c('bash -c "terraform apply"') == "committing"
    assert _c("eval 'terraform apply'") == "committing"


def test_a_mention_is_not_an_invocation():
    assert _c('git commit -m "notes about terraform apply"') == "neutral"


def test_self_authorization_is_refused():
    assert _c("tessera-authorize grant --usd 5") == "self-authorizing"
