"""SQLite storage layer for iCPG reason graph."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .models import DriftEvent, Edge, ReasonNode, Symbol

ICPG_DIR = '.icpg'
DB_NAME = 'reason.db'


def _loads_list(raw) -> list:
    """A JSON list column, or [] if it is unreadable. One definition, every call site.

    Three places parse `drift_dimensions`; two guarded it and one did not, which is how a
    single malformed row could raise out of `get_unresolved_drift()` — taking down
    `icpg status` and `drift list`, and in the pre-edit hook path (stderr to /dev/null)
    taking down the drift surface SILENTLY. Three copies of a guard is how the odd one out
    goes missing, so there is now one.

    **THE DOCSTRING SAID "three call sites" WHILE FOUR MORE SAT UNGUARDED** — `_row_to_reason`
    parsed `scope`, `preconditions`, `postconditions` and `invariants` with raw `json.loads`
    (found 2026-08-10, adjacent to an arbiter finding whose stated mechanism was wrong).
    A NULL or malformed column there raises `TypeError`/`ValueError` out of `list_reasons()`,
    which is on the checkpoint path, the pre-edit hook path and `icpg query` — the same
    silent-surface failure this helper was written for, in the reader next door. The count
    in a docstring is itself a claim that drifts; it now names the property instead.
    """
    try:
        value = json.loads(raw or '[]')
    except (ValueError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _opt(row: sqlite3.Row, column: str):
    """A column that may be absent on a row read before the migration ran."""
    try:
        return row[column]
    except (IndexError, KeyError):
        return None

SCHEMA = """
CREATE TABLE IF NOT EXISTS reasons (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    decision_type TEXT DEFAULT 'task',
    scope TEXT DEFAULT '[]',
    owner TEXT NOT NULL,
    agent TEXT,
    status TEXT DEFAULT 'proposed',
    source TEXT DEFAULT 'manual',
    task_id TEXT,
    parent_id TEXT REFERENCES reasons(id),
    preconditions TEXT DEFAULT '[]',
    postconditions TEXT DEFAULT '[]',
    invariants TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    fulfilled_at TEXT
);

CREATE TABLE IF NOT EXISTS symbols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    language TEXT NOT NULL,
    signature TEXT,
    checksum TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drift_events (
    id TEXT PRIMARY KEY,
    symbol_id TEXT NOT NULL,
    from_reason_id TEXT NOT NULL,
    drift_dimensions TEXT DEFAULT '[]',
    severity REAL DEFAULT 0.5,
    description TEXT,
    resolved INTEGER DEFAULT 0,
    detected_at TEXT NOT NULL,
    last_seen TEXT,
    seen_count INTEGER DEFAULT 1,
    drift_dimensions_key TEXT,
    -- ADR-0016: `resolved` means the drift was REAL and the code or intent was fixed.
    -- `dismissed` means it was never real — a detector false positive. Kept distinct
    -- because dismissal counts per dimension are the only evidence able to say whether a
    -- dimension is miscalibrated, which is the open question about `usage`.
    dismissed INTEGER DEFAULT 0,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
-- One edge per (from, to, type). DECLARED HERE, beside its siblings, not buried in
-- a migration helper: a reader of this table's definition is exactly who needs to
-- see that `INSERT OR IGNORE` means something, and the absence of that line here is
-- how the duplicate defect was introduced. `init_db()` early-returns from _migrate
-- before reaching the collapse helper, so a freshly-init'd database used to have the
-- schema and NO unique index — anything writing to it inserted duplicates freely.
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_triple
    ON edges(from_id, to_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_drift_symbol ON drift_events(symbol_id);
CREATE INDEX IF NOT EXISTS idx_drift_resolved ON drift_events(resolved);
CREATE INDEX IF NOT EXISTS idx_reasons_status ON reasons(status);
"""


class ICPGStore:
    """SQLite-backed storage for the iCPG reason graph."""

    def __init__(self, project_dir: str = '.'):
        self.project_dir = Path(project_dir).resolve()
        self.icpg_dir = self.project_dir / ICPG_DIR
        self.db_path = self.icpg_dir / DB_NAME
        self._migrated = False

    def init_db(self) -> None:
        """Create .icpg/ directory and initialize schema."""
        self.icpg_dir.mkdir(parents=True, exist_ok=True)
        gitignore = self.icpg_dir / '.gitignore'
        if not gitignore.exists():
            gitignore.write_text('*\n')
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def exists(self) -> bool:
        return self.db_path.exists()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        self._migrate(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Idempotent ADD COLUMN for databases created before dedup existed.

        Run from `_conn` rather than `init_db` because `init_db` is only called by
        `icpg init`; every existing `.icpg/reason.db` would otherwise keep the old shape
        and the dedup columns would read as missing at runtime. Once per process, and a
        no-op after the first connection.
        """
        if self._migrated:
            return
        cols = {r[1] for r in conn.execute('PRAGMA table_info(drift_events)')}
        if not cols:
            # No table yet — this is init_db's own first connection, and the CREATE
            # TABLE that follows already has the columns. Deliberately does NOT set
            # `_migrated`: the next connection must re-check, or a store constructed
            # before its schema would skip the migration forever.
            return
        if 'last_seen' not in cols:
            conn.execute('ALTER TABLE drift_events ADD COLUMN last_seen TEXT')
            conn.execute('UPDATE drift_events SET last_seen = detected_at')
        if 'seen_count' not in cols:
            conn.execute(
                'ALTER TABLE drift_events ADD COLUMN seen_count INTEGER DEFAULT 1'
            )
        if 'drift_dimensions_key' not in cols:
            conn.execute(
                'ALTER TABLE drift_events ADD COLUMN drift_dimensions_key TEXT'
            )
            self._backfill_keys(conn)
            self._collapse_existing_duplicates(conn)
        if 'dismissed' not in cols:
            conn.execute(
                'ALTER TABLE drift_events ADD COLUMN dismissed INTEGER DEFAULT 0'
            )
        if 'note' not in cols:
            conn.execute('ALTER TABLE drift_events ADD COLUMN note TEXT')
        self._dedupe_edges(conn)
        conn.commit()
        self._migrated = True

    @staticmethod
    def _dedupe_edges(conn: sqlite3.Connection) -> None:
        """One edge per (from, to, type). Collapse existing duplicates, then enforce.

        FOUND BY REVIEW 2026-07-27, an hour after `icpg-stop-record.sh` was wired.
        `create_edge` used `INSERT OR IGNORE`, which reads as deduplicating — but the
        only UNIQUE column was `id`, a fresh uuid4 per call, so the conflict clause
        could never fire. Every re-record of the same symbol appended a new row.

        Harmless while `record` was manual and had in fact never run. The recorder
        made it live: Stop fires per TURN, so a single session would have appended
        the same ~32 edges dozens of times. Measured at 995 rows / 891 distinct
        after three runs.

        This is ADR-0013's drift-backlog defect exactly — 700 rows that were 154
        distinct drifts re-inserted across 31 scans — in a second table, and the
        fix that closed it there (`drift_dimensions_key` + collapse) is the one
        applied here. Worth naming: the same bug shipped twice because the first
        fix was applied to the row it was found on, not to the pattern.
        """
        # `_migrate` runs from `_conn`, so it fires on any database this store opens
        # — including partially-built ones that have `drift_events` but no `edges`
        # yet. Guarded rather than assumed: the existing suite caught this as
        # `no such table: edges` on four tests, which is the cheap version of a
        # migration that raises on someone's real graph.
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='edges'"
        ).fetchone():
            return

        # SINGLE quotes. Double quotes around `|` are a SQLite misfeature — it
        # falls back to treating an unresolvable double-quoted identifier as a
        # string literal, and builds compiled with -DSQLITE_DQS=0 (which SQLite's
        # own docs recommend for new applications) raise `no such column: |`
        # instead. This runs from `_migrate`, i.e. from EVERY `_conn()`, so on such
        # a build the exception escapes every ICPGStore method: `icpg status`,
        # `icpg why`, the drift surface, all of it.
        dupes = conn.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT from_id || '|' || to_id || '|' "
            "|| edge_type) FROM edges"
        ).fetchone()[0]
        if dupes:
            # Keep the earliest row per triple: created_at is the honest first-seen.
            conn.execute("""
                DELETE FROM edges WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id, MIN(created_at)
                        FROM edges GROUP BY from_id, to_id, edge_type
                    )
                )
            """)
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_triple '
            'ON edges(from_id, to_id, edge_type)'
        )

    @staticmethod
    def _backfill_keys(conn: sqlite3.Connection) -> None:
        """Compute the natural key for rows written before it existed.

        In Python rather than SQL because the key is `json.dumps(sorted(dimensions))`
        and must match `_drift_key` EXACTLY — a second definition in SQL is how a fixer
        and its detector drift apart.
        """
        rows = conn.execute(
            'SELECT id, drift_dimensions FROM drift_events'
        ).fetchall()
        for row in rows:
            dims = _loads_list(row['drift_dimensions'])
            conn.execute(
                'UPDATE drift_events SET drift_dimensions_key = ? WHERE id = ?',
                (json.dumps(sorted(dims)), row['id'])
            )

    @staticmethod
    def _collapse_existing_duplicates(conn: sqlite3.Connection) -> None:
        """One-time: fold pre-existing duplicate OPEN rows into their oldest survivor.

        Dedup-on-insert alone would leave the historic duplicates stranded — a later scan
        matches ONE of them and refreshes it, and the other copies sit unreachable forever.
        The backlog would stop growing while staying unreadable, which is the failure this
        work is about, frozen rather than fixed.

        The survivor is the OLDEST row per key, so `detected_at` keeps meaning "first
        seen"; `seen_count` sums, `last_seen` takes the newest. Resolved rows are left
        alone entirely — someone adjudicated those, and merging into them would resurrect
        a closed finding.
        """
        groups: dict[tuple, list] = {}
        rows = conn.execute(
            """SELECT id, symbol_id, from_reason_id, drift_dimensions_key,
                      detected_at, last_seen, seen_count
               FROM drift_events WHERE resolved = 0
               ORDER BY detected_at ASC"""
        ).fetchall()
        for row in rows:
            key = (row['symbol_id'], row['from_reason_id'],
                   row['drift_dimensions_key'])
            groups.setdefault(key, []).append(row)

        for members in groups.values():
            if len(members) < 2:
                continue
            survivor, duplicates = members[0], members[1:]
            total = sum((m['seen_count'] or 1) for m in members)
            newest = max((m['last_seen'] or m['detected_at']) for m in members)
            conn.execute(
                'UPDATE drift_events SET seen_count = ?, last_seen = ? WHERE id = ?',
                (total, newest, survivor['id'])
            )
            conn.executemany(
                'DELETE FROM drift_events WHERE id = ?',
                [(m['id'],) for m in duplicates]
            )

    # --- ReasonNode CRUD ---

    def create_reason(self, node: ReasonNode) -> str:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO reasons
                   (id, goal, decision_type, scope, owner, agent, status,
                    source, task_id, parent_id, preconditions, postconditions,
                    invariants, created_at, fulfilled_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    node.id, node.goal, node.decision_type,
                    json.dumps(node.scope), node.owner, node.agent,
                    node.status, node.source, node.task_id, node.parent_id,
                    json.dumps(node.preconditions),
                    json.dumps(node.postconditions),
                    json.dumps(node.invariants),
                    node.created_at, node.fulfilled_at
                )
            )
        return node.id

    def get_reason(self, reason_id: str) -> ReasonNode | None:
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM reasons WHERE id = ?', (reason_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_reason(row)

    def list_reasons(self, status: str | None = None) -> list[ReasonNode]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    'SELECT * FROM reasons WHERE status = ? ORDER BY created_at',
                    (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM reasons ORDER BY created_at'
                ).fetchall()
        return [self._row_to_reason(r) for r in rows]

    def update_reason_status(
        self, reason_id: str, status: str,
        fulfilled_at: str | None = None
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                'UPDATE reasons SET status = ?, fulfilled_at = ? WHERE id = ?',
                (status, fulfilled_at, reason_id)
            )

    # --- Symbol CRUD ---

    def upsert_symbol(self, sym: Symbol) -> str:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO symbols
                   (id, name, file_path, symbol_type, language, signature,
                    checksum, created_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                    signature=excluded.signature,
                    checksum=excluded.checksum""",
                (
                    sym.id, sym.name, sym.file_path, sym.symbol_type,
                    sym.language, sym.signature, sym.checksum, sym.created_at
                )
            )
        return sym.id

    def get_symbols_for_file(self, file_path: str) -> list[Symbol]:
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT * FROM symbols WHERE file_path = ?', (file_path,)
            ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    def get_symbol_by_name(self, name: str) -> list[Symbol]:
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT * FROM symbols WHERE name = ?', (name,)
            ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    # --- Edge CRUD ---

    def create_edge(self, edge: Edge) -> str:
        """Upsert one edge per (from, to, type). Returns the SURVIVING row's id.

        Two defects the review found once the unique index made `INSERT OR IGNORE`
        actually fire — it had been inert since the table was written, so neither
        could show up before:

        1. **The return was a lie.** It returned `edge.id` unconditionally, so on an
           existing triple the caller got a uuid for a row that was never written.
           No current caller uses it (`bootstrap.py` and `__main__.py` both discard
           it), but the first one that stores it as a reference gets a dangling id
           rather than an error. Now returns the id actually in the table.

        2. **Confidence became first-writer-wins.** `bootstrap.py` writes CREATES at
           0.6 (inferred from git history); `icpg record` writes the same triple at
           1.0 (an operator asserting it). Whichever landed second was dropped, so
           an explicitly recorded edge kept the bootstrap's guess FOREVER — there is
           no other writer, so nothing could correct it. `MAX(confidence)` fixes the
           direction and is monotone: repeated recording cannot walk it back down,
           and a 0.6 re-import cannot demote a 1.0 assertion.
        """
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO edges
                   (id, from_id, to_id, edge_type, confidence, created_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(from_id, to_id, edge_type) DO UPDATE SET
                       confidence = MAX(confidence, excluded.confidence)""",
                (
                    edge.id, edge.from_id, edge.to_id,
                    edge.edge_type, edge.confidence, edge.created_at
                )
            )
            row = conn.execute(
                'SELECT id FROM edges WHERE from_id = ? AND to_id = ? '
                'AND edge_type = ?',
                (edge.from_id, edge.to_id, edge.edge_type)
            ).fetchone()
        return row['id'] if row else edge.id

    def get_edges_from(
        self, node_id: str, edge_type: str | None = None
    ) -> list[Edge]:
        with self._conn() as conn:
            if edge_type:
                rows = conn.execute(
                    'SELECT * FROM edges WHERE from_id = ? AND edge_type = ?',
                    (node_id, edge_type)
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM edges WHERE from_id = ?', (node_id,)
                ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_edges_to(
        self, node_id: str, edge_type: str | None = None
    ) -> list[Edge]:
        with self._conn() as conn:
            if edge_type:
                rows = conn.execute(
                    'SELECT * FROM edges WHERE to_id = ? AND edge_type = ?',
                    (node_id, edge_type)
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM edges WHERE to_id = ?', (node_id,)
                ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    # --- DriftEvent CRUD ---

    @staticmethod
    def _drift_key(event: DriftEvent) -> str:
        """What counts as 'the same drift'. Chosen 2026-07-27, and it is a judgement.

        NOT the description: it embeds the scores (`usage(1.00)`), so a severity that
        moved by 0.1 would mint a new row and the backlog would keep creeping — the
        defect wearing a smaller hat. A symbol drifting the same WAY is one event whose
        severity and last-seen update in place.

        Dimensions are sorted so ordering in the detector cannot fork the key.
        """
        return json.dumps(sorted(event.drift_dimensions))

    def create_drift_event(self, event: DriftEvent) -> str:
        """Record a drift, or refresh the OPEN one it repeats. Returns the surviving id.

        THE DEFECT THIS CLOSES: this used to INSERT unconditionally with a fresh UUID on
        every scan, and `mnemos-pre-edit.sh` runs a scan on every Edit/Write. 700 rows
        were ~154 distinct drifts re-inserted across 31 scans; one pair appeared 21 times.
        A counter that only climbs is indistinguishable from a broken detector, which is
        why nobody adjudicated the backlog for weeks.

        Scoped to OPEN events on purpose: a drift that was resolved and then recurs is
        NEWS, and must not be silently folded back into the row someone already closed.
        """
        key = self._drift_key(event)
        with self._conn() as conn:
            # A DISMISSED drift stays suppressed while the evidence is unchanged (ADR-0016).
            # Re-raising it every scan would re-litigate a closed ruling on every Stop —
            # conclave F-001 exactly, which this repo already paid for once and fixed with the
            # gate_disposition ledger. A severity move re-opens it; a new dimension produces a
            # different key and therefore a new row on its own.
            dismissed = conn.execute(
                """SELECT id, severity, seen_count FROM drift_events
                   WHERE dismissed = 1 AND symbol_id = ? AND from_reason_id = ?
                   AND drift_dimensions_key = ?""",
                (event.symbol_id, event.from_reason_id, key)
            ).fetchone()
            if dismissed:
                if dismissed['severity'] == event.severity:
                    conn.execute(
                        'UPDATE drift_events SET last_seen = ?, seen_count = ? WHERE id = ?',
                        (event.detected_at, (dismissed['seen_count'] or 1) + 1,
                         dismissed['id'])
                    )
                    return dismissed['id']
                # Evidence moved — the dismissal was about a different reading. Re-open the
                # SAME row rather than minting one, so the note recording why it was once
                # dismissed travels with it.
                conn.execute(
                    """UPDATE drift_events
                       SET dismissed = 0, severity = ?, description = ?, last_seen = ?,
                           seen_count = ?
                       WHERE id = ?""",
                    (event.severity, event.description, event.detected_at,
                     (dismissed['seen_count'] or 1) + 1, dismissed['id'])
                )
                return dismissed['id']

            existing = conn.execute(
                """SELECT id, seen_count FROM drift_events
                   WHERE resolved = 0 AND dismissed = 0 AND symbol_id = ?
                   AND from_reason_id = ? AND drift_dimensions_key = ?""",
                (event.symbol_id, event.from_reason_id, key)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE drift_events
                       SET severity = ?, description = ?, last_seen = ?,
                           seen_count = ?
                       WHERE id = ?""",
                    (event.severity, event.description, event.detected_at,
                     (existing['seen_count'] or 1) + 1, existing['id'])
                )
                return existing['id']

            conn.execute(
                """INSERT INTO drift_events
                   (id, symbol_id, from_reason_id, drift_dimensions,
                    drift_dimensions_key, severity, description, resolved,
                    detected_at, last_seen, seen_count)
                   VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    event.id, event.symbol_id, event.from_reason_id,
                    json.dumps(event.drift_dimensions), key, event.severity,
                    event.description, int(event.resolved), event.detected_at,
                    event.detected_at
                )
            )
        return event.id

    def get_unresolved_drift(self) -> list[DriftEvent]:
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT * FROM drift_events WHERE resolved = 0 AND dismissed = 0 '
                'ORDER BY severity DESC'
            ).fetchall()
        return [self._row_to_drift(r) for r in rows]

    def resolve_drift(self, event_id: str, note: str | None = None) -> None:
        """The drift was REAL and the code or intent was fixed."""
        with self._conn() as conn:
            conn.execute(
                'UPDATE drift_events SET resolved = 1, note = ? WHERE id = ?',
                (note, event_id)
            )

    def dismiss_drift(self, event_id: str, reason: str) -> None:
        """The drift was NEVER REAL — a detector false positive (ADR-0016).

        Distinct from `resolve` because the counts are the point: a dimension accumulating
        dismissals is miscalibrated, and that is the only evidence able to answer whether
        `usage`'s thresholds earn their place. Merging the two states would throw away the
        one signal that can retire a dimension.
        """
        with self._conn() as conn:
            conn.execute(
                'UPDATE drift_events SET dismissed = 1, note = ? WHERE id = ?',
                (reason, event_id)
            )

    def dismissals_by_dimension(self) -> dict[str, int]:
        """Why `dismissed` is its own state: the detector-quality signal, countable."""
        counts: dict[str, int] = {}
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT drift_dimensions FROM drift_events WHERE dismissed = 1'
            ).fetchall()
        for row in rows:
            for dim in _loads_list(row['drift_dimensions']):
                counts[dim] = counts.get(dim, 0) + 1
        return counts

    # --- Composite queries ---

    def get_reasons_for_file(self, file_path: str) -> list[ReasonNode]:
        """All ReasonNodes linked to symbols in a file via CREATES/MODIFIES."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT DISTINCT r.* FROM reasons r
                   JOIN edges e ON e.from_id = r.id
                   JOIN symbols s ON e.to_id = s.id
                   WHERE s.file_path = ?
                   AND e.edge_type IN ('CREATES', 'MODIFIES')""",
                (file_path,)
            ).fetchall()
        return [self._row_to_reason(r) for r in rows]

    def get_constraints_for_scope(
        self, file_paths: list[str]
    ) -> list[dict[str, Any]]:
        """Get all invariants and contracts for files in scope."""
        results = []
        for fp in file_paths:
            reasons = self.get_reasons_for_file(fp)
            for r in reasons:
                if r.invariants or r.postconditions or r.preconditions:
                    results.append({
                        'reason_id': r.id,
                        'goal': r.goal,
                        'file': fp,
                        'preconditions': r.preconditions,
                        'postconditions': r.postconditions,
                        'invariants': r.invariants
                    })
        return results

    def get_blast_radius(self, reason_id: str) -> dict[str, Any]:
        """Symbols + downstream REQUIRES reasons for a ReasonNode."""
        symbols = []
        for edge in self.get_edges_from(reason_id, 'CREATES'):
            syms = self._get_symbol(edge.to_id)
            if syms:
                symbols.append(syms)
        for edge in self.get_edges_from(reason_id, 'MODIFIES'):
            syms = self._get_symbol(edge.to_id)
            if syms:
                symbols.append(syms)

        dependent_reasons = []
        for edge in self.get_edges_to(reason_id, 'REQUIRES'):
            reason = self.get_reason(edge.from_id)
            if reason:
                dependent_reasons.append(reason)

        return {
            'reason': self.get_reason(reason_id),
            'symbols': symbols,
            'dependent_reasons': dependent_reasons,
            'symbol_count': len(symbols),
            'dependent_count': len(dependent_reasons)
        }

    def get_risk_profile(self, symbol_name: str) -> dict[str, Any]:
        """Drift score, ownership history, and status for a symbol."""
        symbols = self.get_symbol_by_name(symbol_name)
        if not symbols:
            return {'found': False, 'symbol': symbol_name}

        sym = symbols[0]
        creating_edges = self.get_edges_to(sym.id, 'CREATES')
        modifying_edges = self.get_edges_to(sym.id, 'MODIFIES')
        drift_edges = self.get_edges_from(sym.id, 'DRIFTS_FROM')

        owners = set()
        for edge in creating_edges + modifying_edges:
            reason = self.get_reason(edge.from_id)
            if reason:
                owners.add(reason.owner)

        with self._conn() as conn:
            drift_rows = conn.execute(
                'SELECT * FROM drift_events WHERE symbol_id = ? '
                'ORDER BY detected_at DESC',
                (sym.id,)
            ).fetchall()

        return {
            'found': True,
            'symbol': sym,
            'owners': list(owners),
            'modify_count': len(modifying_edges),
            'drift_events': [self._row_to_drift(r) for r in drift_rows],
            'active_drift': any(
                not self._row_to_drift(r).resolved for r in drift_rows
            )
        }

    def get_stats(self) -> dict[str, int]:
        with self._conn() as conn:
            reasons = conn.execute('SELECT COUNT(*) FROM reasons').fetchone()[0]
            symbols = conn.execute('SELECT COUNT(*) FROM symbols').fetchone()[0]
            edges = conn.execute('SELECT COUNT(*) FROM edges').fetchone()[0]
            # MUST match get_unresolved_drift's predicate. It did not until
            # 2026-07-27: this counted `resolved = 0` alone, so a DISMISSED event
            # still read as unresolved and `icpg status` disagreed with its own
            # `drift list` (224 vs 59). ADR-0016 made `dismissed` a disposition —
            # a headline that ignores it means disposing a finding changes nothing
            # anyone looks at, which is ADR-0013's only-increments counter in a
            # second function. Invisible while exactly 1 event was dismissed;
            # found when a retirement dismissed 165.
            drift = conn.execute(
                'SELECT COUNT(*) FROM drift_events '
                'WHERE resolved = 0 AND dismissed = 0'
            ).fetchone()[0]
        return {
            'reasons': reasons,
            'symbols': symbols,
            'edges': edges,
            'unresolved_drift': drift
        }

    # --- Helpers ---

    def _get_symbol(self, symbol_id: str) -> Symbol | None:
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM symbols WHERE id = ?', (symbol_id,)
            ).fetchone()
        return self._row_to_symbol(row) if row else None

    @staticmethod
    def _row_to_reason(row: sqlite3.Row) -> ReasonNode:
        return ReasonNode(
            id=row['id'],
            goal=row['goal'],
            decision_type=row['decision_type'],
            scope=_loads_list(row['scope']),
            owner=row['owner'],
            agent=row['agent'],
            status=row['status'],
            source=row['source'],
            task_id=row['task_id'],
            parent_id=row['parent_id'],
            preconditions=_loads_list(row['preconditions']),
            postconditions=_loads_list(row['postconditions']),
            invariants=_loads_list(row['invariants']),
            created_at=row['created_at'],
            fulfilled_at=row['fulfilled_at']
        )

    @staticmethod
    def _row_to_symbol(row: sqlite3.Row) -> Symbol:
        return Symbol(
            id=row['id'],
            name=row['name'],
            file_path=row['file_path'],
            symbol_type=row['symbol_type'],
            language=row['language'],
            signature=row['signature'],
            checksum=row['checksum'],
            created_at=row['created_at']
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> Edge:
        return Edge(
            id=row['id'],
            from_id=row['from_id'],
            to_id=row['to_id'],
            edge_type=row['edge_type'],
            confidence=row['confidence'],
            created_at=row['created_at']
        )

    @staticmethod
    def _row_to_drift(row: sqlite3.Row) -> DriftEvent:
        return DriftEvent(
            id=row['id'],
            symbol_id=row['symbol_id'],
            from_reason_id=row['from_reason_id'],
            drift_dimensions=_loads_list(row['drift_dimensions']),
            severity=row['severity'],
            description=row['description'],
            resolved=bool(row['resolved']),
            detected_at=row['detected_at'],
            last_seen=_opt(row, 'last_seen'),
            seen_count=_opt(row, 'seen_count') or 1,
        )
