"""Suite-wide guarantee: no test may write to the production audit log.

Found 2026-07-12, by reading the log the backstop was about to fire on. `guard.main()` calls
`_log_denial()` → `event.emit()`, which keys on `CLAUDE_CODE_SESSION_ID` — and under a normal
Claude Code session that variable IS set, so **every hook test appended a real `spend_denied`
to `.tessera/logs/<session>.jsonl`.** 26 of the session's 31 denials were manufactured by the
suite: an 84%-polluted friction journal, and a backstop poised to fire on its own tests.

This is the P3/trigger-tagging lesson in a new costume: *a test must never become evidence
about the thing it tests.* There, a hand-run `/compact` could have delivered the Mnemos
verdict on manufactured data. Here, pytest was manufacturing the spend journal.

The fix is at the root, not per-test: strip the session id and `emit()` is inert by
construction (it returns None with nothing to key on). No future test can pollute the log by
forgetting to mock something.

**THAT GUARANTEE HELD FOR 37 DAYS AND THEN A PARAMETER WALKED PAST IT (found 2026-08-18).**
ADR-0016 made `dismiss` human-only, which broke `emit()`'s keying — it read
`CLAUDE_CODE_SESSION_ID`, set only in an AGENT's environment, so a human's dismissal wrote
nothing. The 08-17 fix added an explicit `session_id=` parameter as the bridge. That
parameter takes precedence over the environment **by design**, so stripping the env var no
longer makes `emit()` inert: `event.emit(..., session_id="explicit-session")` writes,
whatever this fixture does.

`test_emit_accepts_an_explicit_session` then tried to contain itself with
`monkeypatch.setenv("TESSERA_SPEND_LOGS", ...)` — **a variable nothing reads.** `event.py`
resolves its root from `TESSERA_ROOT`. So the redirect was inert too, and every run appended
a real `spend_dismissed` to the production journal: **31 manufactured dispositions**, in the
one log this contract says must never be manufactured. Standing pattern #9 in the containment
itself — the monkeypatch RAN, it just set a name no consumer resolves.

So the strip is no longer sufficient and is no longer the guarantee. **`TESSERA_ROOT` is
redirected to a tmp dir for the whole suite**, which makes the bad state unrepresentable
rather than merely unlikely (ADR-0006 §2: before building a detector, ask what would make the
state unrepresentable). An explicit `session_id` now writes — to a temp directory, which is
what the test was trying to say. A test that genuinely needs the real root sets `TESSERA_ROOT`
itself; a fixture-set value is overridden by a later `monkeypatch.setenv` in the test body.
"""
import pytest


@pytest.fixture(autouse=True)
def no_audit_writes(monkeypatch, tmp_path_factory):
    # Both halves. The strip keeps `emit()` inert for the env-keyed path; the root redirect
    # is what survives an explicit `session_id`, which is the parameter that defeated the
    # strip. Either alone has now been shown insufficient.
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path_factory.mktemp("spend-audit-sandbox")))
