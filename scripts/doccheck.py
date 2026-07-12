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
# docs/maggy-rfc.md is skipped on the same principle as docs/adr/: it makes no claim about
# THIS repo's disk. It is *Maggy's* product RFC, inherited verbatim in the fork and never
# rewritten. It is a DELETION CANDIDATE, not a permanent exemption — an unexplained skip is
# how this checker rots into the theater it was built to prevent. Pruning the inherited Maggy
# roadmap docs (this, docs/architecture-v5.md, _project_specs/phases/phase-*-maggy-*.md) is a
# call for Lorenzo, adjacent to FOCUS-004's skill audit. Surfaced 2026-07-12; unresolved.
DOC_GLOBS = ("docs/**/*.md", "CLAUDE.md", "README.md", "GETTING_STARTED.md", "NOTICE")
DOC_SKIP = ("docs/adr/", "docs/maggy-rfc.md")

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
    # assertion lives in check_spend_auth_is_not_tracked; this only exempts it from the `ls`.
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
    "docs/codex-review-v5.md",         # architecture-v5.md references a review never committed
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


def check_no_bare_python3_with_toolchain_import() -> list[str]:
    """THE F-001 DETECTOR. The venv fixes resolution; only this stops the next landmine.

    F-001: a hook invoked the toolchain through bare `python3`. Homebrew re-pointed that name
    (3.13 → 3.14, because *ollama* wanted 3.14), the import silently failed, and every
    checkpoint write no-op'd for weeks. It was invisible, and it confounded the entire Mnemos
    kill/keep trial — "the graph is empty" read as "unused" when it meant "unreachable".

    **A venv does not prevent anyone writing `python3` in a new script tomorrow.** The venv is
    the mechanism; this is the guardrail. It is why `guard.py`, `backstop.py`, `emit.py`,
    `scan.py` and this file are deliberately stdlib-only — that split has been the de facto
    design for months and was never once enforced.

    The rule: a hook/script may invoke bare `python3` ONLY if what it runs is stdlib-only.
    Import a venv-only module, and you must be reached through a path, not a name.

    Proved live on 2026-07-12: `uv python install` shimmed `python3.13` into ~/.local/bin,
    AHEAD of Homebrew — so `run-tests.sh`'s `python3.13` pin silently became a different
    interpreter with no pytest. A NAME is a lookup through a mutable PATH that four package
    managers write to. A path is a path.
    """
    bad = []
    for script in sorted((ROOT / ".claude" / "scripts").glob("*.sh")):
        text = script.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#") or not BARE_PYTHON.search(line):
                continue
            target = _bare_python_target(line, script)
            hits = sorted({m for m in VENV_ONLY if re.search(rf"\b(import|from)\s+{m}\b", target)})
            if hits:
                bad.append(f"{_rel(script)}:{i}: invokes bare `python3` on code importing "
                           f"{', '.join(hits)} — venv-only. It will silently no-op when the "
                           f"`python3` name re-points (F-001). Use the venv by PATH.")
    return bad


def _bare_python_target(line: str, script: Path) -> str:
    """What the bare `python3` on this line will actually execute: an inline -c, or a file."""
    inline = re.search(r"""python3\s+-c\s+(['"])(.*?)\1""", line, re.DOTALL)
    if inline:
        return inline.group(2)
    ref = re.search(r"python3\s+\"?\$?[\w{}/.-]*?([\w-]+\.py)", line)
    if not ref:
        return ""
    for candidate in ROOT.rglob(ref.group(1)):
        if ".venv" not in candidate.parts:
            try:
                return candidate.read_text()
            except OSError:
                return ""
    return ""


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


def check_spend_auth_is_not_tracked() -> list[str]:
    """`.tessera/spend-auth.json` must NEVER be committed. The mirror of tessera-yml-is-tracked.

    A live spend authorization is run-scoped state. Committed, it would grant spend on every
    clone, to every agent, forever — and it would outlive its own TTL in git history. The
    `.yml` check asserts committed; this one asserts the opposite, for the opposite reason.
    """
    listed = subprocess.run(["git", "ls-files", ".tessera/spend-auth.json"], cwd=ROOT,
                            capture_output=True, text=True)
    if listed.returncode != 0 or not listed.stdout.strip():
        return []
    return [".tessera/spend-auth.json is git-tracked — a live spend authorization must never "
            "be committed; it would authorize spend on every clone. Add it to .gitignore and "
            "`git rm --cached` it."]


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
    "spend-auth-is-not-tracked": check_spend_auth_is_not_tracked,
    "no-bare-python3-with-toolchain-import": check_no_bare_python3_with_toolchain_import,
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
