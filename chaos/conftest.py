"""No chaos probe may write to the production audit log. Twin of `scripts/conftest.py`.

These probes deliberately live outside `scripts/` — `pytest scripts/` would collect them, and
`--ignore`ing them would collide with doccheck's `ignored-test-suites-are-run`. That placement
also put them outside every conftest in the tree, and they drive real hooks as subprocesses,
which is exactly the shape that pollutes.

They measured clean when this was written; this is the guard, not a fix. A probe that boots a
guard tomorrow gets it for free.
"""
import pytest


@pytest.fixture(autouse=True)
def no_audit_writes(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
