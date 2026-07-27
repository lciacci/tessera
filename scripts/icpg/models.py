"""Data models for iCPG — ReasonNode, Symbol, Edge, DriftEvent."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def symbol_id(file_path: str, name: str, symbol_type: str) -> str:
    """Deterministic ID for a symbol: hash of file:name:type."""
    raw = f'{file_path}:{name}:{symbol_type}'
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# --- Decision types ---
DECISION_TYPES = (
    'business_goal', 'arch_decision', 'task',
    'workaround', 'constraint', 'patch'
)

# --- ReasonNode statuses ---
REASON_STATUSES = (
    'proposed', 'executing', 'fulfilled',
    'rejected', 'drifted', 'abandoned'
)

# --- Source types ---
SOURCE_TYPES = (
    'manual', 'commit', 'migration',
    'inferred', 'agent-session'
)

# --- Edge types ---
EDGE_TYPES = (
    'CREATES', 'MODIFIES', 'REQUIRES',
    'DUPLICATES', 'VALIDATED_BY', 'DRIFTS_FROM'
)

# --- Drift dimensions ---
# LIVE dimensions only. Nothing reads this tuple — `check_symbol_drift` is the
# real vocabulary and `test_drift.py` asserts it from source — but it sat listing
# six names for a detector that scored three, which is the doc-drift shape this
# repo keeps paying for. Retired names still appear in STORED events and must stay
# readable: 'spec' and 'ownership' and 'test' and 'dependency' (2026-07-27 shrink),
# and 'usage' (ADR-0017). Historical rows are evidence, not schema.
DRIFT_DIMENSIONS = ('changed', 'decision')

# --- Symbol types ---
SYMBOL_TYPES = (
    'function', 'class', 'module', 'route',
    'schema', 'component', 'interface', 'type',
    'constant', 'hook'
)


@dataclass
class ReasonNode:
    """A single intent/decision that drives code changes."""

    goal: str
    owner: str
    id: str = field(default_factory=_uuid)
    decision_type: str = 'task'
    scope: list[str] = field(default_factory=list)
    agent: str | None = None
    status: str = 'proposed'
    source: str = 'manual'
    task_id: str | None = None
    parent_id: str | None = None
    # Design by Contract layer
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    fulfilled_at: str | None = None


@dataclass
class Symbol:
    """A code entity: function, class, module, etc."""

    name: str
    file_path: str
    symbol_type: str
    language: str
    id: str = ''
    signature: str | None = None
    checksum: str = ''
    created_at: str = field(default_factory=_now)

    def __post_init__(self):
        if not self.id:
            self.id = symbol_id(self.file_path, self.name, self.symbol_type)


@dataclass
class Edge:
    """A typed relationship between nodes."""

    from_id: str
    to_id: str
    edge_type: str
    id: str = field(default_factory=_uuid)
    confidence: float = 1.0
    created_at: str = field(default_factory=_now)


@dataclass
class DriftEvent:
    """Auto-generated when behavior diverges from intent."""

    symbol_id: str
    from_reason_id: str
    description: str
    id: str = field(default_factory=_uuid)
    drift_dimensions: list[str] = field(default_factory=list)
    severity: float = 0.5
    resolved: bool = False
    detected_at: str = field(default_factory=_now)
    # Dedup bookkeeping (2026-07-27). `detected_at` keeps meaning FIRST seen; a repeat
    # refreshes these instead of minting a row. See ICPGStore.create_drift_event.
    last_seen: str | None = None
    seen_count: int = 1
