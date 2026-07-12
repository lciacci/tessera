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
PY="${TESSERA_PYTHON:-python3.13}"   # NOT bare python3 — that is 3.14 here, with no pytest (F-001)
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
run "top-level" "$PY" -m pytest scripts/ -q --ignore=scripts/gate --ignore=scripts/override --ignore=scripts/mnemos --ignore=scripts/spend
run "gate"      "$PY" -m pytest scripts/gate -q
run "override"  "$PY" -m pytest scripts/override -q
run "spend"     "$PY" -m pytest scripts/spend -q

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
