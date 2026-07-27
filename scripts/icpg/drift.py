"""Drift detection over the dimensions that have real inputs.

SHRUNK 2026-07-27 from six dimensions to three. Five of the six scored whether an
EDGE TYPE existed in the graph rather than whether the code had changed, and four
of those edge types (REQUIRES, DUPLICATES, VALIDATED_BY, DRIFTS_FROM) have no
writer anywhere in this codebase. Consequences, measured before the cut:

    712 of 712 stored events carried a constant `test(0.30)`
    decision / ownership / dependency drift had NEVER fired, in either direction
    usage drift shelled out to `grep -rl <name> .` over an unfiltered tree

A dimension that can only ever return one value is not a measurement. The stored
events were therefore purged rather than deduplicated: deduplicating them would
have preserved 154 distinct non-measurements. (Standing pattern #7 — a verdict
must not rest on what the instrument could not read.)

WHAT SURVIVES, and the producer feeding each:

    changed   symbol checksum vs. the recorded one          <- upsert_symbol
    decision  the intent's contract predicates, re-run      <- contracts.py
    usage     symbol referenced outside its intent's scope, <- git grep, tracked
              over GIT-TRACKED files only                      files only

WHAT LEFT, and where it went:

    test        -> `coverage.py`. "No VALIDATED_BY edge" is a fact about the
                   graph's completeness, not about code drifting. Reported as a
                   count, never as a severity.
    ownership   -> deleted. Needed >3 distinct reason owners on one symbol; every
                   ReasonNode here is `owner='git-history'` from the bootstrap.
    dependency  -> deleted. Needed REQUIRES edges between reasons; unwritten.

Re-adding a dimension means adding its PRODUCER FIRST. doccheck's
`drift-dimensions-have-producers` fails if this module reads an edge type that
nothing in `scripts/icpg/` writes — the check that would have caught all of the
above at commit time, which is what standing pattern #1 asks for. `coverage.py`
is deliberately out of that check's scope: measuring an absent edge type is its
entire job.

Note this does NOT settle iCPG's kill/keep trial. `design-principles.md:459` asks
two questions and this addresses one; the other — does the agent populate
ReasonNodes in practice — is still unexercised, and its cause is fully explained
(nothing records, and the hook that surfaces intent was silent until 2026-07-24).
See docs/observatory.md -> "iCPG's drift detector measures the emptiness of its
own graph".
"""

from __future__ import annotations

import subprocess

from .models import DriftEvent, _now, _uuid
from .predicates import evaluate_predicate
from .store import ICPGStore
from .symbols import extract_symbols


def check_file_drift(store: ICPGStore, file_path: str) -> list[DriftEvent]:
    """Check drift for symbols in a single file only. Fast path for hooks."""
    events = []
    for sym in store.get_symbols_for_file(file_path):
        event = check_symbol_drift(store, sym.id)
        if event:
            events.append(event)
    return events


def check_all_drift(store: ICPGStore) -> list[DriftEvent]:
    """Full drift scan across all tracked symbols."""
    events = []
    for reason in store.list_reasons():
        if reason.status in ('rejected', 'abandoned'):
            continue
        for edge in store.get_edges_from(reason.id, 'CREATES'):
            sym = store._get_symbol(edge.to_id)
            if not sym:
                continue
            event = check_symbol_drift(store, sym.id)
            if event:
                events.append(event)
    return events


def check_symbol_drift(store: ICPGStore, symbol_id: str) -> DriftEvent | None:
    """Check a single symbol across the dimensions that have inputs."""
    sym = store._get_symbol(symbol_id)
    if not sym:
        return None
    creates_edges = store.get_edges_to(symbol_id, 'CREATES')
    if not creates_edges:
        return None
    reason = store.get_reason(creates_edges[0].from_id)
    if not reason:
        return None

    scored = [
        ('changed', _check_changed_drift(store, sym)),
        ('decision', _check_decision_drift(store, reason)),
        ('usage', _check_usage_drift(store, sym, reason)),
    ]
    hits = [(dim, score) for dim, score in scored if score]
    if not hits:
        return None
    return _build_event(symbol_id, reason.id, hits)


def _build_event(symbol_id: str, reason_id: str, hits) -> DriftEvent:
    dimensions = [dim for dim, _ in hits]
    scores = [score for _, score in hits]
    parts = ', '.join(f'{d}({s:.2f})' for d, s in hits)
    return DriftEvent(
        id=_uuid(),
        symbol_id=symbol_id,
        from_reason_id=reason_id,
        drift_dimensions=dimensions,
        severity=round(sum(scores) / len(scores), 2),
        description=f'Drift detected: {parts}',
        detected_at=_now()
    )


def _check_changed_drift(store, sym) -> float | None:
    """Symbol checksum differs from the one recorded, or the symbol is gone.

    Was `spec` drift, defined as "changed WITHOUT a MODIFIES edge". Renamed
    2026-07-27 because that exemption has never once applied: `icpg record` is
    the only writer of MODIFIES and no hook invokes it, so the old name promised
    a distinction the data could not make. The exemption is kept — it costs one
    query and becomes live the moment a recorder is wired — but the dimension is
    now named for what it actually measures.
    """
    current = next(
        (s for s in extract_symbols(sym.file_path) if s.name == sym.name), None
    )
    if not current:
        return 0.8  # Symbol removed entirely
    if current.checksum != sym.checksum:
        if not store.get_edges_to(sym.id, 'MODIFIES'):
            return 0.6  # Changed without explanation
    return None


def _check_decision_drift(store, reason) -> float | None:
    """Contract predicates that no longer hold.

    Reads invariants AND postconditions. Until 2026-07-27 it read postconditions
    ALONE — and nothing in this repo has ever written one (0 of 10 reasons),
    while `contracts.py:88` writes a `file_exists(...)` invariant for every scope
    path of every reason (10 of 10, ~50 predicates). A live producer and a live
    evaluator that were never connected, which is why this dimension had never
    fired. That is not the "no writer" failure the other dimensions had; it is a
    narrower and more embarrassing one, and only reading the rows found it.
    """
    predicates = list(reason.invariants) + list(reason.postconditions)
    if not predicates:
        return None
    failed = sum(
        1 for p in predicates if not evaluate_predicate(p, store.project_dir)
    )
    return min(1.0, failed / len(predicates)) if failed else None


def _check_usage_drift(store, sym, reason) -> float | None:
    """Symbol referenced outside its intent's declared scope, over tracked files.

    `git grep` replaced `grep -rl <name> .` on 2026-07-27. The old form walked
    the whole tree — `.venv/`, `.git/`, `build/`, `__pycache__` — so any common
    symbol name saturated the score inside vendored code alone, and the score
    was `min(1.0, n/10)`, i.e. pinned at 1.00 after ten hits. Tracked-only is
    also this repo's standing rule: `git ls-files`, never `find`.
    """
    if not reason.scope:
        return None
    files = _tracked_files_mentioning(sym.name, store.project_dir)
    if files is None:
        return None
    out_of_scope = [f for f in files if not _in_scope(f, reason.scope)]
    if len(out_of_scope) <= 2:
        return None
    return min(1.0, len(out_of_scope) / 10)


def _tracked_files_mentioning(name: str, project_dir) -> list[str] | None:
    """Tracked files containing `name`, or None if git could not answer.

    None is "no answer", NOT "no matches" — a missing git, a timeout, or a
    non-repo directory must not read as a clean scope. rc=1 IS an answer: git
    grep uses it for "no matches found".
    """
    try:
        result = subprocess.run(
            ['git', 'grep', '--name-only', '--fixed-strings', '-e', name],
            capture_output=True, text=True, timeout=5, cwd=str(project_dir)
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode not in (0, 1):
        return None
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


def _in_scope(path: str, scope: list[str]) -> bool:
    return any(path.startswith(s.rstrip('/')) for s in scope)
