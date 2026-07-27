"""Suite-wide guarantee: no test may write to the production audit log.

`scripts/spend/conftest.py` made this promise on 2026-07-12 and made it correctly — for
`scripts/spend/`. It could not cover `scripts/test_hook_cwd_anchoring.py`, which drives the
REAL `tessera-spend-guard.sh` as a **subprocess** across four parametrized cwds. The guard
denies, calls `emit()`, and `emit()` keys on the `CLAUDE_CODE_SESSION_ID` **environment
variable** — which a subprocess inherits — so every `bin/tessera-test` run appended four real
`spend_denied` events to the live session journal. Twelve landed during the session that found
this, in a log nobody was reading for spend.

The payload those tests pass carries `"session_id": "anchor-test"`, which reads like isolation
and is not: the emitter never looks at it.

Placed at `scripts/` rather than beside the offending file, because the property is *no test
anywhere writes to the journal*, and the 07-12 fix's own reasoning applies — strip the variable
and `emit()` is inert by construction, so no future test can pollute by forgetting to mock.
Deleting the env var mutates `os.environ`, so it reaches subprocesses too, which is the half
the original conftest could not have known it needed.

`chaos/conftest.py` is its twin: those probes live outside `scripts/` on purpose (to dodge
pytest collection) and dodged this with it.

Pinned by `scripts/test_audit_log_is_not_polluted.py`, which asserts the *property* — invoke
the real hook, assert no production event appears — rather than the existence of this file.
"""
import pytest


@pytest.fixture(autouse=True)
def no_audit_writes(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
