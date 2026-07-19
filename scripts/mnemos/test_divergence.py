"""Self-check for divergence.link_corrections / aggregate (spec 13 Phase 3).

Run from repo root: python3 -m scripts.mnemos.test_divergence

Guards the action-link derivation: a correction links to the NEAREST preceding
human prompt (the ask) and the assistant work since it (files, tools, errors),
window resets on every human prompt, and non-corrections emit nothing.
"""

from .divergence import link_corrections, aggregate


def _ask(idx, text, correction=0, ctype=None):
    return {'idx': idx, 'role': 'user', 'event_type': 'user',
            'tool_name': None, 'tool_use_id': None, 'file_path': None,
            'is_error': 0, 'text_preview': text,
            'correction_match': correction, 'correction_type': ctype}


def _tool(idx, name, file=None):
    return {'idx': idx, 'role': 'assistant', 'event_type': 'assistant',
            'tool_name': name, 'tool_use_id': f'tu{idx}', 'file_path': file,
            'is_error': 0, 'text_preview': None,
            'correction_match': 0, 'correction_type': None}


def _agent_text(idx, text):
    return {'idx': idx, 'role': 'assistant', 'event_type': 'assistant',
            'tool_name': None, 'tool_use_id': None, 'file_path': None,
            'is_error': 0, 'text_preview': text,
            'correction_match': 0, 'correction_type': None}


def _result(idx, tu, error=0):
    return {'idx': idx, 'role': 'user', 'event_type': 'user',
            'tool_name': None, 'tool_use_id': tu, 'file_path': None,
            'is_error': error, 'text_preview': None,
            'correction_match': 0, 'correction_type': None}


def _nearest_window():
    turns = [_ask(0, 'fix typo'), _tool(1, 'Edit', 'a.py'),
             _tool(2, 'Bash'), _agent_text(3, 'done'),
             _ask(4, 'no wrong file', correction=1, ctype='overreached')]
    (u,) = link_corrections(turns)
    assert u['correction_idx'] == 4
    assert u['ask_idx'] == 0 and u['ask_preview'] == 'fix typo'
    assert u['files'] == ['a.py']
    assert u['tool_counts'] == {'Edit': 1, 'Bash': 1}
    assert u['correction_type'] == 'overreached'
    assert u['last_agent_preview'] == 'done'
    assert u['had_error'] is False


def _window_resets_on_each_prompt():
    # A fresh (non-correction) prompt must reset the window: the correction
    # links to 'also do B', not the whole session.
    turns = [_ask(0, 'do A'), _tool(1, 'Edit', 'a.py'),
             _ask(2, 'also do B'), _tool(3, 'Edit', 'b.py'),
             _ask(4, 'no', correction=1)]
    (u,) = link_corrections(turns)
    assert u['ask_idx'] == 2 and u['ask_preview'] == 'also do B'
    assert u['files'] == ['b.py']


def _no_prior_ask():
    # A correction with nothing before it links to a null ask, empty action.
    (u,) = link_corrections([_ask(0, 'no undo that', correction=1)])
    assert u['ask_idx'] is None and u['files'] == []


def _errors_in_window():
    turns = [_ask(0, 'go'), _tool(1, 'Edit', 'a.py'), _result(2, 'tu1', error=1),
             _ask(3, 'you broke it', correction=1, ctype='wrong')]
    (u,) = link_corrections(turns)
    assert u['had_error'] is True and u['correction_type'] == 'wrong'


def _non_correction_emits_nothing():
    turns = [_ask(0, 'do A'), _tool(1, 'Edit', 'a.py'), _ask(2, 'thanks')]
    assert link_corrections(turns) == []


def _aggregate_rollup():
    turns = [
        _ask(0, 'a'), _tool(1, 'Edit', 'x.py'),
        _ask(2, 'no', correction=1, ctype='overreached'),
        _tool(3, 'Write', 'x.py'), _result(4, 'tu3', error=1),
        _ask(5, 'no', correction=1, ctype='overreached'),
        _tool(6, 'Bash'), _ask(7, 'no', correction=1, ctype='wrong'),
        _tool(8, 'Edit', 'y.py'), _ask(9, 'no', correction=1),  # untyped
    ]
    agg = aggregate(link_corrections(turns))
    assert agg['overreached']['count'] == 2
    assert agg['overreached']['errors'] == 1
    assert agg['overreached']['tools'] == {'Edit': 1, 'Write': 1}
    assert agg['overreached']['files'] == {'x.py': 2}
    assert agg['wrong']['count'] == 1
    assert agg['untyped']['count'] == 1


def demo() -> None:
    _nearest_window()
    _window_resets_on_each_prompt()
    _no_prior_ask()
    _errors_in_window()
    _non_correction_emits_nothing()
    _aggregate_rollup()
    print("ok")


if __name__ == "__main__":
    demo()
