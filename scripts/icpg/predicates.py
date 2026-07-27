"""Contract-predicate evaluation.

Split out of `drift.py` on 2026-07-27. It moved because decision drift became the
detector's load-bearing dimension and its evaluator deserved a home that is not
buried under the dimension code — and because `drift.py` was over the 200-line
guideline once the shrink was documented.

The predicate forms are the ones `contracts.py` actually writes plus the two the
iCPG skill documents. An unrecognised predicate PASSES: this evaluator decides
whether to raise drift, and raising it on a form we simply cannot parse would
report a gap in the parser as a defect in the code.
"""

from __future__ import annotations

import re
from pathlib import Path

from .symbols import extract_symbols


def evaluate_predicate(predicate: str, project_dir: Path) -> bool:
    """Evaluate one structured predicate against codebase state.

    Supported:
        file_exists("path")
        test_exists("path")
        symbol_count("dir/") <= N
    """
    predicate = predicate.strip()

    for name in ('file_exists', 'test_exists'):
        target = _match_predicate(predicate, name)
        if target:
            return (project_dir / target).exists()

    sc = re.match(
        r'symbol_count\("([^"]+)"\)\s*(<=|>=|==|<|>)\s*(\d+)', predicate
    )
    if sc:
        count = _count_symbols_in_dir(project_dir / sc.group(1))
        return _compare(count, sc.group(2), int(sc.group(3)))

    return True


def _match_predicate(predicate: str, func_name: str) -> str | None:
    m = re.match(rf'{func_name}\("([^"]+)"\)', predicate)
    return m.group(1) if m else None


def _count_symbols_in_dir(dir_path: Path) -> int:
    if not dir_path.is_dir():
        return 0
    return sum(
        len(extract_symbols(str(f))) for f in dir_path.rglob('*') if f.is_file()
    )


def _compare(value: int, op: str, threshold: int) -> bool:
    ops = {
        '<=': value <= threshold,
        '>=': value >= threshold,
        '==': value == threshold,
        '<': value < threshold,
        '>': value > threshold,
    }
    return ops.get(op, True)
