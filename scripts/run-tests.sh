#!/bin/bash
# Tessera's full test suite. The command `.tessera/config.yml` points `tessera-test` at.
#
# WHY THIS SCRIPT EXISTS — and it is not a style preference:
#
# On 2026-07-11 `.tessera/config.yml` shipped a `test:` that ENUMERATED six test files. It
# reported "57 passed" and I quoted that all evening as if it meant the suite was green. It
# ran 6 of 12 real test files. The gate backstop's 17 tests and override's 13 never ran, and
# mnemos's 3 self-checks are run by nobody at all. **That is precisely the failure
# `bin/tessera-test` was written to prevent — a green exit that did not run the tests** — and
# it shipped inside the tool built to prevent it.
#
# Root cause: `scripts/gate/` and `scripts/override/` BOTH contain `emit.py` and `scan.py`.
# With no packages, pytest prepends each test file's directory to sys.path, so `import emit`
# binds to whichever suite collected first and the other fails collection. I dodged it by
# listing files, which silently dropped the colliding suites. The backlog had already named
# the trigger for fixing this — "next time anything needs a single green-suite command (CI,
# **a pre-commit gate**, ...)" — and I built a pre-commit gate today without noticing it fired.
#
# THE FIX HERE IS PROCESS ISOLATION, NOT NAMESPACING. Separate pytest processes get separate
# sys.modules, so the collision cannot happen. Proper namespacing (packages + qualified
# imports) is the deeper fix and is DEFERRED on purpose: `python3 scripts/gate/emit.py` is the
# invocation documented in four repos' CLAUDE.md and in the gate-event contract, and
# packagifying breaks that bare same-directory import contract. That is a real migration, not
# an 11pm change. See _project_specs/todos/active.md.
#
# The important property: **every test now runs, and a failure anywhere fails this script.**
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

# THE INTERPRETER IS A PATH, NOT A NAME. This line used to read `python3.13`, and on
# 2026-07-12 `uv python install` shimmed that very name into ~/.local/bin — ahead of
# Homebrew on PATH — so `python3.13` silently became a DIFFERENT interpreter, one with no
# pytest. The suite broke instantly. That is F-001's exact shape (a name re-pointing under
# you), and it happened *during the session that was fixing F-001*.
#
# A name is a lookup through a mutable, ordered PATH that four package managers write to.
# A path is a path. There is no fallback to `python3` on purpose: a silent fallback to a
# toolchain-less interpreter is how F-001 stayed invisible for weeks. Fail loudly instead.
PY="${TESSERA_PYTHON:-$PWD/.venv/bin/python}"
if [ ! -x "$PY" ]; then
    echo "FATAL: no toolchain interpreter at $PY" >&2
    echo "       Run ./install.sh to build the venv (uv-managed; see docs/observatory.md F-001)." >&2
    exit 1
fi
fail=0

run() {
    local label="$1"; shift
    if "$@" >/tmp/tessera-tests.$$ 2>&1; then
        printf "  ✓ %-14s %s\n" "$label" "$(grep -oE '[0-9]+ passed' /tmp/tessera-tests.$$ | tail -1)"
    else
        printf "  ✗ %-14s FAILED\n" "$label"
        cat /tmp/tessera-tests.$$
        fail=1
    fi
    rm -f /tmp/tessera-tests.$$
}

echo "Tessera test suite"
echo "──────────────────"

# Separate processes: gate/ and override/ cannot share one (see header). spend/ gets its
# own for the same reason — it has a same-dir `event.py`/`guard.py` import contract, and
# joining the pool is how the collision bites the next suite that lands.
run "top-level" "$PY" -m pytest scripts/ -q --ignore=scripts/gate --ignore=scripts/override --ignore=scripts/mnemos --ignore=scripts/spend --ignore=scripts/verify
run "gate"      "$PY" -m pytest scripts/gate -q
run "override"  "$PY" -m pytest scripts/override -q
run "spend"     "$PY" -m pytest scripts/spend -q
run "verify"    "$PY" -m pytest scripts/verify -q

# mnemos ships assert-based self-checks, not pytest tests — zero `def test_`, run via -m.
# pytest collects them as zero tests and says "no tests ran", which reads exactly like success.
for check in test_haziness test_correction test_bridge_goals; do
    run "mnemos/$check" "$PY" -m "scripts.mnemos.$check"
done

echo "──────────────────"
if [ "$fail" -ne 0 ]; then
    echo "SUITE FAILED"
    exit 1
fi
echo "suite green"
