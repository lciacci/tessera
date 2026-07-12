"""Tests for the config layer and its one consumer.

The config layer exists to answer exactly one question an agent must never GUESS at: how do
you run this project's tests? The guess is not hypothetical — `python3 -m pytest` on this
machine hits Homebrew 3.14, which has no pytest (F-001's interpreter split). A human recovers
in a second; an unsupervised agent concludes the suite is broken and acts on it.
"""
import subprocess
import sys
from pathlib import Path

import tessera_config

BIN = Path(__file__).resolve().parent.parent / "bin" / "tessera-test"


def _project(tmp_path: Path, config: str | None) -> Path:
    (tmp_path / ".tessera").mkdir()
    (tmp_path / ".tessera" / "project.yml").write_text("profile: standard\n")
    if config is not None:
        (tmp_path / ".tessera" / "config.yml").write_text(config)
    return tmp_path


def test_missing_config_is_empty_not_an_error(tmp_path):
    """Config is always optional. A missing file must never raise."""
    assert tessera_config.load(_project(tmp_path, None)) == {}


def test_parses_flat_keys(tmp_path):
    root = _project(tmp_path, "# comment\n\ntest: pytest -q\nlint: ruff check\n")
    assert tessera_config.load(root) == {"test": "pytest -q", "lint": "ruff check"}


def test_value_may_contain_colons_and_flags(tmp_path):
    """`python3.13 -m pytest scripts/` and friends must survive the parser intact."""
    root = _project(tmp_path, "test: python3.13 -m pytest scripts/ --tb=short\n")
    assert tessera_config.get(root, "test") == "python3.13 -m pytest scripts/ --tb=short"


def test_blank_value_is_absent(tmp_path):
    """The template ships `test:` blank. Blank must read as absent, not as an empty command."""
    root = _project(tmp_path, "test:\n")
    assert tessera_config.get(root, "test") is None


def test_no_pyyaml_dependency():
    """MUST parse without PyYAML. PyYAML is installed for 3.13 and ABSENT from the default
    python3 (3.14) — a config reader that dies on the default interpreter is worse than none,
    and is the exact shape of F-001."""
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.modules['yaml'] = None; "
         f"sys.path.insert(0, {str(Path(__file__).parent)!r}); "
         "import tessera_config; print('ok')"],
        capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr


# ─── bin/tessera-test — the config layer's one live consumer.
def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(BIN), *args],
                          capture_output=True, text=True, cwd=cwd)


def test_show_prints_the_command(tmp_path):
    root = _project(tmp_path, "test: echo hello\n")
    assert _run(["--show"], root).stdout.strip() == "echo hello"


def test_runs_the_command_and_forwards_exit_code(tmp_path):
    root = _project(tmp_path, "test: exit 3\n")
    assert _run([], root).returncode == 3


def test_missing_test_key_fails_LOUD(tmp_path):
    """The critical one. A green exit with no tests run is the WORST outcome: it tells an
    unsupervised agent the suite passed when it never ran. Absence must be exit != 0."""
    root = _project(tmp_path, "lint: ruff check\n")
    result = _run([], root)
    assert result.returncode != 0
    assert "no `test:`" in result.stderr


def test_outside_a_tessera_project_fails(tmp_path):
    assert _run([], tmp_path).returncode == 2


def test_runs_from_a_subdirectory(tmp_path):
    """Root is found by walking up, so hooks and agents can invoke it from anywhere."""
    root = _project(tmp_path, "test: echo hi\n")
    (root / "deep" / "nested").mkdir(parents=True)
    assert _run(["--show"], root / "deep" / "nested").stdout.strip() == "echo hi"
