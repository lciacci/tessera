#!/usr/bin/env python3
"""doccheck — assert that docs' machine-checkable claims are still true.

Six doc-drift bugs were found between 2026-07-09 and 2026-07-11, every one of them by
Lorenzo asking "all docs updated?" on a hunch. Each was fixed by hand and left no check
behind, so the next one was found the same way: the human was the detector, and suspicion
is a depleting resource. The better the framework gets, the less it gets asked — which
means drift accumulates fastest exactly when trust is highest. Trust is the failure mode.

That is a principle #17 failure one level up: the *verification* rode on recall, not a
channel. Worse, design-principles.md:560 already recorded the lesson in prose —
"when a doc claims N layers, `ls` all N" — and the `ls` was never built. A prose lesson
is the exact thing #17 says does not work; it then failed five more times.

This is the `ls`. It does NOT try to keep prose in sync with code (unbounded, AI-complete).
It checks the narrow tractable class that covers all six real bugs: **a doc asserts
something checkable about the repo, and nothing checks it.**

Surfaced by tessera-watch P8 (SessionStart) — a non-model channel, per #17.

STANDING RULE: every doc-drift bug a human finds becomes an assertion here. If one is ever
found that has no matching check, that is a finding about *this file*, not just the doc —
it is how we learn the assertion set has rotted into theater.

    python3 scripts/doccheck.py           # human output; exit 1 if any claim is false
    python3 scripts/doccheck.py --json    # machine output
"""
import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Docs held to their claims about THIS repo's disk state. The exclusions are not
# laziness — they are the whole design. A first cut checked every .md and produced 98
# violations, ~95% false, because four doc classes make no claim about current disk:
#   _project_specs/   specs describe work NOT YET BUILT — naming an absent file is the point
#   .claude/skills/   generic instructions for DOWNSTREAM projects, not about Tessera
#   CHANGELOG.md      historical; it correctly names files that were later deleted
#   docs/adr/         immutable record; an ADR describes the world as it was
# A checker that cries wolf gets ignored, and an ignored checker is worse than none
# because it looks like coverage. Precision over recall, deliberately.
#
# The front-door docs (README, GETTING_STARTED, NOTICE) are IN scope, added 2026-07-12.
# They were outside it until then — which is why nothing caught README naming a
# `tess-design-principles.md` that had been renamed six weeks earlier, or GETTING_STARTED
# instructing a `git clone` of the upstream Tessera had formally decoupled from (ADR-0003).
# The docs a stranger reads first were the only ones held to no claim at all. That inverts
# the moment Tessera goes public.
#
# There was briefly a third skip here, for docs/maggy-rfc.md — Maggy's product RFC, inherited
# verbatim. It is gone: the file was PRUNED (2026-07-12) rather than permanently exempted.
# That is the only honest end-state for a skip. An exemption is a decision to tolerate, and a
# tolerated exemption with no expiry is exactly how this checker rots into the theater it was
# built to prevent — so a skip should either get resolved or get deleted, never just sit.
DOC_GLOBS = ("docs/**/*.md", "CLAUDE.md", "README.md", "GETTING_STARTED.md", "NOTICE")
DOC_SKIP = ("docs/adr/",)

# A backticked token is treated as a repo path only if it starts with one of these.
REPO_DIRS = ("docs/", "scripts/", "bin/", ".claude/", "templates/", "hooks/",
             "_project_specs/", ".tessera/", "commands/", "skills/", "rules/", "agents/")

# Tokens that are illustrative, not paths: placeholders and brace-expansions.
PLACEHOLDER = re.compile(r"[{}]|/X$|NNNN|YYYY|TITLE|\.\.\.")

# Paths that legitimately aren't on disk. Every entry is a deliberate exemption with a
# reason — an unexplained allowlist is how a checker rots into theater.
PATH_ALLOWLIST = {
    # Runtime-created, never committed. spend-auth.json is MORE than uncommitted — it must
    # never be tracked (a live grant would authorize spend on every clone). The positive
    # assertion lives in check_runtime_state_is_not_tracked; this only exempts it from the `ls`.
    ".mnemos", ".tessera/logs", ".tessera/escalations", ".tessera/spend-auth.json",
    # Other repos' files. The observatory *evaluates* GSD; it doesn't claim to contain it.
    "bin/lib/state.cjs", "bin/lib/capability-registry.cjs",
    "bin/lib/capability-loader.cjs", "docs/ARCHITECTURE.md",
    ".claude/rules",
    # Claims about DOWNSTREAM projects, not about Tessera. Tessera is the framework: it
    # consumes downstreams' FINDINGS.md (see bin/tessera-findings) and does not carry one,
    # and _project_specs/session/ is the layout the base skill prescribes downstream.
    "docs/FINDINGS.md", "_project_specs/session",
    # A PATH-fallback bridge copy that lives in DOWNSTREAM repos (conclave, howler), not here.
    # Tessera reaches its own binaries through bin/. Kept only because CLAUDE.md's escalation
    # instructions name it as the fallback when tessera/bin is not on PATH.
    "scripts/tessera-escalate",
}

# Designed in docs, never built. NOT the same as a stale reference — these are promises
# the framework has not kept, and docs/design-principles.md describes them in the PRESENT
# tense, so a reader (or a future Claude) goes looking for a file that was never written.
# Parked here rather than allowlisted so the debt stays legible: either build them, or
# reword the doc to the conditional. Tracked in _project_specs/todos/active.md.
# (.tessera/config.yml graduated OUT of this set on 2026-07-11 — it was built, with one live
# consumer in bin/tessera-test. That is what a PLANNED_PATHS entry is supposed to do: get
# built, or get reworded. It should never just sit here.)
PLANNED_PATHS = {
    ".tessera/third-party-scope.yml",  # design-principles.md:726, 763 — build its CONSUMER first
    ".tessera/project.yml.template",   # design-principles.md:195 — deletion candidate, not a build
}

INLINE_CODE = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"```.*?```", re.DOTALL)

# An instruction to ACQUIRE the upstream — not merely to name it. Crediting maggy is required
# (MIT, and NOTICE does it); telling a user to clone it contradicts ADR-0003.
UPSTREAM_ACQUIRE = re.compile(r"git\s+clone\s+\S*maggy|pipx?\s+install\s+maggy", re.I)


def _docs() -> list[Path]:
    seen = {}
    for pattern in DOC_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and not _rel(path).startswith(DOC_SKIP):
                seen[path.resolve()] = path
    return sorted(seen.values())


def _strip_fences(text: str) -> str:
    """Fenced blocks hold examples and shell recipes — their paths are illustrative."""
    return FENCE.sub("", text)


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def check_referenced_paths_exist() -> list[str]:
    """THE FORMAL `ls`. Every repo path a doc names in inline code must exist on disk.

    This is design-principles.md:560's lesson, finally mechanized: "when a doc claims N
    layers, `ls` all N." It is what would have caught the phantom `mnemos-compact-recovery.sh`
    — a 167-line script named by three docs and existing in none of them, for six weeks.
    """
    bad = []
    for doc in _docs():
        for token in INLINE_CODE.findall(_strip_fences(doc.read_text())):
            token = token.strip().rstrip(".,;:)").split(":")[0]  # strip file:symbol suffixes
            if not token.startswith(REPO_DIRS) or any(c in token for c in " *?$<>|"):
                continue
            if PLACEHOLDER.search(token):
                continue
            exempt = PATH_ALLOWLIST | PLANNED_PATHS
            if any(token.rstrip("/") == p or token.startswith(p + "/") for p in exempt):
                continue
            if not (ROOT / token).exists():
                bad.append(f"{_rel(doc)}: names `{token}` — not on disk")
    return sorted(set(bad))


def check_adr_index_complete() -> list[str]:
    """Every ADR on disk is listed in the ADR index. (Found 2026-07-11: 0005 was missing.)"""
    index = ROOT / "docs" / "adr" / "README.md"
    if not index.exists():
        return ["docs/adr/README.md missing"]
    listed = index.read_text()
    bad = []
    for adr in sorted((ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        number = adr.name[:4]
        if not re.search(rf"\|\s*{number}\s*\|", listed):
            bad.append(f"docs/adr/README.md: ADR {number} ({adr.name}) on disk but not indexed")
    return bad


def check_compaction_threshold_qualified() -> list[str]:
    """Any doc stating the Mnemos trial threshold must say the events are NON-MANUAL.

    Found 3× on 2026-07-11, after the trigger-tagging fix landed. An unqualified "≥3
    compaction_fired" invites three hand-run `/compact` tests to deliver the trial's
    verdict on manufactured evidence — the P2 failure exactly. Struck-through (~~) and
    quoted lines are historical record and exempt.
    """
    threshold = re.compile(r"(≥\s*3|>=\s*3|3\+)[^\n]{0,40}compaction_fired")
    bad = []
    for doc in _docs():
        for i, line in enumerate(doc.read_text().splitlines(), 1):
            if not threshold.search(line):
                continue
            if line.lstrip().startswith((">", "~~")) or "~~" in line:
                continue  # superseded or quoted history
            if "non-manual" not in line and "*real*" not in line and "real " not in line:
                bad.append(f"{_rel(doc)}:{i}: states the ≥3 compaction_fired threshold "
                           f"without the non-manual qualifier")
    return bad


def check_gate_recording_not_claimed_as_recall() -> list[str]:
    """If the gate-scan Stop hook is wired, no doc may still say gate recording rides recall.

    Found 2026-07-11: gate-event.md still read "Reliability = the CLAUDE.md convention
    itself" long after a Stop hook backstopped it. A doc that understates a guarantee is
    as wrong as one that overstates it — it tells the reader to distrust a working channel.
    """
    settings = ROOT / ".claude" / "settings.json"
    if not settings.exists() or "tessera-gate-scan" not in settings.read_text():
        return []  # hook not wired; the recall claim would be TRUE
    stale = re.compile(r"[Rr]eliability = the CLAUDE\.md convention itself")
    return [f"{_rel(doc)}: claims gate recording rides model recall, but the gate-scan "
            f"Stop hook is wired in .claude/settings.json"
            for doc in _docs() if stale.search(doc.read_text())]


def check_tessera_yml_is_tracked() -> list[str]:
    """Every `.tessera/*.yml` is COMMITTED. Existing-on-disk is not the same as tracked.

    Found 2026-07-11, the hard way, an hour after doccheck shipped. `.tessera/config.yml` was
    written, documented as "COMMITTED, not gitignored" in four places, and **gitignored in all
    four repos** — the rule inherited from `templates/tessera/gitignore.base`, whose comment I
    corrected while never checking the rule itself. `git add -A` skipped it in silence and the
    commit message claimed otherwise. On a fresh clone the file simply would not be there, and
    the agent it exists for — one that must never guess the test command — would have nothing
    to read.

    `referenced-paths-exist` is blind to this: the path DOES exist, on my disk, forever, and
    nowhere else. **Existence is a local fact; tracked is the shared one.** A doc that says
    "committed" is asserting the second, so the second is what gets checked.
    """
    listed = subprocess.run(["git", "ls-files", ".tessera"], cwd=ROOT,
                            capture_output=True, text=True)
    if listed.returncode != 0:
        return []  # not a git repo / git unavailable — fail open
    tracked = set(listed.stdout.split())
    return [f"{_rel(f)} exists but is NOT git-tracked — a doc claims it is committed, and on "
            f"a fresh clone it would not exist"
            for f in sorted((ROOT / ".tessera").glob("*.yml"))
            if _rel(f) not in tracked]


def check_ignored_test_suites_are_run() -> list[str]:
    """Every suite `run-tests.sh` --ignores must be run separately somewhere in the file.

    THIS IS A FINDING ABOUT THE CHECKER, not just a new check. On 2026-07-11 `.tessera/config.yml`
    shipped a `test:` that enumerated six files, ran 6 of 12, and reported "57 passed" all
    evening. A human found it. It was fixed — by writing run-tests.sh — and **left no check
    behind**, which is precisely what doccheck's standing rule exists to forbid. The rule was
    violated by the commit that fixed the bug the rule was written for.

    The trap is still live: `pytest scripts/` cannot collect `gate/` and `override/` in one
    process (both carry an `emit.py`), so each must be --ignored from the top-level run AND
    given its own. --ignore it and forget the `run` line, and the suite vanishes in silence
    while the script still exits green. That is the same failure wearing a different hat, and
    it is a one-line mistake away at all times. This is the `ls`.
    """
    script = ROOT / "scripts" / "run-tests.sh"
    if not script.exists():
        return ["scripts/run-tests.sh missing — the test command has no definition"]
    text = script.read_text()
    bad = []
    for ignored in re.findall(r"--ignore=(\S+)", text):
        # The suite must be invoked on its own: as a pytest target, or (mnemos) via -m.
        as_module = ignored.replace("/", ".")
        invoked = re.search(rf"pytest\s+{re.escape(ignored)}\b", text) or \
            re.search(rf"-m\s+[\"']?{re.escape(as_module)}\.", text)
        if not invoked:
            bad.append(f"scripts/run-tests.sh: --ignore={ignored} but nothing runs it — "
                       f"the suite is silently skipped and the script still exits green")
    return bad


def check_spend_guard_is_wired() -> list[str]:
    """The spend contract claims a PreToolUse Bash hook blocks unauthorized spend. Is it wired?

    `docs/contracts/spend-authorization.md` asserts the guard is reachable from Claude Code.
    An unwired guard is worse than none: the doc says an agent cannot boot a GPU unauthorized,
    and it can. Existence is a local fact; *wired into settings.json* is the shared one — the
    same lesson as the PATH export that lived in ~/.zshrc and was invisible to the agent.
    """
    contract = ROOT / "docs" / "contracts" / "spend-authorization.md"
    if not contract.exists():
        return []  # no claim, nothing to check
    settings = ROOT / ".claude" / "settings.json"
    if not settings.exists():
        return ["docs/contracts/spend-authorization.md claims a PreToolUse hook, but "
                ".claude/settings.json does not exist"]
    try:
        hooks = json.loads(settings.read_text()).get("hooks", {}).get("PreToolUse", [])
    except json.JSONDecodeError:
        return [".claude/settings.json is not valid JSON — cannot verify the spend guard"]
    wired = any(h.get("matcher") == "Bash"
                and "tessera-spend-guard" in json.dumps(h.get("hooks", []))
                for h in hooks)
    if not wired:
        return ["docs/contracts/spend-authorization.md claims the spend guard runs on "
                "PreToolUse(Bash), but no such hook is wired in .claude/settings.json — "
                "an agent could boot a GPU with no authorization"]
    return []


# Modules that only exist in the toolchain venv. A script that imports one of these AND is
# invoked by a bare-`python3` consumer is an F-001 landmine: it resolves whatever interpreter
# owns the `python3` name today, silently finds nothing, and no-ops.
VENV_ONLY = ("mnemos", "icpg", "polyphony", "skill_lint", "pytest", "yaml", "requests")
BARE_PYTHON = re.compile(r"(?<![\w./-])python3(?![\w.])")


# Every shell file that could execute the toolchain. NOT just `.claude/scripts/*.sh` — that
# glob was the first version's scope, and it was too narrow in three separate ways at once:
# it missed `hooks/` (extensionless files), `templates/` (the install payload), and `bin/`.
# Every executable that could reach the toolchain. Each entry here was a HOLE an adversarial
# verifier walked through: `bin/*.sh` matched nothing (every file in bin/ is extensionless),
# `.githooks/` was unscoped (its pre-commit runs bare python3), repo-root `*.sh` was unscoped
# (install.sh runs bare python3), and `templates/*.sh` missed templates/tessera/ subdirs.
SHELL_SCOPE = (
    ".claude/scripts/*", "hooks/*", "bin/*", ".githooks/*",
    "templates/**/*", "scripts/*.sh", "*.sh",
)

# An interpreter named, not pathed. Matches `python`, `python3`, `python3.13` — as a command,
# ASSIGNED TO A VARIABLE (`MNEMOS_PY="python3"`), or **in a shebang**.
#
# The lookbehind excludes `/` and word chars, so `.venv/bin/python` and `/usr/bin/python3` are
# PATHS and stay green — that is the fix, and the check must not fire on it.
#
# It used to exclude `-` as well, and that was a hole: `${PY:-python3}` evaded it entirely.
# `-` is gone from the lookbehind; it stays in the LOOKAHEAD so `python3-config` (a different
# binary) still doesn't match.
BARE_INTERP = re.compile(r"(?<![\w./])python(?:3(?:\.\d+)?)?(?![\w.-])")

# A venv-only module being imported, anywhere in the file — inline, in a heredoc, in a `-c`
# body spanning fifteen lines, it does not matter. If the file names the module, it needs it.
# The leading class includes QUOTES: `python3 -c "import mnemos"` puts a `"` right before the
# import, and requiring whitespace there missed it. Caught by a test, not by inspection.
VENV_IMPORT = re.compile(
    r"""(?:^|[\s;("'])(?:import|from)\s+(mnemos|icpg|polyphony|skill_lint|pytest|yaml|requests)\b"""
    r"|-m\s+(mnemos|icpg|polyphony|skill_lint|pytest)\b"
    # Dynamic imports evade a literal `import` match. `importlib.import_module("mnemos")` and
    # `__import__("icpg")` are still imports; the verifier used exactly this to walk past v2.
    # The `\\?` is not decoration: inside a shell `-c "…"` the inner quotes are ESCAPED, so the
    # file literally contains `import_module(\"mnemos\")`. A pattern expecting a bare quote
    # walks straight past it — which it did, on the first probe.
    r"""|(?:import_module|__import__)\(\s*\\?["'](mnemos|icpg|polyphony|skill_lint|pytest|yaml)""",
    re.MULTILINE,
)

# A .py file the shell invokes. The imports that matter may live in the SCRIPT, not the hook:
# `python3 scripts/ingest.py` names no module, but ingest.py may import mnemos. v1 followed
# these; v2's rewrite dropped it and a test caught the regression immediately. Five holes
# closed, one opened — which is exactly what the regression suite is for.
PY_TARGET = re.compile(r"[\w${}/.-]*?([\w-]+\.py)\b")


def _strip_sh_comments(text: str) -> str:
    """Drop whole-line comments — BUT KEEP THE SHEBANG.

    A `python3` inside a comment explaining why we removed it is a MENTION, not an invocation
    (the same distinction the spend guard had to learn). But `#!/usr/bin/env python3` is not a
    comment in any sense that matters: **it IS the interpreter resolution.** Stripping every
    line starting with `#` deleted the shebang, so the detector was structurally blind to the
    single most common way a name gets resolved — and `hooks/plugin-trigger` was sitting there
    with `#!/usr/bin/env python3` and `import yaml` wrapped in `except Exception: pass`,
    silently discovering zero plugins under an interpreter with no yaml.

    I was stripping the exact thing I was hunting.
    """
    lines = text.splitlines()
    keep = [ln for ln in lines[1:] if not ln.lstrip().startswith("#")]
    shebang = lines[:1] if lines and lines[0].startswith("#!") else []
    return "\n".join(shebang + keep)


REEXEC = re.compile(r"execv\s*\(\s*str\(\s*_?venv", re.IGNORECASE)


def _reexecs_on_venv(raw: str) -> bool:
    """Does this module hand itself off to the venv interpreter before importing venv-only code?

    A shebang cannot hold a relative path, so `#!/usr/bin/env python3` is the only portable
    form — which means it always names an interpreter. The fix for a python script is to
    RE-EXEC on the venv, once, before the venv-only import runs. This recognises that fix; a
    checker that cannot tell a fix from the bug it demands is a checker that gets ignored.
    """
    return bool(REEXEC.search(raw)) and ".venv" in raw


def _is_python(path: Path, raw: str) -> bool:
    first = raw.splitlines()[0] if raw else ""
    return path.suffix == ".py" or ("python" in first and first.startswith("#!"))


def _python_venv_imports(raw: str) -> list[str]:
    """Venv-only modules this python file REALLY imports — AST, not text.

    The difference is the whole point. `subprocess.run([interp, "-c", "import mnemos"])` contains
    the string "import mnemos" and imports nothing. Grep cannot tell those apart; the parser can.
    """
    venv = {"mnemos", "icpg", "polyphony", "skill_lint", "pytest", "yaml", "requests"}
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return []
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return sorted(found & venv)


def _referenced_py_sources(text: str) -> str:
    """The REAL imports of every .py this shell invokes — parsed, not grepped.

    Grepping the followed source was its own false-positive engine: `.githooks/pre-commit` runs
    `python3 scripts/doccheck.py`, and doccheck's *text* is full of the words "mnemos", "icpg"
    and "pytest" (they are in its own pattern lists and error messages). Grep called that an
    import. The AST does not: doccheck imports argparse, ast, json, re, subprocess, sys.

    Returns synthetic `import X` lines so the caller's VENV_IMPORT match still works.
    """
    out = []
    for name in set(PY_TARGET.findall(text)):
        for candidate in ROOT.rglob(name):
            if ".venv" in candidate.parts:
                continue
            try:
                mods = _python_venv_imports(candidate.read_text(errors="replace"))
            except OSError:
                mods = []
            out += [f"import {m}" for m in mods]
            break
    return "\n".join(out)


def check_no_bare_python3_with_toolchain_import() -> list[str]:
    """THE F-001 DETECTOR. The venv fixes resolution; only this stops the next landmine.

    F-001: a hook invoked the toolchain through bare `python3`. Homebrew re-pointed that name
    (3.13 → 3.14, because *ollama* wanted 3.14) and every checkpoint write no-op'd for weeks,
    invisibly, confounding the entire Mnemos trial — "the graph is empty" read as *unused* when
    it meant *unreachable*.

    ── REWRITTEN 2026-07-12, TWICE, and the second time is the lesson. ──────────────────────

    v1 scanned `.claude/scripts/*.sh` LINE BY LINE, matching `python3 -c "…"` only when the
    closing quote landed on the same line. The Mnemos hooks open a **multi-line** `-c`:

        FATIGUE_ACTION=$(python3 -c "
        import sys; sys.path.insert(0, 'scripts')
        from mnemos.fatigue import compute_fatigue        ← the import is FOUR LINES DOWN

    Line 69 is just `python3 -c "`. No import on it. So v1 returned **zero hits across three
    live, wired hooks** — pre-edit (every Edit/Write), post-tool (every tool call), and
    post-compact-inject. It reported "12 checks, 0 false claims" over the exact bug it exists
    to find, and **I used that green to certify my own fix.** An independent session found it.

    *A detector you verify your fix with must be tested against the fix's own failure mode,
    or it is a mirror, not an instrument.*

    v1 was also blind to `python3.13` (its regex excluded a dotted version), to `hooks/` and
    `bin/` and `templates/` (glob too narrow), and to `MNEMOS_PY="python3"` then `"$MNEMOS_PY"`.
    It caught 1 of 5 landmines an adversarial verifier planted.

    ── So v2 does not parse shell. It asks two questions PER FILE: ──────────────────────────

        1. Does this file name an interpreter instead of pathing to one?
        2. Does this file, ANYWHERE, import a venv-only module?

    Both → landmine. Deliberately coarse. Shell is not parseable in a regex and pretending
    otherwise is what produced v1. Over-flagging costs one `.venv/bin/python`; under-flagging
    routes every checkpoint through an interpreter Homebrew can delete, silently, for weeks.

    The stdlib carve-out survives and is load-bearing: `tessera-gate-scan.sh`,
    `tessera-spend-guard.sh` and `tessera-spend-backstop.sh` run bare `python3` on purpose, so
    the safety machinery keeps working *when the venv is broken*. They import nothing venv-only,
    so they stay green — which is exactly the line this check draws.
    """
    bad = []
    seen = set()
    for pattern in SHELL_SCOPE:
        for script in sorted(ROOT.glob(pattern)):
            if not script.is_file() or script.suffix in (".json", ".md", ".yml", ".yaml", ".txt"):
                continue
            if script in seen:
                continue
            seen.add(script)
            try:
                raw = script.read_text(errors="replace")
            except OSError:
                continue

            # A PYTHON file gets parsed, not grepped. Its interpreter is the shebang, and its
            # imports are AST nodes — not every string that happens to contain the word
            # "import". `bin/tessera-watch` runs `subprocess.run([interp, "-c", "import mnemos"])`
            # as P9's PROBE: that is data, not an import, and a text rule flags it as a landmine.
            # A checker that cries wolf gets ignored, and an ignored checker is worse than none.
            if _is_python(script, raw):
                mods = _python_venv_imports(raw)
                if mods and _reexecs_on_venv(raw):
                    continue  # it re-execs onto the venv before importing — that IS the fix
                if mods and BARE_INTERP.search(raw.splitlines()[0] if raw else ""):
                    bad.append(
                        f"{_rel(script)}:1: shebang NAMES an interpreter and the module really "
                        f"imports venv-only {', '.join(mods)}. A `#!` line IS the resolution — "
                        f"whatever owns the name runs this (F-001)."
                    )
                continue

            text = _strip_sh_comments(raw)
            if not BARE_INTERP.search(text):
                continue
            # The "\n" is load-bearing: without it the shell text and the followed .py source
            # concatenate into `...ingest.pyimport mnemos`, the import is no longer at a line
            # start, and VENV_IMPORT misses it. The unit test passed anyway — its fixture body
            # happened to end in a newline. A live probe caught it. Fixtures are not reality.
            searchable = text + "\n" + _referenced_py_sources(text)
            mods = sorted({m for g in VENV_IMPORT.findall(searchable) for m in g if m})
            if not mods:
                continue  # bare python3 on stdlib-only code — correct, and deliberate
            names = sorted(set(BARE_INTERP.findall(text) or []))
            line = next((i for i, ln in enumerate(text.splitlines(), 1) if BARE_INTERP.search(ln)), 1)
            bad.append(
                f"{_rel(script)}:{line}: names an interpreter (`{'`, `'.join(n or 'python' for n in names) or 'python3'}`) "
                f"and imports venv-only {', '.join(mods)}. With PYTHONPATH/sys.path pointing at "
                f"scripts/, that does NOT fail — it SILENTLY SUCCEEDS on whatever owns the name "
                f"(F-001). Resolve the interpreter by PATH."
            )
    return bad


# A `test:` command that resolves its interpreter by NAME. `python3`, `python3.13`, `python` —
# all lookups through a mutable, ordered PATH. A repo-relative path (.venv/bin/python) is not.
NAMED_INTERPRETER = re.compile(r"^\s*(?:python3?(?:\.\d+)?)\s")


def check_test_command_is_not_a_bare_interpreter() -> list[str]:
    """`.tessera/config.yml`'s `test:` must not resolve an interpreter by NAME.

    FOUND BY LORENZO, NOT BY THIS CHECKER (2026-07-12) — which makes it a finding about the
    checker. `no-bare-python3-with-toolchain-import` scanned only `.claude/scripts/*.sh`, so it
    was blind to the one place the bug actually shipped: the `test:` command. conclave carried
    `test: python3.13 -m pytest scripts/`, and when `uv python install` shimmed that name into
    ~/.local/bin ahead of Homebrew, it silently became an interpreter with no pytest. The suite
    broke. doccheck stayed green.

    Worse, `templates/tessera/config.yml.template` *advised* the broken form — it recommended
    "PATH-relative" `python3.13 -m pytest` over an absolute path. The warning against
    machine-absolute paths was right; the recommendation was the bug, and it would have handed
    the same broken command to every future project.

    The correct form is neither a bare name NOR a machine-absolute path: a **repo-relative
    path**, `.venv/bin/python -m pytest`. One interpreter, forever, on every machine.
    """
    config = ROOT / ".tessera" / "config.yml"
    if not config.exists():
        return []
    for line in config.read_text().splitlines():
        if not line.startswith("test:"):
            continue
        cmd = line[len("test:"):].strip()
        if cmd and NAMED_INTERPRETER.match(cmd):
            return [f".tessera/config.yml: `test: {cmd}` resolves its interpreter by NAME. A "
                    f"name is a lookup through a mutable PATH that several package managers "
                    f"write to (F-001). Use a repo-relative path: `.venv/bin/python -m pytest`."]
    return []


def _bare_python_target(line: str, script: Path) -> str:
    """What the bare `python3` on this line will actually execute: `-m mod`, `-c ...`, or a file.

    THE `-m` BRANCH WAS MISSING, AND IT IS THE ONLY FORM THE HOOKS ACTUALLY USE. Found by an
    independent session on 2026-07-12, verifying this work from a clean context.

    The detector parsed `python3 -c "…"` and `python3 file.py` and stopped there — so it
    returned `[]` against `PYTHONPATH=scripts python3 -m mnemos checkpoint --force`, which
    appears **sixteen times** across five Mnemos hooks. **A detector built for F-001 that
    cannot see F-001 in the place F-001 lives.** It went green while the bug sat inside the
    very hooks it was written to guard.

    And the miss was worse than a plain blind spot: `PYTHONPATH=scripts` lets ANY interpreter
    import mnemos straight from source, so the fallback did not fail — it **silently succeeded
    on an unmanaged Python**. The original F-001 failed silently (import error → no-op). This
    one *works*, on an interpreter Homebrew can re-point or delete. A silent success is
    strictly harder to detect than a silent failure, and nothing was watching for it.
    """
    module = re.search(r"python3?(?:\.\d+)?\s+-m\s+([\w.]+)", line)
    if module:
        # `-m mnemos` IS the import. No file to read, no source to inspect — the module name
        # on the command line is the whole claim.
        return f"import {module.group(1).split('.')[0]}"
    inline = re.search(r"""python3\s+-c\s+(['"])(.*?)\1""", line, re.DOTALL)
    if inline:
        return inline.group(2)
    ref = re.search(r"python3\s+\"?\$?[\w{}/.-]*?([\w-]+\.py)", line)
    if ref:
        for candidate in ROOT.rglob(ref.group(1)):
            if ".venv" not in candidate.parts:
                try:
                    return candidate.read_text()
                except OSError:
                    return ""
        return ""

    # `python3 "$TMPSCRIPT"` — a script GENERATED AT RUNTIME, usually by a heredoc earlier in
    # the same hook. There is no `.py` literal to match, so the branch above sees nothing.
    #
    # This is the THIRD form of the same bug, and it was live: mnemos-pre-compact.sh writes a
    # temp script that does `sys.path.insert(0, 'scripts')` + `from mnemos.store import …`,
    # then runs it on bare python3. Fixing only `-m` would have left it behind.
    #
    # We cannot resolve a runtime variable, so fall back to the whole hook — if this file
    # invokes bare python3 on *something* and anywhere imports a venv-only module, that is a
    # landmine. Deliberately coarse: over-flagging a hook costs one `.venv/bin/python`; a
    # missed one silently writes through an interpreter Homebrew owns.
    if re.search(r"python3\s+[\"']?\$", line):
        try:
            return script.read_text()
        except OSError:
            return ""
    return ""


# The safety machinery, which hooks run on BARE `python3` on purpose so it survives a broken
# venv. That only holds if it survives whatever `python3` turns out to BE.
SAFETY_SCRIPTS = (
    "scripts/spend/guard.py", "scripts/spend/backstop.py", "scripts/spend/authorize.py",
    "scripts/spend/event.py", "scripts/gate/scan.py", "scripts/gate/emit.py",
    "scripts/doccheck.py",
)
OLDEST_PYTHON = "/usr/bin/python3"  # macOS system python — the floor a PATH can drop you to


def check_safety_scripts_run_on_the_system_python() -> list[str]:
    """The safety machinery must run on the OLDEST python a drifting PATH can hand it.

    **THE WORST BUG OF 2026-07-12, and my own reasoning caused it.** I carved out an exception:
    the gate and spend hooks may invoke bare `python3`, because they are *stdlib-only* and must
    keep working when the venv is broken. That is half right, and the wrong half is lethal:

        **stdlib-only is NOT version-independent.**

    When the interpreter NAME drifts, the VERSION drifts with it. On a `/usr/bin`-first PATH,
    `python3` is macOS 3.9. PEP-604 annotations (`str | None`) raise TypeError at definition
    time. `guard.py` exits 1. And the hook wrapper passes that straight through as "not 2" —
    which Claude Code reads as **ALLOW**.

        healthy interpreter → unauthorized GPU boot → exit 2 → BLOCKED
        python3 == 3.9      → unauthorized GPU boot → exit 1 → *** THE GPU BOOTS ***

    The spend guard failed open. Found by an adversarial verifier, not by me, and not by any
    test — the suite runs on the venv's 3.13, where the bug is invisible. **A test that only
    ever runs on the good interpreter cannot see an interpreter bug.**

    So this check EXECUTES each safety script on the system python. Not `ast.parse` — that
    passes, because PEP-604 is syntactically valid and only explodes when evaluated. Compiling
    is not running, and the distinction is the entire bug.
    """
    if not Path(OLDEST_PYTHON).exists():
        return []  # no system python to test against — nothing to assert
    bad = []
    for name in SAFETY_SCRIPTS:
        script = ROOT / name
        if not script.exists():
            continue
        probe = subprocess.run(
            [OLDEST_PYTHON, "-c", f"import sys; sys.path.insert(0, {str(script.parent)!r}); "
                                  f"__import__({script.stem!r})"],
            capture_output=True, text=True, cwd=ROOT, env={"PATH": "/usr/bin:/bin"},
        )
        if probe.returncode != 0:
            err = (probe.stderr or "").strip().splitlines()
            bad.append(f"{name} does NOT run on {OLDEST_PYTHON} ({err[-1] if err else '?'}) — "
                       f"a hook invokes it via bare `python3`, and a /usr/bin-first PATH makes "
                       f"that 3.9. The spend guard would exit non-2, which Claude Code reads as "
                       f"ALLOW. Add `from __future__ import annotations`.")
    return bad


def check_spend_backstop_is_wired() -> list[str]:
    """The escalation contract claims a Stop hook catches undispositioned spend denials.

    The guard's deny path ends in a PROSE instruction ("raise a packet"), i.e. model recall —
    the trigger that missed ~85% of gates. The backstop is what makes it a channel. An unwired
    backstop means the docs promise a guarantee that rides recall, which is the #17 failure
    wearing the label of its own fix.
    """
    contract = ROOT / "docs" / "contracts" / "escalation.md"
    if not contract.exists() or "tessera-spend-backstop" not in contract.read_text():
        return []  # no claim, nothing to check
    settings = ROOT / ".claude" / "settings.json"
    try:
        stop = json.loads(settings.read_text()).get("hooks", {}).get("Stop", [])
    except (OSError, json.JSONDecodeError):
        return [".claude/settings.json unreadable — cannot verify the spend backstop"]
    if "tessera-spend-backstop" not in json.dumps(stop):
        return ["docs/contracts/escalation.md claims a Stop-hook backstop catches "
                "undispositioned spend denials, but no such hook is wired in "
                ".claude/settings.json — the deny path is back to riding model recall"]
    return []


def check_verify_scan_is_wired() -> list[str]:
    """Spec 12's verification contract claims a fail-LOUD Stop hook triggers the falsifier.

    The mechanism existed before the spec — it rode on a human remembering to ask. The Stop
    hook is what makes it a channel; unwired, the adversary is invocable-but-forgotten, which
    is a sentence again. And this is the ONE hook that must not fail open, so its own wiring
    is exactly the kind of claim that needs a checker.
    """
    contract = ROOT / "docs" / "contracts" / "verification-event.md"
    if not contract.exists() or "tessera-verify-scan" not in contract.read_text():
        return []  # no claim, nothing to check
    settings = ROOT / ".claude" / "settings.json"
    try:
        stop = json.loads(settings.read_text()).get("hooks", {}).get("Stop", [])
    except (OSError, json.JSONDecodeError):
        return [".claude/settings.json unreadable — cannot verify the verify-scan backstop"]
    if "tessera-verify-scan" not in json.dumps(stop):
        return ["docs/contracts/verification-event.md claims a fail-LOUD Stop-hook backstop "
                "(tessera-verify-scan), but no such hook is wired in .claude/settings.json — "
                "the one hook that must not fail open is not wired at all, and the adversary "
                "is back to riding human recall"]
    return []


# Per-session runtime state. Tracking any of these ships one machine's live state to every
# clone. `tessera-yml-is-tracked` asserts config MUST be tracked; this asserts the opposite,
# for the opposite reason. Both directions of "tracked" are claims about every clone.
RUNTIME_STATE = (".tessera/spend-auth.json", ".tessera/.spend-backstop-fires")


def check_runtime_state_is_not_tracked() -> list[str]:
    """No per-session runtime state may be committed. Two real bugs, both shipped by `git add -A`.

    1. `spend-auth.json` — a live spend authorization. Committed, it would grant spend on every
       clone, to every agent, forever, outliving its own TTL in git history. (Caught pre-ship.)
    2. `.spend-backstop-fires` — the backstop's fire counter. **SHIPPED TRACKED on 2026-07-12,
       holding the value 5 against a MAX_FIRES of 3.** Every fresh clone and every downstream
       would have inherited a backstop *already past its cap* — born disabled, and silently.
       The guard would deny a GPU boot and the backstop would never once fire to catch the
       denial going undispositioned. The safety net shipped with a hole in it, pre-torn.

    The second was committed one hour after the first was correctly gitignored. Same file, same
    directory, same failure — and the lesson did not generalize on its own. So it is a rule now:
    **existence is a local fact; tracked is the shared one** — and that cuts both ways.
    """
    listed = subprocess.run(["git", "ls-files", *RUNTIME_STATE], cwd=ROOT,
                            capture_output=True, text=True)
    if listed.returncode != 0:
        return []  # not a git repo / git unavailable — fail open
    return [f"{path} is git-tracked — per-session runtime state. Committing it ships one "
            f"machine's live state to every clone. `git rm --cached` it and add to .gitignore."
            for path in sorted(listed.stdout.split())]


def check_no_upstream_clone_instructions() -> list[str]:
    """No doc may instruct acquiring maggy. ADR-0003 decided Tessera owns its distribution.

    Found 2026-07-12, during the provenance audit before going public. ADR-0003 (accepted
    2026-06-26) shipped self-sufficiency in *code* — install.sh literally prints "no maggy
    repo required" — and never reconciled the *docs*. GETTING_STARTED.md still opened with
    `git clone https://github.com/alinaqi/maggy.git`, for six weeks, in the file a new user
    reads first. The decision was real; the front door still pointed at the old house.

    This is the narrow, checkable half of that: an *acquisition instruction* (clone, pip
    install) for the upstream. It deliberately does NOT flag plain links or prose mentions —
    NOTICE and README must name and credit maggy, and MIT requires exactly that. Attribution
    is mandatory; a setup step is a lie. Scanned WITH fences intact: the instruction lives
    inside a code block, which is precisely where _strip_fences would hide it.
    """
    bad = []
    for doc in _docs():
        for n, line in enumerate(doc.read_text().splitlines(), 1):
            if UPSTREAM_ACQUIRE.search(line):
                bad.append(f"{_rel(doc)}:{n}: instructs acquiring maggy (`{line.strip()}`) — "
                           f"ADR-0003 decided Tessera installs standalone; cite maggy, don't clone it")
    return sorted(set(bad))


CHECKS = {
    "referenced-paths-exist": check_referenced_paths_exist,
    "no-upstream-clone-instructions": check_no_upstream_clone_instructions,
    "adr-index-complete": check_adr_index_complete,
    "compaction-threshold-qualified": check_compaction_threshold_qualified,
    "gate-recording-not-recall": check_gate_recording_not_claimed_as_recall,
    "tessera-yml-is-tracked": check_tessera_yml_is_tracked,
    "ignored-test-suites-are-run": check_ignored_test_suites_are_run,
    "spend-guard-is-wired": check_spend_guard_is_wired,
    "spend-backstop-is-wired": check_spend_backstop_is_wired,
    "verify-scan-is-wired": check_verify_scan_is_wired,
    "runtime-state-is-not-tracked": check_runtime_state_is_not_tracked,
    "no-bare-python3-with-toolchain-import": check_no_bare_python3_with_toolchain_import,
    "safety-scripts-run-on-system-python": check_safety_scripts_run_on_the_system_python,
    "test-command-is-not-a-bare-interpreter": check_test_command_is_not_a_bare_interpreter,
}


def run() -> dict[str, list[str]]:
    return {name: check() for name, check in CHECKS.items()}


def render(results: dict[str, list[str]]) -> str:
    violations = [(n, v) for n, vs in results.items() for v in vs]
    if not violations:
        return f"✓ docs honest — {len(CHECKS)} checks, 0 false claims"
    lines = [f"Docs make {len(violations)} claim(s) that are no longer true:"]
    lines += [f"  🔴 [{name}] {v}" for name, v in violations]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Assert docs' checkable claims are still true.")
    ap.add_argument("--json", action="store_true", help="machine output")
    args = ap.parse_args()
    results = run()
    print(json.dumps(results, indent=2) if args.json else render(results))
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
