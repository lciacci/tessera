"""Phase 3 — action-link + divergence surface (spec 13).

Ties each detected correction to the *action* it was about, producing the
doing-calibration unit: ASK -> DID -> CORRECTED(type).

    ask   = the most recent human prompt before the correction (the intent)
    did   = the assistant turns since that prompt (files, tools, errors)
    corr  = the correction turn itself (Phase 1 match + Phase 2 type)

Pure structural derivation over already-ingested `claude_turns` — no qwen, no
new schema, reconstructable any time. `link_corrections`/`aggregate` are pure
(fixture-testable, no store); `_load_turns` is the only store touch, mirroring
haziness.py's pattern.

ponytail: links a correction to the *nearest* preceding action window only. A
correction about work several turns back gets the nearest ask; honest default.
Upgrade to multi-window attribution only if the nearest window misfits in
practice. View-only — does NOT feed the haziness composite (gated on P10).
"""

from __future__ import annotations

_EDIT_TOOLS = {'Edit', 'Write', 'NotebookEdit'}


def link_corrections(turns: list[dict]) -> list[dict]:
    """Walk idx-ordered turns; emit one divergence unit per correction.

    Each human prompt closes the current action window and opens a new one; a
    correction (a human prompt with correction_match) emits a unit built from
    the window it closes, then itself becomes the next window's ask.
    """
    units: list[dict] = []
    ask: tuple = (None, None)
    action = _new_action()
    for t in turns:
        if _is_human_prompt(t):
            if t['correction_match']:
                units.append(_make_unit(t, ask, action))
            ask = (t['idx'], t['text_preview'])
            action = _new_action()
        else:
            _accumulate(action, t)
    return units


def aggregate(units: list[dict]) -> dict:
    """Flat cross-session rollup keyed by correction type: count, error count,
    summed tool usage, and files most often corrected. Deliberately thin — a
    rollup, not a dashboard; tess-dashboard owns anything richer."""
    by_type: dict = {}
    for u in units:
        key = u['correction_type'] or 'untyped'
        agg = by_type.setdefault(
            key, {'count': 0, 'errors': 0, 'tools': {}, 'files': {}})
        agg['count'] += 1
        agg['errors'] += 1 if u['had_error'] else 0
        for name, n in u['tool_counts'].items():
            agg['tools'][name] = agg['tools'].get(name, 0) + n
        for f in u['files']:
            agg['files'][f] = agg['files'].get(f, 0) + 1
    return by_type


# --- internals ----------------------------------------------------------


def _is_human_prompt(t: dict) -> bool:
    """A human-typed prompt — not a tool_result, hook feedback, or system turn.
    Same shape haziness uses for the correction denominator."""
    return (t['role'] == 'user' and t['event_type'] == 'user'
            and t['tool_use_id'] is None and t['text_preview'] is not None)


def _new_action() -> dict:
    return {'files': set(), 'tool_counts': {}, 'had_error': False,
            'last_text': None}


def _accumulate(action: dict, t: dict) -> None:
    if t['role'] == 'assistant' and t['tool_name']:
        name = t['tool_name']
        action['tool_counts'][name] = action['tool_counts'].get(name, 0) + 1
        if t['file_path']:
            action['files'].add(t['file_path'])
    elif t['role'] == 'assistant' and t['text_preview']:
        action['last_text'] = t['text_preview']
    elif t['is_error'] and t['tool_use_id']:
        action['had_error'] = True


def _make_unit(correction: dict, ask: tuple, action: dict) -> dict:
    return {
        'correction_idx': correction['idx'],
        'correction_type': correction['correction_type'],
        'correction_preview': correction['text_preview'],
        'ask_idx': ask[0],
        'ask_preview': ask[1],
        'files': sorted(action['files']),
        'tool_counts': dict(action['tool_counts']),
        'had_error': action['had_error'],
        'last_agent_preview': action['last_text'],
    }


def _load_turns(store, session_id: str) -> list[dict]:
    with store._conn() as conn:
        rows = conn.execute(
            """SELECT idx, role, event_type, tool_name, tool_use_id,
                      file_path, is_error, text_preview, correction_match,
                      correction_type
               FROM claude_turns WHERE session_id = ? ORDER BY idx ASC""",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def session_divergences(store, session_id: str) -> list[dict]:
    """Convenience: load one session's turns and link them."""
    return link_corrections(_load_turns(store, session_id))


def recent_divergences(store, limit: int) -> tuple[list[dict], int]:
    """Link corrections across the N most-recently-ingested sessions. Returns
    (units, sessions_scanned)."""
    with store._conn() as conn:
        rows = conn.execute(
            """SELECT id FROM claude_sessions
               ORDER BY last_ingested_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    units: list[dict] = []
    for r in rows:
        units.extend(session_divergences(store, r['id']))
    return units, len(rows)
