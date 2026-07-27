"""Graph-completeness reporting — what the drift detector deliberately does NOT score.

This is where `_check_test_drift` went on 2026-07-27. As a drift dimension it read
`if not test_edges: return 0.3`, and since nothing writes VALIDATED_BY edges it
returned 0.30 for every symbol on every scan: 712 of 712 stored events carried it,
weighted into every composite severity. It was reported as *the code drifting* when
what it observed was *the graph being empty*.

The observation is still worth having. It is a count of intents with no linked
tests, printed on its own line, with no severity attached and no path into a
composite.

THIS MODULE READS AN EDGE TYPE NOTHING WRITES, ON PURPOSE. That is the one thing
doccheck's `drift-dimensions-have-producers` forbids in `drift.py`, and the
distinction is the whole point of the split: scoring the absence of an edge is a
bug, *reporting* it is the honest form of the same fact. If a VALIDATED_BY writer
ever lands, this number starts moving and nothing here needs to change.
"""

from __future__ import annotations

from .store import ICPGStore


def untested_intents(store: ICPGStore) -> tuple[int, int]:
    """(intents with no VALIDATED_BY edge, live intents). Never a severity."""
    reasons = [
        r for r in store.list_reasons()
        if r.status not in ('rejected', 'abandoned')
    ]
    without = sum(
        1 for r in reasons if not store.get_edges_from(r.id, 'VALIDATED_BY')
    )
    return without, len(reasons)
