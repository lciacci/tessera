"""Extractor coverage: shell + extensionless executables.

Added 2026-07-27 (active.md item 1, step 1). Before this, `symbols.py` dispatched
purely on file extension, so iCPG saw 84 of 260 code files in this repo — every
`.sh` hook and every `bin/tessera-*` was invisible to the layer built to track
intent, and 46 of 56 scope entries pointed at files it could not parse.
"""

from pathlib import Path

from .symbols import detect_language, extract_symbols

SHELL_SRC = """#!/usr/bin/env bash
set -euo pipefail

report_degraded() {
  printf '%s\\n' "$1"
}

function main {
  report_degraded "hi"
}
"""


def _write(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_dot_sh_is_detected_and_extracted(tmp_path):
    fp = _write(tmp_path, 'hook.sh', SHELL_SRC)
    assert detect_language(fp) == 'shell'
    names = {s.name for s in extract_symbols(fp)}
    assert names == {'report_degraded', 'main'}


def test_extensionless_bash_is_detected_by_shebang(tmp_path):
    fp = _write(tmp_path, 'tessera-thing', SHELL_SRC)
    assert Path(fp).suffix == ''
    assert detect_language(fp) == 'shell'
    assert {s.name for s in extract_symbols(fp)} == {'report_degraded', 'main'}


def test_extensionless_python_routes_to_the_ast_extractor(tmp_path):
    fp = _write(tmp_path, 'tessera-watch', '#!/usr/bin/env python3\ndef p3():\n    return 1\n')
    assert detect_language(fp) == 'python'
    syms = extract_symbols(fp)
    assert [s.name for s in syms] == ['p3']
    assert syms[0].language == 'python'


def test_shell_checksum_tracks_the_body_not_just_the_signature(tmp_path):
    """`changed` is the dimension that survives if `usage` is retired — it must
    see a body edit, or shell coverage is cosmetic."""
    before = extract_symbols(_write(tmp_path, 'a.sh', SHELL_SRC))[0]
    after = extract_symbols(
        _write(tmp_path, 'b.sh', SHELL_SRC.replace('"$1"', '"$1" >&2'))
    )[0]
    assert before.name == after.name == 'report_degraded'
    assert before.checksum != after.checksum


def test_extensionless_non_script_is_still_invisible(tmp_path):
    """No shebang -> no language. LICENSE and friends must not become symbols."""
    assert detect_language(_write(tmp_path, 'LICENSE', 'MIT\n')) is None
    assert detect_language(str(tmp_path / 'nonexistent')) is None


def test_unknown_shebang_is_not_guessed(tmp_path):
    assert detect_language(_write(tmp_path, 'rb-tool', '#!/usr/bin/env ruby\nx = 1\n')) is None
