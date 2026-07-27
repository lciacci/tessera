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
import os
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


def _is_local_module(module: str, _cache: dict = {}) -> bool:
    """A module that SHIPS IN THIS REPO is not a third-party dependency.

    `bin/tessera-watch` imports `doccheck`, `bin/tessera-test` imports `tessera_config`,
    `bin/tessera-authorize` imports `authorize` — all local .py siblings reached by
    `sys.path.insert`. They are stdlib-only themselves and travel with the repo, so bare
    `python3` finds them fine. A checker that cannot tell those from a missing `httpx` is a
    checker that gets switched off. (It flagged all three on its first run. This is the fix.)
    """
    if module not in _cache:
        hits = [p for p in ROOT.rglob(module + ".py") if ".venv" not in p.parts]
        _cache[module] = bool(hits)
    return _cache[module]


def _findable_by(interp: str, module: str, _cache: dict = {}) -> bool:
    """Can THIS interpreter even FIND this module?

    `find_spec`, not `import` — locating a module does not execute it.
    """
    key = (interp, module)
    if key not in _cache:
        probe = ("import importlib.util as u, sys; "
                 "sys.exit(0 if u.find_spec(%r) else 1)" % module)
        try:
            r = subprocess.run([interp, "-c", probe], capture_output=True, timeout=20)
            _cache[key] = r.returncode == 0
        except Exception:
            _cache[key] = True  # cannot probe => do not invent a failure
    return _cache[key]


def _toplevel_imports(raw: str) -> list[str]:
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return []
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return sorted(found - {"__future__"})


def check_bin_scripts_are_stdlib_only() -> list[str]:
    """`bin/` runs on bare `python3`. So `bin/` must import only what bare `python3` can find.

    ── WHY THIS EXISTS (2026-07-13, FOCUS-004) ──────────────────────────────────────────────

    `bin/deepseek`, `bin/grok` and `bin/gemini-api` are `#!/usr/bin/env python3` and
    `import httpx`. **httpx is installed nowhere** — not in the venv, not in any Homebrew
    python. All three had never run, on any machine, ever. `bin/validate-plan` called them,
    caught the ModuleNotFoundError, and scored it as a reviewer VOTING NO — so Tessera's
    council returned a confident `CHANGES_NEEDED 0/3` built entirely out of this.

    The F-001 detector (`no-bare-python3-with-toolchain-import`) did not catch it, and the
    reason is the finding: it matched against a HARDCODED SET of module names —
    `{mnemos, icpg, polyphony, skill_lint, pytest, yaml, requests}`. `httpx` was simply not
    on the list. **A blacklist of names someone has to remember to extend is not a detector;
    it is a to-do list that fails open.** Adding "httpx" to it would have fixed this one
    escape and guaranteed the next dependency escapes the same way.

    So this check does not name anything. It states the invariant literally and tests it by
    EXECUTION: bin/ is reached through a bare interpreter name, a name resolves through a
    mutable PATH, and the floor that PATH can drop to is /usr/bin/python3. Therefore every
    module bin/ imports must be findable BY THAT INTERPRETER. Anything else is F-001 waiting.

    ── THE HATCH IS PROBED, NOT TRUSTED (and this closes a hole in v1 of this check) ────────

    The documented escape is to re-exec on the venv (`_reexecs_on_venv`). v1 of this check
    treated that as proof of correctness and SKIPPED such scripts. That is the same mistake
    one level up: re-execing on the venv proves the script REACHES the venv, not that the venv
    HAS the module. `bin/build-in-public-status` re-execs on the venv and imports `httpx` —
    and **the venv does not have httpx either.** It was skipped, and it is broken.

    So there is no skip. Each script is probed against the interpreter it ACTUALLY runs on:
    a bare shebang is probed against /usr/bin/python3 (the floor a PATH can drop to); a
    venv re-exec is probed against .venv/bin/python. Same invariant, honestly applied:
    **a script must be able to find its imports on the interpreter it actually uses.**

    A script that does not even PARSE is also a failure. v1 let those through: `_toplevel_imports`
    swallows SyntaxError and returns [], so a syntactically dead file reported zero bad imports
    and looked clean. `bin/build-in-public-status` has an illegal `from __future__` after its
    re-exec preamble — it cannot have run, ever, on any interpreter — and v1 called it fine.
    """
    venv_python = str(ROOT / ".venv" / "bin" / "python")
    failures = []
    for script in sorted((ROOT / "bin").glob("*")):
        if not script.is_file():
            continue
        try:
            raw = script.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if not _is_python(script, raw):
            continue

        # A bin/ script that will not COMPILE has never run. Silence here is not cleanliness.
        #
        # `compile()`, NOT `ast.parse()`. ast.parse uses PyCF_ONLY_AST and happily ACCEPTS a
        # misplaced `from __future__ import annotations` — which python then refuses to run
        # ("must occur at the beginning of the file"). bin/build-in-public-status has exactly
        # that (its re-exec preamble precedes the __future__ line), and an ast.parse guard
        # called it clean. The weaker gate is the one that lets the corpse through.
        try:
            compile(raw, str(script), "exec")
        except SyntaxError as e:
            failures.append(f"bin/{script.name}: will not compile ({e.msg}, line {e.lineno}) — "
                            f"it cannot have run on ANY interpreter, ever.")
            continue

        on_venv = _reexecs_on_venv(raw)
        first = raw.splitlines()[0]
        if not on_venv and not BARE_INTERP.search(first):
            continue
        interp = venv_python if on_venv else OLDEST_PYTHON
        if on_venv and not Path(interp).exists():
            continue  # no venv built yet; install.sh's job, not ours to invent a failure

        for mod in _toplevel_imports(raw):
            if _is_local_module(mod) or _findable_by(interp, mod):
                continue
            where = ".venv/bin/python (the interpreter it re-execs onto)" if on_venv else \
                    f"{OLDEST_PYTHON} (the floor a drifting PATH can drop to)"
            failures.append(
                f"bin/{script.name}: imports `{mod}`, which {where} cannot find. "
                f"bin/ must import only what the interpreter it actually runs on already has "
                f"(CLAUDE.md). This is F-001."
            )
    return failures


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


def check_tessera_tools_are_documented() -> list[str]:
    """Every `bin/tessera-*` tool must be named somewhere in CLAUDE.md.

    CLAUDE.md's Commands section is the agent's index of what exists. A tool absent from it is
    a tool nobody reaches for — including the model that most needs it.

    Found 2026-07-22 the way six prior doc-drift bugs were found: Lorenzo asked "anything
    stale?". FIVE of eleven tools were undocumented — tessera-hooks, tessera-new-project,
    tessera-sync-harness, tessera-sync-skills, tessera-changelog — two of them written that
    same day. CLAUDE.md's standing rule is that a doc-drift bug a human finds becomes an
    assertion here; this is that assertion, and it covers the whole class rather than the five
    instances, so the next tool added cannot go undocumented quietly.
    """
    claude_md = ROOT / "CLAUDE.md"
    bindir = ROOT / "bin"
    if not claude_md.is_file() or not bindir.is_dir():
        return []
    body = claude_md.read_text()
    missing = sorted(
        t.name for t in bindir.glob("tessera-*")
        if t.is_file() and t.name not in body
    )
    if missing:
        return [f"CLAUDE.md: {len(missing)} bin/ tool(s) undocumented — "
                f"{', '.join(missing)} (add to the Commands section)"]
    return []


def check_downstream_template_names_the_findings_channel() -> list[str]:
    """The scaffolded CLAUDE.md must tell a downstream agent its findings channel exists.

    `tessera-new-project` ships docs/FINDINGS.md, and the findings contract calls it the
    downstream-to-framework channel — but until 2026-07-22 the CLAUDE.md template never
    mentioned it. A channel the agent is never told about collects nothing: shipping the file
    without the instruction is the "ship both halves" rule violated in documentation.
    """
    tpl = ROOT / "templates" / "tessera" / "CLAUDE.md.template"
    if not tpl.is_file():
        return []
    body = tpl.read_text()
    if "FINDINGS.md" not in body:
        return ["templates/tessera/CLAUDE.md.template: never mentions docs/FINDINGS.md — "
                "scaffolded projects ship a findings channel their agent is never told about"]
    return []


def check_hooks_status_really_compares_content() -> list[str]:
    """`tessera-hooks status` must actually compare bytes, since its header says it does.

    Its usage line advertised "drift check" from the start, and for weeks the command only
    compared declared-mode against how MANY local copies existed. A copy that had DIVERGED
    from the global source it shadows was invisible to it — which is the entire failure
    F-003 describes, and the observatory had already written the verdict: "a drift check
    that doesn't compare bytes isn't a drift check." The header kept claiming it anyway.

    Cost, measured: three projects ran a stale mnemos-pre-compact.sh for six days (missing an
    AttributeError guard, so a non-object payload drops the compaction event) and the tool
    whose job was to say so reported clean. Fixed 2026-07-22 — this asserts it stays fixed.
    """
    hooks = ROOT / "bin" / "tessera-hooks"
    if not hooks.is_file():
        return []
    body = hooks.read_text()
    if "CONTENT drift" not in body:
        return []          # header no longer makes the claim; nothing to hold it to
    if "cmp -s" not in body:
        return ["bin/tessera-hooks: header advertises CONTENT drift but the script performs "
                "no byte comparison (`cmp -s`) — the claim the observatory already called out"]
    return []


def check_hooks_match_templates() -> list[str]:
    """Every live hook in .claude/scripts/ must be byte-identical to its templates/ copy.

    templates/ IS the install payload `tessera-new-project` ships and the global-fallback
    source (ADR-0004). A live hook that drifts from its template silently ships the OLD
    behavior downstream. This is `tessera-watch` P1 as a COMMIT-TIME BLOCK, and the two are
    not redundant: P1 is a SessionStart advisory with no enforcement, so an edit to a live
    hook that forgot its template copy commits clean and is only flagged next session — the
    "green is only meaningful if failing it stops something" gap, one level up from P8/doc-drift.

    FOUND 2026-07-16: the `mnemos-pre-compact.sh` payload_probe fix (#7) landed in
    .claude/scripts/ but not templates/. tessera-watch caught it a session later; nothing
    caught it at commit. Same class as the doc-drift bugs — so, same remedy: a pre-commit check.
    """
    bad = []
    for hook in sorted((ROOT / ".claude" / "scripts").glob("*.sh")):
        template = ROOT / "templates" / hook.name
        if not template.exists():
            bad.append(f"templates/{hook.name}: missing — live .claude/scripts/{hook.name} has no install-payload copy")
        elif template.read_bytes() != hook.read_bytes():
            bad.append(f"templates/{hook.name}: differs from live .claude/scripts/{hook.name} — sync it, or the edit ships stale downstream")
    return bad


_HOOK_PATH_TOKEN = re.compile(r"(?:\.claude/scripts|hooks)/[A-Za-z0-9._-]+")
# A path as its OWN quoted token, tolerating a leading `./`. The `${CLAUDE_PROJECT_DIR:-.}/`
# anchor sits between the `"` and the path, so an anchored path does not match — only a bare
# `".claude/scripts/x"` or `"./.claude/scripts/x"` does.
_HOOK_PATH_QUOTED = re.compile(r'"(?:\./)?((?:\.claude/scripts|hooks)/[A-Za-z0-9._-]+)"')


def _bare_hook_paths(cmd: str) -> list[str]:
    """Cwd-relative hook paths in a command — the quoted exec form and the bare-statusLine form.

    The first cut required a `"` IMMEDIATELY before the path, so `"./.claude/scripts/x"` (a
    leading ./) slipped a check whose whole job is catching cwd-relative paths (review L3).
    This tolerates the `./`.

    DELIBERATELY NOT matched: a fully unquoted command-position path (`bash .claude/scripts/x`).
    It is indistinguishable from a path merely NAMED in a message — templates/settings.json's
    maggy hooks say `echo "… touch .claude/scripts/X to silence"`, and flagging that mention is
    a false positive (it bit the first broad version of this check). The actual-execution risk
    of an unquoted path is caught by the script self-anchor check anyway; the string-mention
    ambiguity is real, so this stays scoped to quoted/statusLine forms.
    """
    stripped = cmd.strip()
    if _HOOK_PATH_TOKEN.fullmatch(stripped):        # statusLine: whole command is a bare path
        return [stripped]
    return _HOOK_PATH_QUOTED.findall(cmd)
_SELF_ANCHOR = 'cd "$(dirname "$0")/../.."'
_SCRIPT_DIR_ANCHOR = 'cd "$SCRIPT_DIR/../.."'
_ANCHOR_GUARD = "*/.claude/scripts)"
# Hooks with no repo-relative path of their own: nothing inside them to mis-resolve.
_NO_ANCHOR_NEEDED = {"mnemos-stop-ingest.sh", "tessera-spend-guard.sh", "tessera-spend-backstop.sh"}


def check_hook_commands_are_anchored() -> list[str]:
    """Hook commands must anchor to the project root, and their scripts must self-anchor.

    A hook command inherits the SESSION's cwd, which is NOT guaranteed to be this repo — the
    Bash tool keeps cwd across calls, so one `cd ~/Claude/howler` retargets every relative
    path for the rest of the session.

    FOUND 2026-07-24, live, in this repo. A cd into a downstream persisted and: this session's
    gate log split 4/2 across two repos under one session id; the Stop hook resolved against
    howler and reported "hook script missing or not executable" for a file that existed and
    was -rwxr-xr-x (`[ -x ]` cannot tell wrong-directory from not-executable). An adversarial
    probe then planted decoys and got RETARGETED 13/13 — and from a cwd with no
    .claude/scripts, twelve of thirteen exited 0 with EMPTY OUTPUT. Only verify-scan spoke.

    BOTH halves are required and neither is sufficient. Anchoring only the command runs the
    right script, which then reads the wrong repo's files (proven: the anchored watch-surface
    still printed nothing until the script itself anchored). Anchoring only the script is
    unreachable, because the command cannot find it.
    """
    bad = []
    settings = ROOT / ".claude" / "settings.json"
    try:
        data = json.loads(settings.read_text())
    except Exception:
        return [".claude/settings.json unreadable — cannot verify hook anchoring"]

    commands = []
    sl = data.get("statusLine") or {}
    if sl.get("type") == "command":
        commands.append(("statusLine", sl.get("command", "")))
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                commands.append((event, hook.get("command", "")))

    for event, cmd in commands:
        for path in _bare_hook_paths(cmd):
            bad.append(
                f".claude/settings.json {event}: hook path \"{path}\" is cwd-relative — it "
                f'retargets to whatever repo the session cd\'d into. Use "${{CLAUDE_PROJECT_DIR:-.}}/{path}".'
            )

    for tpl in ("templates/tessera/settings.base.json", "templates/settings.json"):
        try:
            tdata = json.loads((ROOT / tpl).read_text())
        except Exception:
            bad.append(f"{tpl}: unreadable — cannot verify hook anchoring")
            continue
        tcmds = []
        tsl = tdata.get("statusLine") or {}
        if tsl.get("type") == "command":
            tcmds.append(tsl.get("command", ""))
        for groups in (tdata.get("hooks") or {}).values():
            for group in groups:
                for hook in group.get("hooks", []):
                    tcmds.append(hook.get("command", ""))
        for cmd in tcmds:
            for path in _bare_hook_paths(cmd):
                bad.append(
                    f'{tpl}: hook path "{path}" is cwd-relative — every project scaffolded '
                    f"from this template is born with the retargeting bug."
                )

    for hook in sorted((ROOT / ".claude" / "scripts").glob("*.sh")):
        if hook.name in _NO_ANCHOR_NEEDED:
            continue
        body = hook.read_text()
        if _SELF_ANCHOR not in body and _SCRIPT_DIR_ANCHOR not in body:
            bad.append(
                f".claude/scripts/{hook.name}: no project-root self-anchor — its own relative "
                f'paths resolve against the session cwd. Add cd "$(dirname "$0")/../.." after '
                f"the shebang (or after SCRIPT_DIR if the script resolves $0 itself)."
            )
        # The anchor MUST be guarded by `*/.claude/scripts)`. Unguarded, the ~/.claude/templates/
        # global-tier copy (where ../.. is $HOME) cd's every downstream hook to $HOME and silently
        # no-ops it — the exact catastrophe the anchor's own comments warn about. An unguarded cd
        # that passed this check would be "ship both halves" violated inside the check for it.
        elif _ANCHOR_GUARD not in body:
            bad.append(
                f".claude/scripts/{hook.name}: self-anchor is UNGUARDED — add the "
                f'`case ... */.claude/scripts) cd ...` guard, or the global-tier copy in '
                f"~/.claude/templates/ cd's to $HOME and silently disables every downstream hook."
            )
    return bad


# Skills a template/command tells you to load or copy, by name. Matches
# `@.claude/skills/X/…`, `~/.claude/skills/X/…`, `cp … skills/X/`, etc.
_TEMPLATE_SKILL_REF = re.compile(r"skills/([a-z][a-z0-9-]+)/")
# Legit references to skills that live only in the global registry, not skills/.
# Empty today; add a name here (with a reason) if such a case ever appears.
_TEMPLATE_SKILL_REF_ALLOWLIST: set[str] = set()


def check_template_skill_refs_exist() -> list[str]:
    """Every skill a template or command tells you to eager-load or copy must exist in skills/.

    The blind spot behind the 2026-07-17 spawn-team break: `referenced-paths-exist` only checks
    repo-relative inline-code paths, so a `@.claude/skills/X/SKILL.md` eager-load or a
    `cp ~/.claude/skills/X/` recipe (a `~/…` path, often inside a fenced block) pointing at a
    DELETED skill passed green. A kept command (`spawn-team`) silently lost its dependency and
    no check caught it — a human did. This closes that class: scan templates/ + commands/ raw
    text (fences included — the `cp` recipes live there) and assert every `skills/<name>/` it
    names exists in `skills/`.
    """
    bad = []
    for sub in ("templates", "commands"):
        base = ROOT / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            names = set(_TEMPLATE_SKILL_REF.findall(path.read_text()))
            for name in sorted(names - _TEMPLATE_SKILL_REF_ALLOWLIST):
                if not (ROOT / "skills" / name).is_dir():
                    bad.append(f"{_rel(path)}: loads/copies skills/{name}/ — not in skills/")
    return sorted(set(bad))


def check_no_phantom_global_skill_body_claim() -> list[str]:
    """No skill/doc may claim that trimmed skill content is preserved in a full-body
    `~/.claude/skills/...` copy that serves downstream apps.

    Found 2026-07-18, applying the python-TRIM read-first. The eagerly-loaded `base`
    skill asserted its cut scaffolding "survives in the GLOBAL `~/.claude/skills/base`
    copy… which retains the full body those repos actually use." Verified FALSE: the
    global copy is byte-identical to the trimmed project copy, and NO install.sh/script
    copies skill bodies out to `~/.claude/skills`. A convincing HARVEST-BEFORE-CUT claim
    pointed at an archive that does not exist — the exact deletion-safety illusion base
    itself warns about. This forbids the verbatim phrasings that make that false claim;
    the corrected note paraphrases around them, so it does not self-trip.
    """
    forbidden = re.compile(
        r"retains the full body|full body those repos|serves downstream app repos", re.I)
    bad = []
    scanned = list(_docs()) + sorted((ROOT / "skills").rglob("*.md"))
    for doc in scanned:
        # Whitespace-normalized: the original false claim was line-wrapped
        # ("retains the\nfull body"), which a per-line scan would miss.
        text = " ".join(doc.read_text().split())
        if forbidden.search(text):
            bad.append(f"{_rel(doc)}: claims skill bodies live in a global "
                       f"`~/.claude/skills` archive — no copy mechanism exists (2026-07-18)")
    return sorted(set(bad))


def check_skill_profiles_names_are_installed() -> list[str]:
    """Every skill named in templates/tessera/skill-profiles.json must exist in skills/.

    The curation map (ADR-0009) names skills to turn on per downstream profile; a name
    that points at a DELETED skill is dangling curation — it silently selects nothing.
    Sibling of `template-skill-refs-exist` for the one skill reference that isn't an
    `@`/`~/` path but a bare name in a JSON list. Added 2026-07-19 during the profiles
    tidy: catches the next skill removal that forgets to update the map. (Orphans — a
    skill installed but named in NO list — are a deliberate off-everywhere policy, not
    an error, so they are NOT flagged; only dangling names are.)
    """
    profiles = ROOT / "templates" / "tessera" / "skill-profiles.json"
    if not profiles.is_file():
        return []
    try:
        data = json.loads(profiles.read_text())
    except json.JSONDecodeError as e:
        return [f"skill-profiles.json: invalid JSON ({e})"]
    named: set[str] = set(data.get("universal", []))
    for group in ("profiles", "extensions"):
        for names in data.get(group, {}).values():
            named |= set(names)
    bad = [f"skill-profiles.json: names skills/{name}/ — not in skills/"
           for name in sorted(named) if not (ROOT / "skills" / name).is_dir()]
    return bad


def check_handoff_heading_is_current() -> list[str]:
    """active.md's newest session section must carry the surfacer's magic heading.

    `.claude/scripts/tessera-watch-surface.sh` greps `^## Handoff — pick up here`
    (first match) at SessionStart. When the heading convention drifted to
    `## ═══ SESSION` (2026-07-17), the surfacer silently fell back to the 07-12
    handoff and printed it for 8 days — a stale handoff surfaced as current is
    worse than none. Assert: the magic heading exists, and its first occurrence
    precedes any other session-block heading. Added 2026-07-20.
    """
    handoff = ROOT / "_project_specs" / "todos" / "active.md"
    if not handoff.is_file():
        return []
    lines = handoff.read_text().splitlines()
    magic = next((i for i, l in enumerate(lines)
                  if l.startswith("## Handoff — pick up here")), None)
    session = next((i for i, l in enumerate(lines)
                    if l.startswith("## ═══ SESSION")), None)
    if magic is None:
        return ["active.md: no '## Handoff — pick up here' heading — "
                "the SessionStart surfacer will print nothing (or a stale block)"]
    if session is not None and session < magic:
        return [f"active.md: a '## ═══ SESSION' block (line {session + 1}) precedes the "
                f"magic handoff heading (line {magic + 1}) — the surfacer will print a "
                f"stale handoff; retitle the newest section"]
    return []


def check_standing_patterns_are_surfaced() -> list[str]:
    """The cross-cutting lessons must be PRINTED at SessionStart, not merely written down.

    ADDED 2026-07-24. The file-anchored decision surface (ADR/observatory -> file) cannot
    reach these: they are patterns ACROSS entries, owned by no ADR, keyed to no path.
    Measured that day: only 20 of 43 observatory entries name a file at all. So the
    through-lines rode model recall — and a session re-derived a lesson the repo had already
    paid for eight times. A pointer would ride recall too; the block is printed verbatim.
    """
    bad = []
    handoff = ROOT / "_project_specs" / "todos" / "active.md"
    surfacer = ROOT / ".claude" / "scripts" / "tessera-watch-surface.sh"
    if not handoff.exists():
        return ["_project_specs/todos/active.md missing — cannot verify standing patterns"]
    text = handoff.read_text()
    first = text.find("## Handoff — pick up here")
    if first == -1:
        return []                      # handoff-heading-is-current owns that failure
    nxt = text.find("\n## ", first + 5)
    block = text[first:nxt if nxt != -1 else len(text)]
    if "### Standing patterns" not in block:
        bad.append("_project_specs/todos/active.md: newest handoff has no '### Standing "
                   "patterns' block — the cross-cutting lessons are not surfaced at SessionStart")
    if surfacer.exists() and "Standing patterns" not in surfacer.read_text():
        bad.append(".claude/scripts/tessera-watch-surface.sh: does not extract the standing-"
                   "patterns block — the section exists but nothing prints it")
    return bad


# JSON mechanisms by which a PreToolUse hook can actually reach the model. Bare stdout cannot:
# it goes to the debug log (only SessionStart/UserPromptSubmit add bare stdout to context).
_MODEL_CHANNELS = ("additionalContext", "permissionDecision", "updatedInput")
# Model-facing stdout: a python `print(` (not to stderr), or a shell echo/printf at line-start
# whose output is NOT piped or redirected away (`printf … | jq` feeds jq, not the hook's stdout).
_EMITS_STDOUT = re.compile(r"\bprint\((?![^)]*file=)|^\s*(?:echo|printf)\b(?![^\n]*[|>])", re.M)


def _executable_lines(text: str) -> str:
    """Drop full-line `#` comments. A channel or an emit named ONLY in a comment must not count:
    the check clears/flags on what the hook DOES, not what its rationale says. Review 2026-07-24
    found the channel test matched 'additionalContext' in a comment — the guard against the
    silent-hook class, silently weakened by the same class."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def check_pretooluse_hooks_reach_the_model() -> list[str]:
    """A PreToolUse hook that emits stdout must use a JSON channel, not bare stdout.

    FOUND 2026-07-24 in multi-agent review. A PreToolUse hook's plain stdout goes to the DEBUG
    LOG, not context (verified against code.claude.com/docs/en/hooks). It bit three hooks: the
    decision-surface hook built this same session, and — silently for the whole Mnemos trial —
    mnemos-pre-edit.sh (the fatigue/constraint/drift feature) and mnemos-post-compact-inject.sh
    (Layer 3 compaction recovery, which explained why its injection was "never seen reaching the
    model"). This asserts the fix holds and the class cannot recur at commit.
    """
    bad = []
    settings = ROOT / ".claude" / "settings.json"
    try:
        data = json.loads(settings.read_text())
    except Exception:
        return [".claude/settings.json unreadable — cannot verify PreToolUse hooks"]
    scripts_dir = ROOT / ".claude" / "scripts"
    for group in (data.get("hooks") or {}).get("PreToolUse", []):
        for hook in group.get("hooks", []):
            for name in re.findall(r'(?:\.claude/scripts|hooks)/([A-Za-z0-9._-]+)', hook.get("command", "")):
                script = scripts_dir / name if (scripts_dir / name).exists() else ROOT / "hooks" / name
                if not script.exists():
                    continue
                text = script.read_text()
                # Follow referenced scripts/*.py — decision-surface.sh delegates its envelope there.
                for py in re.findall(r'scripts/([A-Za-z0-9._/-]+\.py)', text):
                    ref = ROOT / "scripts" / py
                    if ref.exists():
                        text += "\n" + ref.read_text()
                code = _executable_lines(text)      # channels/emits in comments do not count
                if any(ch in code for ch in _MODEL_CHANNELS):
                    continue                      # reaches the model via a JSON channel
                # Emission checked across the .sh AND its referenced .py: a hook whose shell is
                # silent but delegates model output to a bare-print() .py is the same bug.
                if _EMITS_STDOUT.search(code):
                    bad.append(
                        f".claude/scripts/{name}: PreToolUse hook emits stdout but uses no JSON "
                        f"channel — bare stdout goes to the debug log, not the model. Emit "
                        f"hookSpecificOutput.additionalContext (or permissionDecision/updatedInput)."
                    )
    return bad


def check_decision_surface_is_wired() -> list[str]:
    """The decision surface must be wired, and every Accepted ADR must be reachable by it.

    ADDED 2026-07-24, after ADR-0004 was missed on a change it directly governs. An ADR that
    names no file cannot be surfaced by a file-keyed hook — so it will be missed the same way.
    That is a finding about the ADR, not only about the hook.
    """
    bad = []
    settings = ROOT / ".claude" / "settings.json"
    try:
        data = json.loads(settings.read_text())
    except Exception:
        return [".claude/settings.json unreadable — cannot verify the decision surface"]
    wired = any("decision-surface" in h.get("command", "")
                for g in (data.get("hooks") or {}).get("PreToolUse", [])
                for h in g.get("hooks", []))
    if not wired:
        bad.append("no PreToolUse decision-surface hook in .claude/settings.json — which ADR "
                   "governs a file is back to riding model recall")
    # The settings entry's `if [ -x SCRIPT ]` wrapper makes a missing/non-exec script a SILENT
    # no-op. Asserting only the wire (not the script) certifies a hook that may never run — the
    # vacuous-green trap this repo keeps hitting. Check the mechanism, not just the reference.
    script = ROOT / ".claude" / "scripts" / "tessera-decision-surface.sh"
    if wired and not (script.exists() and os.access(script, os.X_OK)):
        bad.append(".claude/scripts/tessera-decision-surface.sh missing or not executable — the "
                   "wired hook is a silent no-op (the `if [ -x ]` wrapper swallows it)")
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import decision_surface
        index = decision_surface.build_index()
    except Exception as exc:
        return bad + [f"scripts/decision_surface.py cannot build its index: {exc}"]
    # Only ADR entries mark an ADR reachable. Keying on every entry's first token (L4) let an
    # observatory heading starting "ADR-0004" falsely satisfy the ADR — collision, however rare.
    reachable = {e["title"].split()[0] for entries in index.values()
                 for e in entries if e["kind"] == "adr"}
    for adr in sorted((ROOT / "docs" / "adr").glob("0*.md")):
        body = adr.read_text()
        if "**Status:** Accepted" not in body:
            continue
        num = body.splitlines()[0].split(":")[0].lstrip("# ").strip()
        if num not in reachable:
            bad.append(f"docs/adr/{adr.name}: {num} is Accepted but names no repo path in "
                       f"backticks — nothing can surface it when its subject is edited")
    return bad


# The session-keyed tools that are invoked BY HAND — no hook wrapper to cd to the repo first.
# Their hook-invoked siblings (gate/scan.py, verify/scan.py, spend/*) are omitted on purpose:
# the wrapper's `cd "$(dirname "$0")/../.."` already anchors them, and that is checked by
# `hook-commands-are-anchored`. Add a file here the moment it stops being hook-invoked.
_HAND_INVOKED_SESSION_TOOLS = (
    "scripts/gate/emit.py",
    "scripts/gate/label.py",
    "scripts/gate/ratio.py",
    "scripts/gate/remap_kind.py",
    "scripts/override/emit.py",
    "scripts/mnemos/eval_correction.py",
)
# A quoted `.tessera/...` or `.mnemos/...` literal with no leading `/` — i.e. resolved against
# the cwd. `paths.logs_dir()` and the inlined `_ROOT / ".tessera" / "logs"` forms don't match:
# their segments are separate string literals, which is the point of splitting them.
_CWD_RELATIVE_STATE = re.compile(r'"\.(?:tessera|mnemos)/[^"]*"')


def check_session_logs_are_repo_anchored() -> list[str]:
    """Hand-invoked, session-keyed tools must anchor their state paths to the repo.

    `.tessera/logs/<session>.jsonl` is keyed by CLAUDE_CODE_SESSION_ID, so it belongs to the
    SESSION, not to whatever directory the tool was run from. Resolving it against the cwd is
    wrong by construction — and the Bash tool keeps cwd across calls, so a single `cd` into a
    downstream retargets every one of these for the rest of the session.

    FOUND 2026-07-24 as a 4/2 gate-log split under one session id; fixed 2026-07-26. The write
    side (emit.py) corrupts: half the events land in another repo. The READ side is worse
    because it is quiet — `ratio.py` from a foreign cwd printed a clean, well-formatted report
    of ZERO gates over ZERO sessions rather than erroring. Standing pattern #2: it did not
    break, it produced something plausible.

    NOT flagged, deliberately: `bin/tessera-*` and `tessera_config.py`. Those are repo-keyed —
    `tessera-watch` run inside a downstream SHOULD evaluate that downstream. The rule is that
    the anchor must match the key, not that cwd-relative is always wrong.
    """
    bad = []
    for rel in _HAND_INVOKED_SESSION_TOOLS:
        path = ROOT / rel
        try:
            body = path.read_text()
        except OSError:
            bad.append(f"{rel}: listed as a hand-invoked session tool but unreadable")
            continue
        for line_no, line in enumerate(body.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for hit in _CWD_RELATIVE_STATE.findall(line):
                bad.append(
                    f"{rel}:{line_no}: {hit} is cwd-relative. This tool is invoked by hand with "
                    f"no hook wrapper to cd first, and its state is session-keyed — anchor it to "
                    f"the repo (scripts/gate/paths.py, or the inlined TESSERA_ROOT form)."
                )
    return bad


HANDOFF = "_project_specs/todos/active.md"

# Figures and criteria this repo has FORMALLY RETRACTED. Each must not appear in the handoff
# without a retraction marker near it. Hand-curated on purpose: the value is that the list is
# short enough to read, and every entry names where it was retired.
#
# WHY THIS IS THE ONLY A6 CHECK THAT SHIPPED. Two other shapes were prototyped against the live
# file and BOTH were rejected on measurement, not taste:
#   · "a closed entry must name an existing path" -> 12 false positives in 13 entries. Closed
#     handoff items legitimately cite commits, ADRs and watcher predicates, not paths. The ADR
#     `Executed:` line works only because it is a STRUCTURED FIELD with a stated contract;
#     handoff prose has none.
#   · "an item closed in START HERE must be struck through in its body" -> FAILS OPEN. Scoped to
#     the newest section it found no closed-list at all, because the phrasing it keys on was
#     invented one day and the very next section did not use it. A check over unenforced prose
#     format goes quietly green.
# A6 said to say so rather than ship a noisy check. Those two shapes need a human re-read.
RETIRED_FIGURES = {
    "2010 user turns": "retracted 2026-07-26 — divided by TOOL-RESULT rows, ~19x the real count",
    "5 detections": "retracted 2026-07-26 — same bad denominator",
    "COMPACTION_MIN": "retired by ADR-0015 — P3 no longer counts compaction events",
    "≥3 non-manual": "retired by ADR-0015 — the trial watched the wrong event",
}
_RETRACTION_MARKER = re.compile(
    r"RETRACTED|SUPERSEDED|superseded|Original text|kept for the trail|"
    r"Quote nothing|RETIRED|retired|do not repeat|Do not repeat",
    re.IGNORECASE,
)
_RETRACTION_WINDOW = 4


def check_handoff_retires_its_own_figures() -> list[str]:
    """A number this repo has retracted must not read as live in the handoff.

    THE FAILURE THIS CATCHES, measured on its first run: the 2026-07-12 backlog still stated
    "Fires at ≥3 non-manual compaction_fired" as a current trigger — 15 days after ADR-0015
    retired it. A reader landing there would have believed P3 still counts to three.

    The handoff is the one document whose entire job is being TRUE ON ARRIVAL, and it is the
    only one `doccheck` can meaningfully assert on inside `_project_specs/` — that directory is
    otherwise excluded because specs describe work NOT YET BUILT, where naming an absent file is
    the point. On 2026-07-26 this file drifted four ways in a single day and nothing could see it.

    Deliberately NOT scoped to the newest section: an archived criterion stated as live is
    exactly the trap, and whole-file scope measured ZERO false positives once the one real hit
    was fixed. The cost is that retiring a figure means qualifying its old occurrences once,
    which is the intended behaviour rather than a burden.
    """
    handoff = ROOT / HANDOFF
    if not handoff.is_file():
        return [f"{HANDOFF} missing — the handoff is the SessionStart channel"]
    if not RETIRED_FIGURES:
        return ["RETIRED_FIGURES is empty — this check cannot fail, so it proves nothing"]

    lines = handoff.read_text().splitlines()
    bad = []
    for figure, why in RETIRED_FIGURES.items():
        for i, line in enumerate(lines):
            if figure not in line:
                continue
            window = "\n".join(
                lines[max(0, i - _RETRACTION_WINDOW):i + _RETRACTION_WINDOW + 1]
            )
            if not _RETRACTION_MARKER.search(window):
                bad.append(
                    f"{HANDOFF}:{i + 1}: states {figure!r} with no retraction marker "
                    f"within {_RETRACTION_WINDOW} lines — {why}"
                )
    return bad


DRIFT_MODULE = "scripts/icpg/drift.py"


def _edge_types_read_by_the_detector(text: str) -> set[str]:
    return set(re.findall(r"get_edges_(?:to|from)\([^)]*?['\"]([A-Z_]+)['\"]", text))


def _untyped_edge_reads(text: str) -> list[str]:
    """Edge reads with no edge-type argument — invisible to the producer check.

    FOUND BY FALSIFYING THIS CHECK (tessera-verify, 2026-07-27). The removed
    `_check_ownership_drift` called `store.get_edges_to(sym.id)` untyped, so it
    named no edge type, so it read as consuming nothing and passed. Re-adding it
    tripped neither this check nor the runtime tests — the one dimension caught by
    nothing. An untyped read means "every edge type", which cannot be
    producer-checked at all; the fix is to make it say which one it means.
    """
    return re.findall(
        r"get_edges_(?:to|from)\(\s*[A-Za-z_][\w.]*\s*\)", text
    )


def _edge_types_any_code_writes() -> set[str]:
    """Producers: an `edge_type='X'` write, or a declared `--edge-type` choice.

    `coverage.py` is excluded as a READER by construction (it is not scanned for
    reads), and it writes nothing, so it contributes neither side.
    """
    produced: set[str] = set()
    icpg = ROOT / "scripts" / "icpg"
    for path in sorted(icpg.glob("*.py")) if icpg.is_dir() else []:
        if path.name in ("drift.py", "test_drift.py"):
            continue  # a reader cannot vouch for itself; tests are not producers
        text = path.read_text()
        produced |= set(re.findall(r"edge_type\s*=\s*['\"]([A-Z_]+)['\"]", text))
        for block in re.findall(r"--edge-type.*?choices\s*=\s*\[([^\]]*)\]", text, re.S):
            produced |= set(re.findall(r"['\"]([A-Z_]+)['\"]", block))
    return produced


def check_drift_dimensions_have_producers() -> list[str]:
    """Every edge type `drift.py` READS must be one some code in scripts/icpg/ WRITES.

    THE BUG THIS EXISTS FOR, measured 2026-07-26: of six edge types, one was ever
    written. `REQUIRES`, `DUPLICATES`, `VALIDATED_BY` and `DRIFTS_FROM` appeared only
    in the models enum and on the read side, so the dimensions that consumed them
    scored *the emptiness of the graph* and called it drift — `test(0.30)` on 712 of
    712 stored events, `ownership` and `dependency` never once firing in either
    direction. Nothing anywhere asserted that a consumed edge type had a producer,
    and that is the only reason it survived three evaluation passes.

    Standing pattern #1 says to ask what would tell you this check itself died. Two
    answers are built in: an empty read set is reported as a violation rather than a
    pass (a detector reading no edge types is either broken or the parser is), and
    `drift.py` is excluded from the producer scan so it can never vouch for itself.

    `coverage.py` reads VALIDATED_BY with no producer ON PURPOSE — reporting an
    absent edge as a count is the honest form of the fact that scoring it was not.
    That is why this check names one module rather than the package.
    """
    drift = ROOT / DRIFT_MODULE
    if not drift.exists():
        return [f"{DRIFT_MODULE} missing — iCPG's detector has no definition"]

    text = drift.read_text()
    read = _edge_types_read_by_the_detector(text)
    if not read:
        return [f"{DRIFT_MODULE} reads no edge type at all — either the detector "
                f"stopped detecting or this check's parser drifted; both are findings"]

    bad = [
        f"{DRIFT_MODULE}: `{call}` reads edges with no edge type, so no producer "
        f"can be checked for it — name the edge type (this is how the old "
        f"ownership dimension slipped past every guard)"
        for call in _untyped_edge_reads(text)
    ]

    produced = _edge_types_any_code_writes()
    return bad + [
        f"{DRIFT_MODULE} scores `{edge}` but nothing in scripts/icpg/ writes it — "
        f"the dimension measures the graph's emptiness, not the code (add the "
        f"producer first, or drop the dimension)"
        for edge in sorted(read - produced)
    ]


def check_chaos_suite_is_reachable() -> list[str]:
    """Every chaos probe file must be invoked by a runner that exists and is executable.

    The spec-11 probes live OUTSIDE `tessera-test` on purpose: they are legitimately RED
    until the degraded mechanism ships, and a permanently-red main suite is one people
    learn to ignore. The cost of that choice is exactly standing pattern #1 — a suite
    nothing runs is a suite that rots, and its rotting is silent.

    So this is the `ls`. It is the same shape as `ignored-test-suites-are-run`, which
    exists because a `test:` that enumerated six files reported "57 passed" all evening
    while running half the suite.

    When the mechanism lands and the probes are folded into run-tests.sh, this check keeps
    working — `pytest chaos` in run-tests.sh satisfies it just as well as bin/tessera-chaos
    does. It is about reachability, not about which runner.

    The suite sits at top-level `chaos/`, not `scripts/chaos/`: run-tests.sh's top-level run
    is `pytest scripts/`, which would collect these deliberately-red probes and fail the main
    suite. Excluding it there would instead collide with `ignored-test-suites-are-run`.
    """
    chaos = ROOT / "chaos"
    probes = sorted(chaos.glob("test_*.py")) if chaos.is_dir() else []
    if not probes:
        return []  # no chaos suite yet — nothing to keep reachable

    runners = {
        "bin/tessera-chaos": ROOT / "bin" / "tessera-chaos",
        "scripts/run-tests.sh": ROOT / "scripts" / "run-tests.sh",
    }
    invoked_by = []
    for name, path in runners.items():
        try:
            text = path.read_text()
        except OSError:
            continue
        if re.search(r"pytest\s+(?:\S+\s+)*\bchaos\b", text):
            invoked_by.append((name, path))

    if not invoked_by:
        return [f"chaos/ has {len(probes)} probe file(s) but neither "
                f"bin/tessera-chaos nor scripts/run-tests.sh runs them — the suite is "
                f"unreachable and its rotting would be silent (standing pattern #1)"]

    bad = []
    for name, path in invoked_by:
        if not os.access(path, os.X_OK):
            bad.append(f"{name} runs the chaos probes but is not executable — "
                       f"`chmod +x {name}`, or nothing can invoke it")
    return bad


def check_unrunnable_hooks_report_themselves() -> list[str]:
    """A local-only wired hook that cannot be exec'd must say so, not exit 0 in silence.

    The wired form `if [ -x "P" ]; then exec "P"; fi; exit 0` swallows a missing, typo'd, or
    non-executable script as a silent success. tess-dashboard carried a typo'd hook path, so
    that hook had NEVER run, and nothing noticed for weeks — the failure mode is not
    hypothetical and it is invisible from outside.

    THE FIXER IS scripts/hooks/report_settings.py, and this check IMPORTS its predicate rather
    than mirroring a regex. The sibling anchoring pair mirrors-plus-tests because its detector
    predates its fixer; a new pair has no reason to inherit that risk. A detector that flags
    what the fixer cannot fix (or misses what it does) is the exact asymmetry this repo keeps
    rediscovering.

    Scope is every wired hook of the recognised shape. It was once narrowed to "local-only",
    excluding ADR-0004 two-tier commands on the premise that a missing local file still resolves
    globally — but under the DEFAULT `global` distribution no local copy is ever shipped, so the
    global branch is the ONLY tier, not a redundancy. That exclusion left all 7 mnemos hooks
    fail-silent in every default downstream, and because this check imports the fixer's
    predicate, detector and fixer were blind together. Retired 2026-07-26 (criterion-5 re-read).
    """
    sys.path.insert(0, str(ROOT / "scripts" / "hooks"))
    try:
        import report_settings
    except Exception as exc:
        return [f"scripts/hooks/report_settings.py cannot be imported: {exc}"]

    bad = []
    targets = [".claude/settings.json", "templates/tessera/settings.base.json"]
    for rel in targets:
        try:
            data = json.loads((ROOT / rel).read_text())
        except Exception:
            bad.append(f"{rel}: unreadable — cannot verify hook reporting")
            continue
        for event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                for hook in group.get("hooks", []):
                    cmd = hook.get("command", "")
                    script = report_settings.needs_reporting(cmd)
                    if script:
                        bad.append(
                            f"{rel} {event}: wired hook \"{script}\" exits 0 silently when it "
                            f"cannot be exec'd — a typo'd, missing or non-executable hook is "
                            f"indistinguishable from one with nothing to say. Run "
                            f"`python3 scripts/hooks/report_settings.py {rel}`."
                        )
    return bad


def check_adr_references_resolve() -> list[str]:
    """Every `ADR-NNNN` cited in the docs must name an ADR that exists.

    Found 2026-07-26 while building the decision->amendment edge: the observatory cites
    `ADR-1244`, which is not an ADR — almost certainly a line number or figure that matched the
    pattern. Harmless in isolation, corrosive in aggregate: the amendment edge keys on exactly
    this token, so a dangling id is a decision-link that silently points at nothing, and a
    reader chasing it finds no record and cannot tell a typo from a deleted decision.

    Cheap because it is exact — a set difference between cited ids and ids on disk, no judgement.

    SCOPED TO Tessera's OWN NUMBERING (`ADR-0NNN`), and that scope is not cosmetic: the first
    version flagged `ADR-1244 (theirs)`, which is **Open GSD's** ADR, correctly cited as external
    provenance. A checker that cannot tell our decisions from someone else's would push a reader
    to "fix" a true reference. Every Tessera ADR is docs/adr/0NNN-*.md, so anything outside the
    0-range is by construction not ours to resolve.
    """
    cited: dict[str, set[str]] = {}
    for rel in ("docs/observatory.md", "docs/design-principles.md",
                "_project_specs/todos/active.md", "CLAUDE.md"):
        path = ROOT / rel
        if not path.is_file():
            continue
        for num in set(re.findall(r"ADR-(0\d{3})", path.read_text())):
            cited.setdefault(num, set()).add(rel)
    for adr in (ROOT / "docs" / "adr").glob("0*.md"):
        for num in set(re.findall(r"ADR-(0\d{3})", adr.read_text())):
            cited.setdefault(num, set()).add(f"docs/adr/{adr.name}")

    on_disk = {p.name[:4] for p in (ROOT / "docs" / "adr").glob("0*.md")}
    return [f"ADR-{num} is cited in {', '.join(sorted(where))} but no such ADR exists in "
            f"docs/adr/ — a decision link pointing at nothing"
            for num, where in sorted(cited.items()) if num not in on_disk]



_ADR_EXECUTED = re.compile(r"^- \*\*Executed:\*\* *(.+)$", re.M)
_ADR_STATUS = re.compile(r"^- \*\*Status:\*\* *(.+)$", re.M)
_BACKTICKED = re.compile(r"`([^`]+)`")
_PATH_EXT = (".py", ".sh", ".md", ".json", ".yml", ".yaml", ".jsonl", ".toml")


def _looks_like_path(token: str) -> bool:
    """Path-shaped, not merely backticked. `bin/tessera-hooks` yes, `hook_distro` no."""
    return "/" in token or token.endswith(_PATH_EXT)


def check_adr_execution_recorded() -> list[str]:
    """Every Accepted ADR must say whether it was actually BUILT — and name artifacts
    that exist.

    An accepted ADR reads identically whether it shipped or never shipped. That gap bit
    twice on 2026-07-26: ADR-0008's cut sat unexecuted for 12 days while a session read
    the verdict and recommended acting on it, and P3's counting ran 10 days past the
    decision that superseded it. `decision_amendments.py` already surfaces when an ADR was
    REVISITED; nothing surfaced that one was decided and never done.

    This does NOT license editing ADRs. The decision text stays immutable — that is what
    stops revisionism, and it has already earned its keep (ADR-0007 is legible precisely
    because nobody rewrote it). `Executed:` is APPEND-ONLY and records a fact that did not
    exist when the decision was made.

    The artifact check is the load-bearing half. Without it `Executed:` is just another
    doc claim and drifts like every other one — which is this checker's entire subject.
    Accepted values:
        - **Executed:** not yet
        - **Executed:** n/a — <why nothing ships>
        - **Executed:** <date> — `path/one`, `path/two`
    Only Accepted ADRs are required to carry it: Proposed is undecided, Watching decided
    NOT to adopt, Superseded is history.
    """
    bad = []
    for adr in sorted((ROOT / "docs" / "adr").glob("0*.md")):
        text = adr.read_text()
        status = (_ADR_STATUS.search(text) or [None, ""])[1] if _ADR_STATUS.search(text) else ""
        if not status.strip().lower().startswith("accepted"):
            continue
        m = _ADR_EXECUTED.search(text)
        if not m:
            bad.append(f"{_rel(adr)}: Accepted but no `- **Executed:**` line — a decided-"
                       f"but-never-built ADR is indistinguishable from a shipped one")
            continue
        value = m.group(1).strip()
        if value.lower().startswith(("not yet", "n/a")):
            continue
        # Backticks also wrap IDENTIFIERS (`hook_distro`, `skillOverrides`), which are not
        # artifacts. Only path-shaped tokens are verifiable, and asserting on the rest would
        # push authors to drop backticks from real prose to appease the checker.
        # A decision whose execution is a PRUNE names paths that must NOT exist. This check
        # assumed execution always CREATES, so ADR-0014 — whose whole execution was deleting a
        # dead review stack — could not record itself honestly: every artifact it named was
        # correctly absent and read as a false claim. Found 2026-07-27 while accepting it.
        #
        # `- **Executed:** <date> — `a`, `b`; removed: `c`, `d``
        #
        # The removed half is the STRONGER assertion: it verifies the prune actually happened,
        # which is exactly the "decided but never built" gap this field exists for. Without it,
        # a cut that was recorded and never made would have been invisible.
        created_part, _, removed_part = value.partition("removed:")
        created = [p for p in _BACKTICKED.findall(created_part) if _looks_like_path(p)]
        removed = [p for p in _BACKTICKED.findall(removed_part) if _looks_like_path(p)]
        if not created and not removed:
            bad.append(f"{_rel(adr)}: Executed claims completion but names no artifact in "
                       f"backticks — nothing to verify, so nothing is proven")
        for p in created:
            if not (ROOT / p.rstrip("/")).exists():
                bad.append(f"{_rel(adr)}: Executed names `{p}`, which does not exist")
        for p in removed:
            if (ROOT / p.rstrip("/")).exists():
                bad.append(f"{_rel(adr)}: Executed says it removed `{p}`, but it is still "
                           f"on disk — the cut was recorded, not made")
    return bad

def check_tier_vocabulary_is_consistent() -> list[str]:
    """The tier list the classifier PARSES must match its own header and the router's arms.

    Found 2026-07-27, and it had already done its damage: `tier-classify-hook`'s header said
    "classifies each prompt into CLAUDE_HAIKU / CLAUDE_SONNET / CLAUDE_OPUS" while the parse
    regex, the few-shot examples, and `subagent-route-hook`'s case arms had all carried FABLE
    since it was added. Reading the header, I told Lorenzo the classifier had three tiers and
    that Fable had never shipped. He remembered otherwise and was right.

    WHY THIS ONE IS MECHANICAL, when A6 rejected two handoff checks as judgement-in-a-regex:
    the subject is not prose. It is a regex ALTERNATION (`grep -oE 'A|B|C'`) compared against
    `case` arms — two closed lists of exact strings, both machine-extractable. That is the same
    shape as `retired figures`, which shipped, and the opposite of "is this status consistent",
    which failed open.

    The header is the drifting half BY CONSTRUCTION: adding a tier means editing the prompt,
    the regex, and the router — all load-bearing, all fail loudly if wrong — while the comment
    is the one place that can rot silently. A stale comment in a routing hook is not cosmetic;
    it is read as the spec by the next person, which is exactly what happened.
    """
    hook = ROOT / "hooks" / "tier-classify-hook"
    router = ROOT / "hooks" / "subagent-route-hook"
    if not hook.exists():
        return ["hooks/tier-classify-hook missing — the tier vocabulary has no definition"]
    text = hook.read_text()

    # The parse regex is the authority: it is what actually produces a tier.
    m = re.search(r"grep -oE '([A-Z|]+)'", text)
    if not m:
        return ["hooks/tier-classify-hook: no tier-parsing `grep -oE` found — "
                "the vocabulary is no longer machine-readable, so this check is blind"]
    parsed = set(m.group(1).split("|"))

    bad = []
    header = "\n".join(text.splitlines()[:20])
    for tier in sorted(parsed):
        if f"CLAUDE_{tier}" not in header:
            bad.append(f"hooks/tier-classify-hook: parses {tier} but the header comment "
                       f"omits CLAUDE_{tier} — the comment understates the vocabulary")

    if router.exists():
        arms = set(re.findall(r"CLAUDE_([A-Z]+)\)", router.read_text()))
        for tier in sorted(parsed - arms):
            bad.append(f"hooks/subagent-route-hook: no case arm for CLAUDE_{tier}, but "
                       f"tier-classify-hook can emit it — subagents silently get no override")
    return bad


CHECKS = {
    "tier-vocabulary-is-consistent": check_tier_vocabulary_is_consistent,
    "handoff-retires-its-own-figures": check_handoff_retires_its_own_figures,
    "drift-dimensions-have-producers": check_drift_dimensions_have_producers,
    "chaos-suite-is-reachable": check_chaos_suite_is_reachable,
    "session-logs-are-repo-anchored": check_session_logs_are_repo_anchored,
    "standing-patterns-are-surfaced": check_standing_patterns_are_surfaced,
    "decision-surface-is-wired": check_decision_surface_is_wired,
    "pretooluse-hooks-reach-the-model": check_pretooluse_hooks_reach_the_model,
    "referenced-paths-exist": check_referenced_paths_exist,
    "handoff-heading-is-current": check_handoff_heading_is_current,
    "no-phantom-global-skill-body-claim": check_no_phantom_global_skill_body_claim,
    "template-skill-refs-exist": check_template_skill_refs_exist,
    "skill-profiles-names-are-installed": check_skill_profiles_names_are_installed,
    "hooks-match-templates": check_hooks_match_templates,
    "hook-commands-are-anchored": check_hook_commands_are_anchored,
    "hooks-status-compares-content": check_hooks_status_really_compares_content,
    "tessera-tools-are-documented": check_tessera_tools_are_documented,
    "template-names-findings-channel": check_downstream_template_names_the_findings_channel,
    "no-upstream-clone-instructions": check_no_upstream_clone_instructions,
    "adr-index-complete": check_adr_index_complete,
    "adr-execution-recorded": check_adr_execution_recorded,
    "compaction-threshold-qualified": check_compaction_threshold_qualified,
    "gate-recording-not-recall": check_gate_recording_not_claimed_as_recall,
    "tessera-yml-is-tracked": check_tessera_yml_is_tracked,
    "ignored-test-suites-are-run": check_ignored_test_suites_are_run,
    "spend-guard-is-wired": check_spend_guard_is_wired,
    "spend-backstop-is-wired": check_spend_backstop_is_wired,
    "verify-scan-is-wired": check_verify_scan_is_wired,
    "runtime-state-is-not-tracked": check_runtime_state_is_not_tracked,
    "no-bare-python3-with-toolchain-import": check_no_bare_python3_with_toolchain_import,
    "bin-scripts-are-stdlib-only": check_bin_scripts_are_stdlib_only,
    "safety-scripts-run-on-system-python": check_safety_scripts_run_on_the_system_python,
    "test-command-is-not-a-bare-interpreter": check_test_command_is_not_a_bare_interpreter,
    "unrunnable-hooks-report-themselves": check_unrunnable_hooks_report_themselves,
    "adr-references-resolve": check_adr_references_resolve,
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
