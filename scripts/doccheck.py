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
# MUST STAY 3.9-COMPATIBLE: `safety-scripts-run-on-system-python` asserts this file runs
# on /usr/bin/python3 (3.9.6 here), because a hook invokes it via bare `python3` and a
# /usr/bin-first PATH resolves there — a crash would make the spend guard exit non-2, which
# Claude Code reads as ALLOW. PEP 585 (`dict[str, ...]`) is fine on 3.9; PEP 604 (`X | None`)
# is NOT. This defers every annotation to a string so the next union does not re-learn it —
# and that check caught exactly this, in this file, on 2026-08-10.
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import hashlib
import itertools
import re
import subprocess
import sys
from pathlib import Path

# One definition of the foreign-path data, shared with decision_surface. Only the DATA is
# shared: each side applies its own comparison, deliberately — see repo_paths' docstring.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from repo_paths import ABSENT_TESSERA_PATHS, FOREIGN_PATHS, PLACEHOLDER_PATTERN  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _prefix_meter():
    """Import the sibling meter LAZILY, the way decision_surface and report_settings are.

    It was a module-level `import prefix_meter` for exactly one day. Found by arbiter
    2026-08-09: a missing or syntactically broken `prefix_meter.py` killed the whole
    doccheck process with a traceback before any check ran, so the pre-commit hook lost
    all 41 checks — and `check_eager_prefix_figure_is_current`'s own try/except, written
    to turn precisely this into one reported line, could never be reached.

    Standing pattern #1, in the code written to guard against standing pattern #1: the
    thing that would tell you the meter is broken was killed by the meter being broken.
    It also made the safety-script probe (which `__import__`s doccheck under the oldest
    supported Python) carry a hidden transitive dependency invisible to SAFETY_SCRIPTS.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import prefix_meter
    return prefix_meter


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
# COMPILED FROM repo_paths.PLACEHOLDER_PATTERN, not re-typed. That module claims to hold the
# pattern "so the two consumers agree on what a placeholder looks like" — and this file kept a
# hand-copy anyway, so the claim was prose. Adding `…` there on 2026-08-17 left this copy
# behind and `docs/…` went red here while the surface correctly ignored it.
PLACEHOLDER = re.compile(PLACEHOLDER_PATTERN)

# Paths that legitimately aren't on disk. Every entry is a deliberate exemption with a
# reason — an unexplained allowlist is how a checker rots into theater.
PATH_ALLOWLIST = {
    # Runtime-created, never committed. spend-auth.json is MORE than uncommitted — it must
    # never be tracked (a live grant would authorize spend on every clone). The positive
    # assertion lives in check_runtime_state_is_not_tracked; this only exempts it from the `ls`.
    ".mnemos", ".tessera/logs", ".tessera/escalations", ".tessera/spend-auth.json",
    # Same class, added 2026-08-09 when `bin/tessera-verify` showed this check was RED on a
    # clean clone — so the pre-commit hook blocked before `install.sh` had ever run. Both are
    # gitignored runtime state: for these, "exists" is a MACHINE-LOCAL fact, and a check that
    # passes only on the author's disk is asserting nothing shared.
    ".claude/settings.local.json", ".tessera/.spend-backstop-fires",
    # Other repos' and downstream projects' files. MOVED to scripts/repo_paths.py on
    # 2026-08-15 and unioned back in here, so the data has one definition and this check's
    # behaviour is unchanged. They left because a SECOND consumer needed exactly this
    # subset and nothing else: decision_surface must not treat an evaluated repo's
    # `docs/architecture.md` as a Tessera path it governs. Reusing the whole of
    # PATH_ALLOWLIST there was the bug — this set answers "is it required to exist on
    # disk", and the entries ABOVE are Tessera's own gitignored runtime state, for which
    # the honest answer to "should a decision surface on it" is YES.
} | FOREIGN_PATHS
# ABSENT_TESSERA_PATHS is the MIRROR of PLANNED_PATHS below: deliberately-gone rather than
# deliberately-unbuilt. It is NOT unioned here. A first version was, and that exempted
# `bin/review` and friends from the existence check in EVERY doc — so a live instruction
# ("run `bin/review` to ...") in CLAUDE.md would pass silently where it used to go red, which
# is this block's own "tolerated exemption with no expiry" warning. It is applied per-doc
# below, only to the file whose job is recording history.

# Designed in docs, never built. NOT the same as a stale reference — these are promises
# the framework has not kept, and docs/design-principles.md describes them in the PRESENT
# tense, so a reader (or a future Claude) goes looking for a file that was never written.
# Parked here rather than allowlisted so the debt stays legible: either build them, or
# reword the doc to the conditional. Tracked in _project_specs/todos/active.md.
# (.tessera/config.yml graduated OUT of this set on 2026-07-11 — it was built, with one live
# consumer in bin/tessera-test. That is what a PLANNED_PATHS entry is supposed to do: get
# built, or get reworded. It should never just sit here.)
HISTORY_DOCS = frozenset({"docs/observatory.md"})

PLANNED_PATHS = {
    ".tessera/third-party-scope.yml",  # design-principles.md:726, 763 — build its CONSUMER first
    ".tessera/project.yml.template",   # design-principles.md:195 — deletion candidate, not a build
    # NEVER EXISTED, and that absence is the point: ADR-0007:463 and ADR-0008:37 both record it
    # as the reason `iterative-development` is a setup guide rather than a wired mechanism, and
    # design-principles.md:672 wrongly describes it in the PRESENT tense. Parked here rather
    # than in repo_paths.ABSENT_TESSERA_PATHS because unbuilt and deleted are different
    # questions — filing it as "gone" would tell a future reader to drop the declaration if it
    # ever appears, when the right action is graduating it and re-reading those two ADRs.
    "scripts/tdd-loop-check.sh",
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

    Paths under the three gitignored mirror symlinks resolve to their tracked sources via
    `prefix_meter.canonical_path`. If that import fails the check DEGRADES rather than
    dying or going blind: it falls back to literal resolution — its behaviour before
    2026-08-09 — and says so, because a silently literal run is red on a clean clone for
    reasons no reader could diagnose from the message.
    """
    degraded = []
    try:
        canonical = _prefix_meter().canonical_path
    except Exception as exc:
        canonical = lambda root, ref: root / ref                          # noqa: E731
        degraded = [f"scripts/prefix_meter.py cannot be imported ({exc}) — mirror-symlink "
                    f"resolution is OFF, so paths under .claude/{{skills,commands,agents}} "
                    f"are checked literally and will report false violations pre-install"]
    bad = list(degraded)
    for doc in _docs():
        for token in INLINE_CODE.findall(_strip_fences(doc.read_text())):
            token = token.strip().rstrip(".,;:)").split(":")[0]  # strip file:symbol suffixes
            if not token.startswith(REPO_DIRS) or any(c in token for c in " *?$<>|"):
                continue
            if PLACEHOLDER.search(token):
                continue
            # HISTORY_DOCS may name paths this repo deliberately deleted; a live
            # instruction elsewhere may not. Same token, different meaning by venue — and
            # the check cannot read intent, so it reads location. ADRs get this for free
            # via DOC_SKIP; the observatory is the other file that records what was cut.
            exempt = PATH_ALLOWLIST | PLANNED_PATHS
            if _rel(doc) in HISTORY_DOCS:
                exempt = exempt | frozenset(ABSENT_TESSERA_PATHS)
            if any(token.rstrip("/") == p or token.startswith(p + "/") for p in exempt):
                continue
            if not canonical(ROOT, token).exists():
                bad.append(f"{_rel(doc)}: names `{token}` — not on disk")
    return sorted(set(bad))


SIBLING_PATH = re.compile(r"^\.\./([A-Za-z0-9_.-]+)/(.+)$")
BRACE_SET = re.compile(r"\{([^}]*)\}")


def check_sibling_paths_exist() -> list[str]:
    """THE FORMAL `ls`, extended ACROSS the repo boundary — for peers that are checked out.

    `check_referenced_paths_exist` only walks REPO_DIRS, so every `../conclave/…`,
    `../arbiter/…`, `../pr-arbiter/…` citation in the peer contract was unverified. That is
    30 citations in `docs/contracts/three-project-cohesion.md` alone, in the one file whose
    own rule is: *"Evidence is referenced by sibling-relative path so the map survives a
    machine move."* A rule about paths, with nothing checking the paths.

    **Stated plainly: this check would NOT have caught the drift that motivated it** (the
    Pattern lane naming frozen `pr-arbiter` while S4/S5/D4 named `arbiter` — every path
    involved existed on disk). It is here for the class one step out, and it is tested
    against a failure that was NOT just fixed: a peer renaming or moving a file the contract
    cites. `second_pass.py` getting renamed in `../arbiter` now turns this red instead of
    rotting silently. Per A6's rule, the lane-CONSISTENCY property has no mechanical subject
    — the Owns column is authored prose — and stays a human re-read; see the observatory.

    **Skips a peer that is not checked out**, rather than failing. Absence of `../arbiter` on
    some machine is not a false doc claim, and a check that goes red on a fresh clone is one
    people learn to ignore. Brace sets are EXPANDED, not skipped: `{a,b}.py` is a closed list
    of real files, so it is checked, unlike the repo-path check which treats `{}` as a
    placeholder.
    """
    bad = []
    for doc in _docs():
        for token in INLINE_CODE.findall(_strip_fences(doc.read_text())):
            token = token.strip().rstrip(".,;:)").split(":")[0]
            match = SIBLING_PATH.match(token)
            if not match or any(c in token for c in " *?$<>|…"):
                continue
            peer, rest = match.group(1), match.group(2)
            root = ROOT.parent / peer
            if not root.is_dir():
                continue  # peer not checked out here — unknowable, not false
            for target in _expand_braces(rest):
                if not (root / target).exists():
                    bad.append(f"{_rel(doc)}: names `../{peer}/{target}` — not on disk")
    return sorted(set(bad))


def _expand_braces(path: str) -> list[str]:
    """Expand EVERY brace set, not just the first — `{a,b}/x/{c,d}.py` is 4 paths.

    Was `BRACE_SET.search` (first set only), found by `bin/tessera-verify` while confirming
    the check's other three claims: a second brace set stayed literal, and a stat on a
    literal `{c,d}.py` can never succeed, so it reported a permanent false violation. It
    fails LOUD rather than open, and no doc cites two sets today — latent, not live — but a
    pre-commit-blocking check that can go permanently red on a legal citation is not one to
    leave for later. Recursive so nesting depth is not a second special case.
    """
    braces = BRACE_SET.search(path)
    if not braces:
        return [path]
    return [expanded
            for name in braces.group(1).split(",")
            for expanded in _expand_braces(path.replace(braces.group(0), name.strip(), 1))]


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


PROMO = "docs/promo/index.html"
# The ADR timeline is a JS array of rows: ["ADR-NNNN", date, status, title, prose, css].
# Anchored to the row-leading id ON PURPOSE — see the docstring below.
_PROMO_ADR_ROW = re.compile(r'^\s*\["(ADR-0\d{3})"', re.M)


def check_promo_adr_timeline_is_complete() -> list[str]:
    """Every ADR on disk appears as a ROW on the outward-facing promo timeline.

    FOUND 2026-07-30, by a human asking "is the html document up to date?" — the same way
    the six doc-drift bugs before it were found. The page documented ADR-0001..0006 while
    19 were on disk: **13 behind, and it is published** (houseofyeti.com, linked from
    GitHub). Nothing could have said so. `check_adr_references_resolve` reads the
    observatory, design-principles, the handoff and CLAUDE.md — this file was outside
    every check in the repo, which is the standing-pattern-#1 shape aimed at the one
    artifact strangers actually read.

    WHY COMPLETENESS IS THE PROPERTY HERE AND NOT A PROXY. A6 rejected two handoff checks
    for keying on unenforced prose, and concluded the ADR `Executed:` field works "only
    because it is a STRUCTURED FIELD with a stated contract." Both conditions hold here:
    the rows are a JS array of exact ids, and the section frames itself as a *timeline* of
    records "numbered, dated, and immutable once accepted" — not a curated highlight reel.
    A timeline with gaps is wrong in a way a selection would not be. If that framing ever
    changes to "selected decisions", this check must be retired rather than satisfied.

    WHY IT ANCHORS ON THE ROW AND NOT ON ANY MENTION. Row prose cites other ADRs — 0006's
    entry opens "Amends ADR-0005's readiness claim". A loose `ADR-0\\d{3}` scan would count
    those mentions, so a page whose timeline array was emptied or renamed could still go
    green on prose alone. Keying on the row-leading quoted id is what makes the check
    unable to be satisfied by a footnote. That case is covered by a regression test.

    No status filter: a timeline is history, so Superseded and Watching records belong on
    it too, and filtering would re-introduce the judgement this check exists to avoid.

    A missing file is deliberately NOT an error — this asserts the timeline is complete,
    not that a marketing page must exist. Emptying the array is still caught, loudly: every
    ADR reports missing.
    """
    promo = ROOT / PROMO
    if not promo.is_file():
        return []
    listed = set(_PROMO_ADR_ROW.findall(promo.read_text()))
    return [f"{PROMO}: ADR {adr.name[:4]} ({adr.name}) is on disk but has no row on the "
            f"published ADR timeline — an outward-facing page reads as current"
            for adr in sorted((ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
            if f"ADR-{adr.name[:4]}" not in listed]


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
    # ADDED 2026-08-10, and the omission is the lesson. The membership rule is "a hook
    # invokes it via bare python3" — `.claude/scripts/tessera-decision-surface.sh:55` does
    # exactly that, and this file was not here. It had an f-string with a backslash in the
    # expression (3.12+), so on a /usr/bin-first PATH it did not PARSE, the `2>/dev/null`
    # on that line swallowed the traceback, and the DECISION SURFACE block silently never
    # reached the model — the hook built to defeat silent failure, failing silently (#1).
    # It surfaced only because `decision-surface-is-wired` happened to be evaluated by a
    # doccheck that was itself running on 3.9; had doccheck only ever run on the venv, that
    # check would have stayed green over a dead hook. Listing it here makes the 3.9 probe
    # unconditional instead of dependent on which interpreter runs the checker.
    "scripts/decision_surface.py",
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
            # The remedy is NOT hardcoded any more. It used to always say "Add
            # `from __future__ import annotations`" — right for PEP-604 annotations, the
            # bug it was written for, and WRONG for the f-string backslash that hit
            # decision_surface.py on 2026-08-10. A fix instruction that names the wrong
            # fix is the report-is-true-but-misleading shape (#12) aimed at the remedy.
            last = err[-1] if err else "?"
            remedy = ("Add `from __future__ import annotations`."
                      if "|" in last or "unsupported operand" in last
                      else "Rewrite the 3.10+/3.12+ construct this line uses.")
            bad.append(f"{name} does NOT run on {OLDEST_PYTHON} ({last}) — "
                       f"a hook invokes it via bare `python3`, and a /usr/bin-first PATH makes "
                       f"that 3.9. The spend guard would exit non-2, which Claude Code reads as "
                       f"ALLOW. {remedy}")
    return bad


_BARE_PY3 = re.compile(r"(?<![/\w.-])python3\s+(?:\"?[^\"'\s]*?/)?(scripts/[A-Za-z0-9_./-]+\.py)")


def check_bare_python3_hook_scripts_are_probed() -> list[str]:
    """SAFETY_SCRIPTS' membership rule was PROSE. Make it mechanical.

    The rule is stated plainly in the sibling check: "a hook invokes it via bare `python3`".
    Nothing enforced it, so `scripts/decision_surface.py` — invoked exactly that way by
    `.claude/scripts/tessera-decision-surface.sh` — was simply absent from the list, and
    its 3.12+ f-string meant it did not PARSE on a /usr/bin-first PATH. The invoking line
    ends in `2>/dev/null`, so the traceback went nowhere and the DECISION SURFACE block
    silently stopped reaching the model. It surfaced only because a doccheck run that
    happened to be on 3.9 tripped a DIFFERENT check.

    That is the shape ADR-0016 named: a rule written in prose with no enforcement is a rule
    that holds until someone adds the next file. This check is the enforcement — the list
    can no longer fall behind the hooks silently.

    Deliberately narrow: only `scripts/*.py` reached through a BARE `python3` from a hook.
    An explicit interpreter path (`.venv/bin/python`) is the toolchain split working as
    designed and is not in scope.
    """
    hooks = ROOT / ".claude" / "scripts"
    if not hooks.is_dir():
        return []
    bad = []
    invoked = set()
    for sh in sorted(hooks.glob("*.sh")):
        try:
            text = sh.read_text(errors="replace")
        except OSError:
            continue
        for target in sorted(set(_BARE_PY3.findall(text))):
            if not (ROOT / target).exists():
                continue
            invoked.add(target)
            if target not in SAFETY_SCRIPTS:
                bad.append(
                    f"{sh.relative_to(ROOT)} runs `python3 {target}` (bare interpreter) but "
                    f"{target} is not in SAFETY_SCRIPTS — nothing proves it runs on "
                    f"{OLDEST_PYTHON}, which is what a /usr/bin-first PATH hands it")

    # SECOND HALF: CLAUDE.md enumerates the same set in PROSE, and prose was how this drifted
    # in the first place. It is read by every session; a stale list there teaches the wrong
    # rule to the next person adding a hook. Globs are honoured (`scripts/gate/*.py`).
    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        line = ""
        for candidate in claude_md.read_text(errors="replace").splitlines():
            if candidate.lstrip().startswith("- **Stdlib-only**"):
                line = candidate
                break
        # ONLY the parenthetical enumeration, never the whole line. Scanning the line
        # scooped up backticked paths from the PROSE beside it — including the sentence
        # explaining that decision_surface.py had been missing — so the check passed
        # because of its own explanation and could not fail. Caught by re-planting the
        # omission and watching it stay green (#10: a guard tested against the fixed state
        # proves nothing; and its corollary — do not match prose about the code).
        enumeration = re.search(r"-\s*\*\*Stdlib-only\*\*\s*\(([^)]*)\)", line)
        if enumeration:
            patterns = re.findall(r"`([^`]+\.py)`", enumeration.group(1))
            for target in sorted(invoked):
                if not any(fnmatch.fnmatch(target, p) for p in patterns):
                    bad.append(
                        f"CLAUDE.md's stdlib-only list does not cover {target}, which a hook "
                        f"runs via bare `python3` — the prose rule the next person reads is "
                        f"already behind the hooks")
    return sorted(set(bad))


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


def check_verdict_channel_literals_match_contract() -> list[str]:
    """The contract documents two `verdict_channel` values; the code must define those two.

    There are THREE copies of this vocabulary — `cmd_run` writes it, `cmd_stats` reads it, and
    docs/contracts/verification-event.md documents it — and on 2026-08-09 two of them had
    drifted apart for long enough that the ⚠ banner announcing a regression to the fragile
    channel could not fire at all. A shared constant now makes the writer/reader pair
    unrepresentable-apart; this closes the doc as the third copy.

    SCOPE, stated because a narrowing that lives only in the source is standing pattern #12:
    this checks the DOC against the code's declared vocabulary and nothing else. It cannot see
    a literal re-inlined at a use site — that is covered behaviourally by
    test_tessera_verify.py::test_the_message_channel_warning_fires_on_what_cmd_run_actually_writes,
    which drives writer→reader and names no literal.

    The module is loaded INSIDE the function on purpose. A module-level import here would take
    every other check down with it if it ever failed — which is exactly what happened to this
    file on 2026-08-09 with `import prefix_meter`.
    """
    import importlib.machinery
    import importlib.util

    contract = ROOT / "docs" / "contracts" / "verification-event.md"
    tool = ROOT / "bin" / "tessera-verify"
    if not contract.exists() or "verdict_channel" not in contract.read_text(encoding="utf-8"):
        return []  # no claim, nothing to check
    try:
        loader = importlib.machinery.SourceFileLoader("_tv_doccheck", str(tool))
        spec = importlib.util.spec_from_loader("_tv_doccheck", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        channels = {mod.CHANNEL_FILE, mod.CHANNEL_MESSAGE}
    except Exception as e:  # noqa: BLE001 — a rename or a syntax error must FAIL, never skip
        return [f"bin/tessera-verify does not expose CHANNEL_FILE/CHANNEL_MESSAGE ({e!r}) — "
                "docs/contracts/verification-event.md documents a verdict_channel vocabulary "
                "that can no longer be checked against the code"]

    text = contract.read_text(encoding="utf-8")
    missing = sorted(c for c in channels if f'"{c}"' not in text)
    if missing:
        return [f"bin/tessera-verify can emit verdict_channel {missing} but "
                "docs/contracts/verification-event.md never documents "
                f"{'them' if len(missing) > 1 else 'it'} — the contract is the third copy of "
                "this vocabulary, and the last time two copies drifted the regression banner "
                "went dead for weeks"]
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

    RETARGETED 2026-08-06 when the block moved to `tessera-patterns-surface.sh`. This check
    used to assert that the string "Standing patterns" appeared in `tessera-watch-surface.sh`,
    which is a substring test over a shell script and cannot tell code from prose.

    HOW CLOSE THAT CAME, stated accurately because the first draft of this docstring did not.
    The claim was that the check would have gone on passing on the COMMENT left behind in the
    surfacer. `bin/tessera-verify` REFUTED it: the comment reads "The standing patterns USED
    TO BE PRINTED HERE" in lowercase, the old grep was capitalised, and the old check fires
    correctly on this change. The hazard is still real — the falsifier capitalised one letter
    in that comment and got a surfacer emitting ZERO patterns while the old check returned
    PASS. So the repo escaped a false green by a capital letter, not by design. A near-miss,
    not a hit.

    It now names the emitting script explicitly and, more importantly,
    `standing-patterns-fit-the-cap` RUNS it. Emission is not the property; arrival is.
    """
    bad = []
    handoff = ROOT / "_project_specs" / "todos" / "active.md"
    emitter = ROOT / ".claude" / "scripts" / "tessera-patterns-surface.sh"
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
    if not (emitter.exists() and os.access(emitter, os.X_OK)):
        bad.append(".claude/scripts/tessera-patterns-surface.sh: missing or not executable — "
                   "the standing-patterns block exists but nothing emits it")
    return bad


# Claude Code caps hook output at 10,000 characters (code.claude.com/docs/en/hooks); past
# that the harness saves it to a file and hands the model a ~2KB preview. 9,000 leaves a
# margin so growth is caught by a failing check rather than by silent truncation.
_HOOK_OUTPUT_CAP = 10_000
_HOOK_OUTPUT_BUDGET = 9_000


def check_docs_name_the_right_patterns_emitter() -> list[str]:
    """A doc that says hook X prints the standing patterns must name the hook that does.

    ADDED 2026-08-06, and it is a finding about the CHECKER, not just about a doc. Moving
    the block out of `tessera-watch-surface.sh` left CLAUDE.md asserting that that script
    "prints the handoff pointer, the Standing patterns block ... and any fired observatory
    trigger". False the moment the split landed. doccheck stayed green — 38 checks — and a
    human found it by asking "no drift?", which is precisely how the previous six doc-drift
    bugs were found and precisely what this file exists to stop happening a seventh time.

    The claim is machine-checkable and was simply never claimed: if a doc names a script in
    the same sentence as the standing patterns, that script must be the one that emits them.
    """
    emitter = "tessera-patterns-surface.sh"
    bad = []
    for doc in [ROOT / "CLAUDE.md", *(ROOT / "docs").rglob("*.md")]:
        if not doc.is_file() or doc.name == "observatory.md":
            continue           # the observatory records history, including superseded wiring
        for i, line in enumerate(doc.read_text().splitlines(), 1):
            if "Standing patterns" not in line and "standing patterns" not in line:
                continue
            named = set(re.findall(r"([a-z0-9-]+-surface\.sh)", line))
            if named and emitter not in named:
                bad.append(f"{doc.relative_to(ROOT)}:{i}: says {sorted(named)} handles the "
                           f"standing patterns, but {emitter} emits them — the block moved "
                           f"2026-08-06 and the doc did not")
    return bad


def check_standing_patterns_fit_the_cap() -> list[str]:
    """The standing patterns must ARRIVE — every one of them, not merely be emitted.

    ADDED 2026-08-06, after measuring that 11 of 12 never reached the model. The surfacer
    emitted 10,878 characters in one output; the cap is 10,000; the harness replaced
    everything past ~2KB with a file path. `standing-patterns-are-surfaced` was green the
    whole time because it asked whether the block was EXTRACTED, which was true.

    So this check RUNS the registered parts and measures what they emit. Three properties,
    and the third is the one a size check alone would miss:

      1. the registered `--part` indices are exactly 1..N for the declared `--of N`;
      2. every part's output is under the budget;
      3. the UNION of the parts carries every pattern in the handoff, each exactly once.

    (3) exists because a chunker that silently drops or duplicates a pattern reproduces the
    original bug with better numbers. Growth past what N parts can carry fails (2) loudly;
    the fix is to add a part in settings.json, which cannot be done by accident.

    COVERAGE IS DISTRIBUTED, so do not audit this check alone. `bin/tessera-verify` found
    the seam: when the emitter is merely NON-EXECUTABLE this check fires (the subprocess
    raises), but when it is ABSENT this check early-returns [] and goes silent — absence is
    owned by `standing-patterns-are-surfaced`, which fires on both. The property is "does
    something report it", not "does this function report it". That is the same distinction
    the degraded-event contract records, and counting per-check coverage is how three wrong
    findings got written on 2026-07-26.
    """
    settings = ROOT / ".claude" / "settings.json"
    emitter = ROOT / ".claude" / "scripts" / "tessera-patterns-surface.sh"
    handoff = ROOT / "_project_specs" / "todos" / "active.md"
    if not (settings.exists() and emitter.exists() and handoff.exists()):
        return []                      # standing-patterns-are-surfaced owns the absence
    try:
        hooks = json.loads(settings.read_text())["hooks"]["SessionStart"]
    except (ValueError, KeyError):
        return [".claude/settings.json: SessionStart hooks unreadable — cannot verify "
                "standing-patterns delivery"]

    parts, declared = [], set()
    for entry in hooks:
        for h in entry.get("hooks", []):
            m = re.search(r"tessera-patterns-surface\.sh\"? --part (\d+) --of (\d+)",
                          h.get("command", ""))
            if m:
                parts.append(int(m.group(1)))
                declared.add(int(m.group(2)))
    if not parts:
        return [".claude/settings.json: tessera-patterns-surface.sh is not registered on "
                "SessionStart — the standing patterns are emitted by nothing"]
    if len(declared) != 1:
        return [f".claude/settings.json: patterns hooks disagree on --of {sorted(declared)} — "
                f"the chunking would drop or duplicate lessons"]
    total = declared.pop()
    if sorted(parts) != list(range(1, total + 1)):
        return [f".claude/settings.json: patterns parts registered {sorted(parts)}, expected "
                f"{list(range(1, total + 1))} — a missing part is silently unsurfaced lessons"]

    bad, seen = [], []
    for n in sorted(parts):
        try:
            out = subprocess.run([str(emitter), "--part", str(n), "--of", str(total)],
                                 cwd=ROOT, capture_output=True, text=True, timeout=30).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            bad.append(f".claude/scripts/tessera-patterns-surface.sh --part {n}: "
                       f"failed to run ({exc}) — delivery is unverifiable, treat as broken")
            continue
        if len(out) > _HOOK_OUTPUT_BUDGET:
            bad.append(f"standing-patterns part {n}/{total} emits {len(out):,} chars, over the "
                       f"{_HOOK_OUTPUT_BUDGET:,} budget (harness cap {_HOOK_OUTPUT_CAP:,}) — it "
                       f"will be truncated to a preview. Add a part in .claude/settings.json")
        seen += re.findall(r"^(\d+)\. \*\*", out, re.M)

    text = handoff.read_text()
    first = text.find("## Handoff — pick up here")
    nxt = text.find("\n## ", first + 5)
    block = text[first:nxt if nxt != -1 else len(text)]
    # LINE-ANCHORED, matching the emitter's awk (`/^### Standing patterns/`). An unanchored
    # `find` matched a BACKTICKED PROSE MENTION of the heading in the 2026-08-15 handoff —
    # a sentence describing this very mechanism — and sliced the section from there, so the
    # check reported the handoff carried ZERO patterns while the emitter correctly carried
    # all 12. Emitter and checker must locate the block the same way or the checker can be
    # fooled by text the emitter ignores. Same class as prose-matching a code comment (#10's
    # corollary), aimed at a doc rather than at source.
    s = block.find("\n### Standing patterns")
    if s != -1:
        s += 1
        e = block.find("\n### ", s + 5)
        expected = re.findall(r"^(\d+)\. \*\*", block[s:e if e != -1 else len(block)], re.M)
        if sorted(seen) != sorted(expected):
            missing = sorted(set(expected) - set(seen), key=int)
            dupes = sorted({p for p in seen if seen.count(p) > 1}, key=int)
            bad.append(f"standing-patterns parts carry {sorted(seen, key=int)} but the handoff "
                       f"has {sorted(expected, key=int)}"
                       + (f" — MISSING {missing}" if missing else "")
                       + (f" — DUPLICATED {dupes}" if dupes else ""))
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


def check_decision_surface_deps_ship_downstream() -> list[str]:
    """Every module `decision_surface.py` imports at module scope must be scaffolded too.

    ADDED 2026-08-15. `decision_surface` is copied into every new project by
    `bin/tessera-new-project`; a module-scope import it does NOT copy makes the hook die on
    import in every downstream — the failure `decision_amendments`' own comment already
    warns about. `repo_paths` joined that copy set the same day and nothing asserted it.

    The version this replaced was worse than a missing copy. It reached for `doccheck.py`
    behind a defensive try/except, so downstream the import failed, the exemption silently
    did nothing, permanently, and the arm written to detect that degradation could only run
    in THIS repo — where the import cannot fail. Ship-both-halves (#5) with the halves one
    process apart.

    Parses the imports rather than matching a list, so adding a new dependency cannot pass
    by being forgotten here as well as there.
    """
    src = ROOT / "scripts" / "decision_surface.py"
    scaffold = ROOT / "bin" / "tessera-new-project"
    if not src.exists() or not scaffold.exists():
        return ["scripts/decision_surface.py or bin/tessera-new-project missing — cannot "
                "verify the downstream hook's dependencies ship with it"]
    try:
        tree = ast.parse(src.read_text())
    except SyntaxError as exc:
        return [f"scripts/decision_surface.py does not parse: {exc}"]
    # tree.body only — MODULE SCOPE, matching what this check claims. `ast.walk` also
    # reaches imports inside functions, which are the normal way to declare an OPTIONAL
    # downstream dependency (import it lazily, degrade if absent); flagging those would
    # forbid the pattern rather than guard it. Over-strict is still wrong.
    local = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            name = node.module.split(".")[0]
            if (ROOT / "scripts" / f"{name}.py").exists():
                local.add(name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                name = a.name.split(".")[0]
                if (ROOT / "scripts" / f"{name}.py").exists():
                    local.add(name)
    copied = scaffold.read_text()
    return [f"scripts/decision_surface.py imports `{name}` at module scope but "
            f"bin/tessera-new-project does not copy scripts/{name}.py — the decision-surface "
            f"hook will die on import in every scaffolded project"
            for name in sorted(local) if f"scripts/{name}.py" not in copied]


def check_decision_surface_honors_path_exemptions() -> list[str]:
    """No path THIS FILE exempts may be indexed as a governing Tessera decision.

    ADDED 2026-08-15. `PATH_ALLOWLIST` records, entry by entry with the reason beside it,
    which backticked paths are not this repo's — *"Other repos' files. The observatory
    evaluates GSD; it doesn't claim to contain it."* `decision_surface` could not see that
    list, so it indexed six of them anyway: GSD's `bin/lib/*.cjs`, Open GSD's
    `docs/ARCHITECTURE.md`, downstream `docs/FINDINGS.md`, and a `scripts/tessera-escalate`
    that only ever existed at `bin/`. An ADR-0023 review found the same class in ADR form —
    a Switchyard evaluation backticking Switchyard's own `docs/architecture.md`, which would
    have fired as a governing decision the day this repo gained a file by that name.

    WHAT IT GUARDS, STATED NARROWLY BECAUSE RE-PLANTING PROVED THE FIRST DRAFT WRONG.
    This guards the FILTER, not the docs. Verified by deliberately breaking each (#10):
      - delete the `_is_exempt` call from `build_index()` -> fires;
      - break `_exempt_paths()`'s defensive `import doccheck` -> fires 4x via the empty-set
        arm below. That arm is load-bearing: the import runs inside a PreToolUse hook whose
        stderr is discarded, so it must not raise, and a degraded import silently exempts
        NOTHING and restores the defect (#1: what tells you the check itself died).

    WHAT IT DOES **NOT** CATCH, and this is the honest scope limit. Adding a NEW foreign path
    to a doc does not fire it — the filter drops the path before it is ever indexed, so the
    condition cannot arise. Re-planting `docs/ARCHITECTURE.md` into an ADR was silently
    correct-by-construction, which is exactly what made the first version of this docstring
    ("the class guard, not the row fix") an over-claim. A foreign path NOT already in
    PATH_ALLOWLIST is caught for ordinary docs by `referenced-paths-exist` (it does not
    exist -> red -> a human allowlists or fixes it), and is caught by NOTHING in an ADR,
    because DOC_SKIP exempts docs/adr/ from that check entirely. That residual gap is real,
    is not closed here, and is recorded in docs/observatory.md.

    NOT asserted here either: that every index key EXISTS on disk. Deliberate — `bin/kimi`,
    `bin/review`, `bin/research` and `docs/maggy-rfc.md` are real Tessera files that were
    deleted, and an ADR that governed one arguably SHOULD fire if it is ever recreated.
    Existence and foreignness are different questions; only the second is checkable here.
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import decision_surface
        index = decision_surface.build_index()
    except Exception as exc:
        return [f"scripts/decision_surface.py cannot build its index: {exc}"]

    # THE COMPARISON IS RE-IMPLEMENTED HERE, NOT IMPORTED. Calling
    # `decision_surface._is_exempt` is what made the first version of this check vacuous:
    # the filter and the guard shared one predicate, so stubbing it restored the entire
    # defect (index 141 -> 148 keys, every foreign path reindexed) while this returned
    # clean. Found by review, reproduced, and it is the reason these four lines are
    # duplicated rather than factored. Sharing the DATA is single-sourcing; sharing the
    # COMPARISON makes a guard an echo of the thing it guards.
    placeholder = re.compile(PLACEHOLDER_PATTERN)
    bad = []
    for key in sorted(index):
        bare = key.rstrip("/")
        foreign = any(bare == p or key.startswith(p + "/") for p in FOREIGN_PATHS)
        if foreign or placeholder.search(key):
            srcs = ", ".join(sorted({e["doc"] for e in index[key]}))
            bad.append(f"decision_surface indexes `{key}` as a governing path, but it "
                       f"belongs to another repo or a downstream project (named in {srcs})")
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


def check_insert_or_ignore_needs_a_real_key() -> list[str]:
    """`INSERT OR IGNORE` is a lie unless the table has a UNIQUE key it can conflict on.

    THE BUG THIS EXISTS FOR, and it shipped THREE TIMES before anything generalized:

      1. `drift_events` — 700 rows that were 154 distinct drifts re-inserted across
         31 scans (ADR-0013). Fixed with `drift_dimensions_key`.
      2. `edges` — `INSERT OR IGNORE` whose only UNIQUE column was `id`, a fresh
         uuid4 per call, so the clause could never fire. Inert until an auto-recorder
         started calling it per turn; 995 rows / 891 distinct when measured.
      3. `mnemo_nodes` — the same, in the auto-node writer that runs per commit and
         per edit. 485 `auto-commit` rows for 319 distinct messages.

    Each fix was applied to the row it was found on. The commit that fixed (2) said
    in its own message "fix the pattern, not the row" and then did not, which is how
    (3) was still live for an independent reviewer to find hours later. This is the
    repo's standing rule applied to code instead of docs: a defect class that has
    recurred becomes an assertion, or the fourth instance is found the same way.

    The check: for each `INSERT OR IGNORE INTO <table>` in the toolchain, the value
    bound to that table's first column must not be a freshly generated uuid. That is
    the exact tell — a per-call unique id makes the conflict clause unreachable.
    An empty scan set is a violation, not a pass (standing pattern #1: what would
    tell you this check itself died).
    """
    targets = [
        Path("scripts/icpg/store.py"),
        Path("scripts/mnemos/store.py"),
        Path("scripts/mnemos/auto_nodes.py"),
    ]
    pattern = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)", re.IGNORECASE)
    scanned = 0
    problems: list[str] = []

    for rel in targets:
        path = ROOT / rel
        if not path.exists():
            problems.append(f"{rel}: named by this check but missing")
            continue
        text = path.read_text()
        scanned += 1
        for match in pattern.finditer(text):
            table = match.group(1)
            # Window spans BOTH SIDES of the statement. The first version looked
            # only forward and was vacuous: the id is generated on the line ABOVE
            # the INSERT (`node_id = str(uuid.uuid4())`), so re-introducing the real
            # defect left the check green. Caught by re-introducing it on purpose —
            # a guard tested only against the fixed code proves nothing.
            window = text[max(0, match.start() - 400):match.end() + 900]
            uuid_bound = re.search(r"(uuid\.uuid4\(\)|_uuid\(\))", window)
            declares_unique = re.search(
                rf"CREATE\s+UNIQUE\s+INDEX[^;]*\bON\s+{table}\b", text,
                re.IGNORECASE,
            )
            if uuid_bound and not declares_unique:
                problems.append(
                    f"{rel}: `INSERT OR IGNORE INTO {table}` binds a fresh uuid and "
                    f"{table} has no UNIQUE index in this file — the IGNORE can never "
                    f"fire, so every call appends a duplicate. Give the table a real "
                    f"natural key, or dedup explicitly before inserting."
                )

    if not scanned:
        problems.append(
            "insert-or-ignore scan matched no files — the check is blind, "
            "which is indistinguishable from clean"
        )
    return problems


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


def check_chaos_probe_count_is_current() -> list[str]:
    """`bin/tessera-chaos` quotes how many probes are green. That number must be real.

    IT HAD ALREADY DRIFTED SILENTLY ONCE. The header said "ALL 8 PROBES ARE GREEN as of
    2026-07-26" in two places while `chaos/test_chaos.py` held **11** — probes 9-11 were
    added by the A5b audit on 07-27 and CLAUDE.md was updated; the runner's own banner was
    not. So the first thing anyone sees when running the suite understated its coverage by
    three probes, in the file whose entire subject is *"does the framework still notice when
    I break it?"*.

    WHY A NUMBER IS ALLOWED HERE AT ALL. CLAUDE.md refuses to quote a test count for
    `tessera-test`, because a hardcoded number drifts on every test added. The difference is
    ownership: this is not a number restated in a second place, it is a CONSISTENCY
    ASSERTION between two live sources — the banner and the probe file. Same shape as
    `tessera-watch`'s `_max_spend_fires`, which reads MAX_FIRES out of the backstop rather
    than copying it, and for the same reason: whoever adds probe 12 gets told.

    Deliberately does NOT check the date beside it. "As of <date>" is a claim about when a
    human last ran them, which no file can verify — asserting it would be a mechanical check
    with a non-mechanical subject (#3's corollary, and the reason two of three candidate
    handoff checks were rejected on 2026-07-27).
    """
    runner = ROOT / "bin" / "tessera-chaos"
    probe_file = ROOT / "chaos" / "test_chaos.py"
    if not runner.is_file() or not probe_file.is_file():
        return []                      # nothing to keep honest

    try:
        banner = runner.read_text()
        probes = probe_file.read_text()
    except OSError:
        return []

    actual = len(re.findall(r"^def test_", probes, re.M))
    if not actual:
        return []

    # Match ONLY the two shapes the banner actually uses. The first version accepted any
    # "<n> green", which `echo "ran 11 probes, 10 green, 1 red"` satisfies twice — yielding a
    # false claim of 10 and firing this check wrongly (arbiter, 2026-08-09). A false alarm here
    # is worse than a missed one: doccheck blocks the commit. Comments are NOT stripped — in
    # this file the banner IS a comment, and the comment is what the reader sees.
    claimed = {int(n) for pair in re.findall(r"\b(\d+)\s+PROBES\b|\bAll\s+(\d+)\s+green\b",
                                             banner) for n in pair if n}
    wrong = sorted(n for n in claimed if n != actual)
    if wrong:
        return [f"bin/tessera-chaos claims {', '.join(str(n) for n in wrong)} probe(s) but "
                f"chaos/test_chaos.py defines {actual} — the banner is the first thing a "
                f"reader sees and it has already drifted silently once (8 vs 11)"]
    if not claimed:
        return [f"bin/tessera-chaos no longer states a probe count; chaos/test_chaos.py "
                f"defines {actual}. Restore it or drop this check — a banner that says "
                f"nothing cannot go stale, but it also cannot be verified"]
    return []


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
    # PROMO added 2026-07-30: it was outside every check in the repo, and it is the one
    # artifact strangers read. Completeness is checked separately; this catches the other
    # direction — a published row citing a decision that does not exist.
    for rel in ("docs/observatory.md", "docs/design-principles.md",
                "_project_specs/todos/active.md", "CLAUDE.md", PROMO):
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


# `| 0011 | 2026-07-21 | title | Superseded by ADR-0012 |`. Status is read as the LAST cell
# rather than by column index: column ORDER in this table is not enforced by anything, and the
# 0006 row carried its date and title transposed from 2026-07-12 until 2026-08-17, so a
# positional parse would have read a title as a status for five weeks. Anchored on a leading
# 4-digit id so prose tables elsewhere in the file cannot match.
#
# The trailing `|` is OPTIONAL because GFM does not require it. Requiring it made the check
# VACUOUS rather than noisy: an unparseable row fell through the `num not in rows` branch that
# is documented as "adr-index-complete owns it", and that check's looser regex passes too, so a
# real disagreement was owned by nobody. Found by review 2026-08-17, one commit after landing.
_ADR_INDEX_ROW = re.compile(r"^\|\s*(0\d{3})\s*\|(.+?)\|?\s*$", re.M)
_ADR_VERDICT = re.compile(r"^(Accepted|Watching|Superseded|Proposed|Deprecated)\b", re.I)
# re.I to match _ADR_VERDICT. Without it `superseded by adr-0012` parsed as (Superseded, None)
# and produced the same false positive the None-compatibility rule below exists to prevent.
_ADR_SUPERSEDER = re.compile(r"ADR-(0\d{3})", re.I)


def _adr_verdict(status: str) -> tuple[str, str | None]:
    """Reduce a Status string to the pair that must agree: (verdict, superseded-by).

    NOT byte-equality, and that is the whole design. Measured across all 24 ADRs before
    writing this: three carry a qualifier in exactly one of the two places and are correct
    both times — the index says `Accepted (delivery mechanism refined by ADR-0009)` where
    0008's file says `Accepted`; 0012's file says `Accepted (supersedes ADR-0011)` where the
    index says `Accepted`; 0014's file appends `— **Option D: review is Claude-only**`.
    Demanding equality would report all three and push an author to DELETE a true qualifier to
    appease the checker, which is the failure mode `_looks_like_path` above is scoped around.

    The superseder id is kept because `Superseded by ADR-0008` and `Superseded by ADR-0009`
    are a real disagreement, not a formatting difference.
    """
    m = _ADR_VERDICT.match(status.strip())
    verdict = m.group(1).capitalize() if m else status.strip()
    target = None
    if verdict == "Superseded":
        t = _ADR_SUPERSEDER.search(status)
        target = t.group(1) if t else None
    return verdict, target


_ADR_BECAUSE = re.compile(r"^- \*\*(Superseded|Deprecated) because:\*\* *(.+)$", re.M)


def check_superseded_status_is_accountable() -> list[str]:
    """A retired ADR must name its successor and say why — the bound on CLAUDE.md's second
    ADR-editing exception.

    2026-08-17 widened "don't edit accepted ADRs" to permit moving `Status:` to
    `Superseded by ADR-NNNN` / `Deprecated`, because `adr-status-matches-index` had made stale
    statuses visible and the rule's only remedy was a forbidden edit. A widened exception with
    nothing enforcing its edge is how a maintenance carve-out becomes a licence to flip a
    verdict quietly, so the edge is a check rather than the paragraph that describes it.

    Asserts three things: the named successor EXISTS (a pointer at nothing retires a decision
    into a dead end); a because-line is present (the reason is the fact readers come for, and
    it is what distinguishes recording a supersession from performing one); and `Deprecated`
    carries one too, since it is the one retirement with no successor to explain it.

    This CODIFIES practice rather than inventing it — both superseded ADRs already comply,
    2 of 2, including the one edited the day this shipped. That is deliberate: a new rule whose
    corpus is already green is a rule the repo had, unwritten.
    """
    bad = []
    on_disk = {p.name[:4] for p in (ROOT / "docs" / "adr").glob("0*.md")}
    for adr in sorted((ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = adr.read_text()
        m = _ADR_STATUS.search(text)
        if not m:
            continue  # adr-status-matches-index owns the missing-Status case
        status = m.group(1).strip()
        verdict, target = _adr_verdict(status)
        if verdict not in ("Superseded", "Deprecated"):
            continue
        because = _ADR_BECAUSE.search(text)
        if not because:
            bad.append(f"docs/adr/{adr.name}: Status is {verdict!r} with no "
                       f"`- **{verdict} because:**` line — a retirement with no stated reason "
                       f"is indistinguishable from a verdict quietly flipped in place")
        elif because.group(1) != verdict:
            bad.append(f"docs/adr/{adr.name}: Status says {verdict!r} but the reason line says "
                       f"{because.group(1)!r} — they must name the same retirement")
        if verdict == "Superseded":
            if target is None:
                bad.append(f"docs/adr/{adr.name}: Status is 'Superseded' but names no "
                           f"successor — say which ADR governs now")
            elif target not in on_disk:
                bad.append(f"docs/adr/{adr.name}: superseded by ADR-{target}, which does not "
                           f"exist — the decision is retired into a dead end")
    return bad


_DEPLOY_MARKER = re.compile(r"<!--\s*deployed:\s*([0-9a-f]{16})")
_DEPLOY_BLOCK = re.compile(r"<!--\s*deployed:.*?-->", re.S)
PROMO_PAGE = "docs/promo/index.html"


def promo_body_hash(text: str) -> str:
    """Hash of the page with only the HASH TOKEN neutralised — not the whole marker comment.

    Excluding the token is what makes stamping a no-op on the compared value; otherwise the
    cheapest way to clear the finding would be to edit the marker, which certifies nothing.
    But the first version stripped the entire `<!-- deployed: … -->` block, ~14 lines of prose
    that IS part of the uploaded HTML — so rewording it changed the published page while the
    check stayed green. Blanking just the 16 hex characters keeps the property and closes that.
    (Review, 2026-08-17.)
    """
    neutral = re.sub(r"(<!--\s*deployed:\s*)[0-9a-f]{16}", r"\1" + "0" * 16, text)
    return hashlib.sha256(neutral.encode()).hexdigest()[:16]


def check_promo_deploy_marker_is_current() -> list[str]:
    """The published page must match the repo's copy of it.

    `docs/promo/index.html` is uploaded BY HAND. `promo-adr-timeline-is-complete` catches a
    MISSING row and blocks; nothing caught a row present and correct in git but stale on the host.
    conclave F-004 records the cost — a wrong claim reached a deployed page and outlived the commit
    that fixed it, because "needs re-upload" lived only in whoever remembered doing it.

    A DATE MARKER WAS BUILT FIRST AND WAS A FALSE GREEN. F-004 proposes comparing a `deployed:`
    date against the file's last content commit. Implemented, it went green immediately: the page
    took FOUR commits on 2026-08-17 and a same-day date cannot distinguish them. The design failed
    on the exact instance that motivated it, which is why this compares CONTENT, not time.

    WHAT IT CANNOT DO, said plainly: verify the upload. Nothing here reaches the host, so the
    marker records a CLAIM — the shape `restore_injected` got wrong. No second party exists, so
    the achievable goal is narrower and is the whole scope: make FORGETTING loud.
    """
    page = ROOT / PROMO_PAGE
    if not page.is_file():
        return []
    text = page.read_text()
    m = _DEPLOY_MARKER.search(text)
    if not m:
        return [f"{PROMO_PAGE}: no `<!-- deployed: <hash> -->` marker — the page is uploaded by "
                f"hand, so without it nothing can tell whether the published copy is stale"]
    want = promo_body_hash(text)
    if m.group(1) != want:
        return [f"{PROMO_PAGE}: content hash is {want} but the deploy marker says {m.group(1)} — "
                f"the published page is behind the repo. Upload it, then run "
                f"`python3 scripts/doccheck.py --stamp-deploy` and commit."]
    return []


def stamp_deploy() -> int:
    """Write the current content hash into the marker. Run AFTER uploading, never before."""
    page = ROOT / PROMO_PAGE
    if not page.is_file():
        print(f"{PROMO_PAGE}: not present — nothing to stamp", file=sys.stderr)
        return 1
    text = page.read_text()
    if not _DEPLOY_MARKER.search(text):
        print(f"{PROMO_PAGE}: no deploy marker to stamp", file=sys.stderr)
        return 1
    want = promo_body_hash(text)
    page.write_text(_DEPLOY_MARKER.sub(f"<!-- deployed: {want}", text, count=1))
    print(f"stamped {PROMO_PAGE} deployed: {want}")
    return 0


def check_absent_index_paths_are_declared() -> list[str]:
    """Every path the decision surface indexes must exist, or be declared with a reason.

    CLOSES THE RESIDUAL GAP `check_decision_surface_honors_path_exemptions` names in its own
    docstring: a foreign path *not already* in the exemption list is caught in ordinary docs by
    `referenced-paths-exist` going red, and is caught by **nothing** inside an ADR, because
    `DOC_SKIP` exempts `docs/adr/` from that check and five others. That is how Braintrust's
    two `.mdx` paths sat in the index as Tessera paths from 2026-08-06 to 2026-08-17.

    WHY NOT JUST NARROW `DOC_SKIP`. Measured before choosing: dropping it produces 13 findings
    in ADRs and **11 are correct behaviour** — `bin/kimi`, `bin/review`, `bin/research`,
    `docs/maggy-rfc.md`, `skills/tessera-code-review/` are real Tessera paths this repo deleted,
    and `scripts/tdd-loop-check.sh` is one two ADRs correctly record as never built. An ADR
    naming a path it retired is an ADR doing its job. A blanket existence rule would go red on
    all of them, which is why queue item 2 warned against it.

    So the assertion is DECLARATION, not existence. An absent index key must be either foreign
    (`repo_paths.FOREIGN_PATHS`, already filtered out before indexing) or listed in
    `ABSENT_TESSERA_PATHS` with a stated reason. That keeps the deliberate behaviour — a
    retired path stays governed, and its ADR fires if anyone recreates it — while making a
    genuinely foreign path impossible to add silently.

    Both directions, because a one-way check rots: a declaration whose path has come BACK is
    stale and is reported, so the list cannot quietly accumulate entries that stopped being
    true. That is the DeepSeek gate's own property (ADR-0024 §4) and the second half of what
    that ADR adopted.
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import decision_surface
        from repo_paths import _DOWNSTREAM, _OTHER_REPOS
        index = decision_surface.build_index()
    except Exception as exc:
        return [f"cannot cross-check the decision-surface index: {exc}"]
    try:
        canonical = _prefix_meter().canonical_path
    except Exception:
        canonical = lambda root, ref: root / ref                          # noqa: E731

    bad = []
    # A key in two dicts is a CONTRADICTION, not a merge. `{**a, **b}` let the last one win
    # silently, which is the exact conflation repo_paths' docstring exists to end: marking a
    # path foreign ALSO drops it from the index, so a path in both would stop being governed
    # while still being declared ours-and-gone, with nothing reporting the disagreement.
    # itertools.combinations, NOT a name comparison. The first version guarded pairs with
    # `if a_name >= b_name: continue`, which is True for EVERY pair here ("_" sorts above
    # "A"), so the duplicate check never executed once — decoration that read as a guard.
    # Caught by the test written for it, not by inspection.
    declared = (("_OTHER_REPOS", _OTHER_REPOS), ("_DOWNSTREAM", _DOWNSTREAM),
                ("ABSENT_TESSERA_PATHS", ABSENT_TESSERA_PATHS))
    for (a_name, a), (b_name, b) in itertools.combinations(declared, 2):
        for dup in sorted(set(a) & set(b)):
            bad.append(f"scripts/repo_paths.py: {dup!r} is in BOTH {a_name} and {b_name} — "
                       f"'another repo's' and 'ours, absent' are different answers and the "
                       f"foreign one silently wins, un-governing the path")
    for name, group in declared:
        for path, reason in group.items():
            if not reason.strip():
                bad.append(f"scripts/repo_paths.py: {path!r} in {name} is declared with no "
                           f"reason — the reason is what stops the next reader inferring "
                           f"the set's meaning")

    # THE SAME EXEMPTION SET AND THE SAME RESOLVER AS `referenced-paths-exist`, deliberately.
    # The first version used a bare `(ROOT / path).exists()` and honoured only
    # ABSENT_TESSERA_PATHS. On a CLEAN CLONE that produced 7 findings where its sibling
    # produced 0 — `.claude/{skills,commands,agents}` are gitignored symlinks `install.sh`
    # creates, and `.claude/settings.local.json` is gitignored runtime state — so doccheck,
    # a pre-commit BLOCKER, refused every commit before install had ever run. That is the
    # regression the PATH_ALLOWLIST block above records for 2026-08-09, re-committed by
    # someone editing that very block. Worse, the old remedy text said "add it to
    # FOREIGN_PATHS", which for settings.local.json would have rebuilt the 2026-08-15 defect.
    # ABSENT_TESSERA_PATHS counts as a declaration HERE, unlike in referenced-paths-exist,
    # where it is scoped to HISTORY_DOCS. This check asks 'is it declared anywhere'; that
    # one asks 'may THIS doc say it exists'. Different questions, deliberately.
    exempt = PATH_ALLOWLIST | PLANNED_PATHS | frozenset(ABSENT_TESSERA_PATHS)
    for path in sorted(index):
        if any(path.rstrip("/") == p or path.startswith(p + "/") for p in exempt):
            continue
        if canonical(ROOT, path).exists():
            continue
        sources = ", ".join(sorted({e["doc"] for e in index[path]}))
        bad.append(
            f"{sources}: `{path}` is indexed as a governing Tessera path but is not on disk "
            f"and is not declared. Declare it: repo_paths.FOREIGN_PATHS (another repo's or a "
            f"downstream's), repo_paths.ABSENT_TESSERA_PATHS (ours, deliberately GONE), or "
            f"doccheck.PLANNED_PATHS (ours, deliberately NOT BUILT YET) — with a reason")

    for path in sorted(ABSENT_TESSERA_PATHS):
        if canonical(ROOT, path).exists():
            bad.append(f"scripts/repo_paths.py: {path!r} is declared GONE but EXISTS — the "
                       f"declaration is stale; drop it so the path is checked normally")
    return bad


def check_adr_status_matches_index() -> list[str]:
    """An ADR's own `Status:` line must agree with its row in the ADR index.

    Found 2026-08-17 by review, during ADR-0024. `docs/adr/0011-sqlfluff-evaluation.md` read
    `Status: Watching` with a live `Next check: 2026-09-19`, while the index row had said
    `Superseded by ADR-0012` since 2026-07-22 — ADR-0012's own title is "supersedes ADR-0011".
    So for 26 days ADR-0011 presented as an OPEN decision awaiting a re-check, and the count of
    live review cadences was wrong in every artifact that quoted it.

    Neither side is authoritative here, deliberately: the check reports disagreement and a human
    decides which is stale. That is the honest contract when two hand-written records overlap —
    picking a winner would have silently rewritten whichever one happened to be right.

    Why this class matters more than a normal doc claim: `decision_surface` renders the ADR's own
    Status into the pre-edit block, so a stale one does not merely sit in a file — it is injected
    as current governance before an edit. A decision that reads `Watching` when it is settled
    invites re-litigating a closed question; one that reads `Accepted` when superseded invites
    acting on a retired decision, which is the failure ADR-0008's 12-day gap already cost once.
    """
    index = ROOT / "docs" / "adr" / "README.md"
    if not index.exists():
        return ["docs/adr/README.md missing — cannot cross-check ADR statuses"]
    index_text = index.read_text()
    rows = {num: [c.strip() for c in body.split("|")][-1]
            for num, body in _ADR_INDEX_ROW.findall(index_text)}
    bad = []
    for adr in sorted((ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        num = adr.name[:4]
        if num not in rows:
            # ABSENT is adr-index-complete's case; do not double-report. PRESENT-BUT-UNPARSEABLE
            # is nobody's, and skipping it silently is how this check went vacuous once already:
            # that sibling's regex is looser, so it passes on exactly the rows this one cannot
            # read, and a real disagreement went unowned. Detected with an independent, looser
            # probe than the row regex — sharing it would reproduce the blind spot.
            if re.search(rf"^\|\s*{num}\s*\|", index_text, re.M):
                bad.append(
                    f"docs/adr/README.md: the row for ADR {num} exists but this check cannot "
                    f"parse it, so its status is unverified — fix the row's shape, and note "
                    f"adr-index-complete passes on it, so nothing else is covering this")
            continue
        m = _ADR_STATUS.search(adr.read_text())
        if not m:
            bad.append(f"docs/adr/{adr.name}: no `- **Status:**` line to cross-check")
            continue
        got, want = _adr_verdict(m.group(1)), _adr_verdict(rows[num])
        # A superseder id on only ONE side is the same "qualifier in one place" case the
        # verdict comparison exists to tolerate — `Superseded` and `Superseded by ADR-0012`
        # agree on the verdict and one is merely more specific. Only two DIFFERENT ids are a
        # real conflict, and that one matters: pointing a reader at the wrong successor is
        # worse than pointing at none. Without this the check FIRED on records that agree, in
        # a pre-commit blocker, contradicting its own docstring (review, 2026-08-17).
        if got[0] == want[0] and None in (got[1], want[1]):
            continue
        if got != want:
            bad.append(
                f"docs/adr/{adr.name}: Status says {m.group(1).strip()!r} but the ADR index row "
                f"says {rows[num]!r} — one of them is stale, and the ADR's own line is what "
                f"decision_surface injects before an edit")
    return bad



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


METERED_FIGURE = re.compile(r"METERED [\d-]+: ([\d,]+) tokens tracked")
PREFIX_BAND = 0.05


def check_eager_prefix_figure_is_current() -> list[str]:
    """The metered eager-prefix figure in the observatory must match what the meter measures.

    ADDED 2026-08-09 (ADR-0021). `docs/observatory.md` carried "~15,600 tokens" as a one-shot
    chars/4 estimate taken on 2026-07-30 and never recomputed, while the standing-patterns
    split and repeated CLAUDE.md growth moved the composition underneath it. Nothing could
    have said so: a number frozen in prose is a doc claim, and this file exists because doc
    claims drift.

    Deliberately a DRIFT check and not a ceiling. `docs/observatory.md` → "The eager prefix
    is ~15.6k tokens — and the size of it is NOT the argument" established that the count is
    an artifact and the pain (dilution) is unmeasured; failing a commit on a threshold would
    be principle #3's error aimed at the eager load. This asserts only that the recorded
    number is still true.

    The 5% band mechanizes the "~" the prose actually claims. Exact equality would fire on
    every wording tweak to CLAUDE.md, and a check that fires on noise teaches `--no-verify`
    — which is how a load-bearing check stops being load-bearing.

    Only the TRACKED total is asserted. `prefix_meter` also measures the handoff surfacer
    (varies with fired triggers) and the Mnemos checkpoint (machine-local, gitignored);
    asserting either would make this fail differently on every clone.

    CORRECTED 2026-08-09, same day, by `bin/tessera-verify` — the paragraph above was true
    of what this check EXCLUDED and false about what it included. `.claude/skills` is a
    gitignored symlink `install.sh` creates, so on a fresh clone the two eagerly-imported
    SKILL.md files were absent, the meter silently skipped them, and this check went red
    at -37% telling the reader to record a figure that was wrong. The claim "cannot fail
    differently on every clone" was being violated by the very component it named. Fixed
    in `prefix_meter._canonical`, which resolves an import to its tracked source. Kept as
    a correction rather than a rewrite because the docstring asserting the property while
    breaking it is the more useful thing to have on the record.
    """
    doc = ROOT / "docs" / "observatory.md"
    if not doc.exists():
        return []
    found = METERED_FIGURE.search(doc.read_text())
    if not found:
        return ["docs/observatory.md: no `METERED <date>: <n> tokens tracked` figure — "
                "the eager prefix is unmetered again, so nothing can detect its drift"]
    claimed = int(found.group(1).replace(",", ""))
    # Two steps, not one. IMPORT failure must catch broadly — a broken sibling raises
    # SyntaxError, not ImportError, and the first version of this fix caught only the
    # latter and still died on the case it was written for. MEASUREMENT failure stays
    # narrow, so a genuine bug in the meter surfaces instead of being swallowed.
    try:
        meter = _prefix_meter()
    except Exception as exc:
        return [f"scripts/prefix_meter.py cannot be imported ({exc}) — the figure in "
                f"docs/observatory.md is unverifiable, not confirmed"]
    try:
        actual = meter.tracked_total(ROOT)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return [f"scripts/prefix_meter.py could not measure the eager prefix ({exc}) — "
                f"the figure in docs/observatory.md is unverifiable, not confirmed"]
    if not actual:
        return ["scripts/prefix_meter.py measured 0 tokens of eager prefix — either "
                "CLAUDE.md's @ imports are gone or the meter is broken; both are findings"]
    if abs(actual - claimed) / actual > PREFIX_BAND:
        drift = (actual - claimed) / actual      # same denominator as the band, or the
        return [f"docs/observatory.md: METERED figure is {claimed:,} tokens but "
                f"scripts/prefix_meter.py measures {actual:,} ({drift:+.0%}) — re-run the "
                f"meter and update the figure and its composition breakdown"]
    return []


def check_mirror_links_are_symlinks() -> list[str]:
    """The `.claude` dogfood mirrors must be symlinks to their canonical dirs, or absent.

    ADDED 2026-08-09. `bin/tessera-verify` and arbiter independently flagged that
    `prefix_meter.canonical_path` prefers the literal path, so a REAL `.claude/skills`
    directory holding a stale copy would be measured, and a doc naming a deleted skill
    would go green. Both framed it as a resolver-ordering choice between two consumers
    that want opposite things — the meter wants what actually loads, this file wants the
    tracked source.

    **It is neither. It is an unenforced precondition.** When the path is a symlink the
    two resolutions are the SAME FILE and no consumer can disagree; they diverge only in
    a state nothing should create. So this asserts the shape and the question dissolves —
    strictly better than detecting divergence after the fact, and it needs no definition
    of "diverged".

    Note on the evidence, because it corrected a mistake in how the finding was weighed:
    two reviewers reading the same code and noting the same branch is ONE finding twice,
    not independent corroboration. What actually settled it was reading `install.sh` and
    discovering neither reviewer's implied premise held — nothing created these at all.

    ABSENT IS GREEN, deliberately: that is the state of every fresh clone before
    `./install.sh`, and this check runs in the pre-commit hook. Absence is machine state
    and belongs to install.sh's `verify()`; a wrong SHAPE is a repo-structural fact and
    belongs here. Same split the doc-claims contract draws — existence is a local fact,
    the shared one is what gets asserted.
    """
    bad = []
    for mirror, canonical in {".claude/skills": "skills", ".claude/commands": "commands",
                              ".claude/agents": "agents"}.items():
        link, target = ROOT / mirror, ROOT / canonical
        if not link.exists() and not link.is_symlink():
            continue                                    # pre-install; verify() owns this
        if not link.is_symlink():
            bad.append(f"{mirror} exists but is NOT a symlink — a real directory here "
                       f"shadows {canonical}/ with a copy nothing syncs")
        elif not link.exists():
            # Dangling. Caught explicitly: without this it would fall to the target branch
            # and PASS whenever the canonical dir is also missing.
            bad.append(f"{mirror} is a dangling symlink to {os.readlink(link)}")
        elif link.resolve() != (ROOT / canonical).resolve():
            # COMPARE THE TARGET UNCONDITIONALLY. This read `target.exists() and …` for four
            # hours: with the canonical dir absent, the condition short-circuited and a
            # symlink pointing at a WRONG BUT EXISTING path passed silently. Demonstrated by
            # arbiter 2026-08-09 and reproduced — `.claude/skills -> ../elsewhere` with no
            # `skills/` returned clean. A representable divergence, inside the check whose
            # entire purpose is to make divergence unrepresentable. `Path.resolve()` is
            # non-strict, so it compares fine when the canonical dir does not exist.
            bad.append(f"{mirror} is a symlink to {link.resolve()}, not {canonical}/")
    return sorted(bad)


def check_checkpoint_budget_matches_p3() -> list[str]:
    """The delivery budget is defined TWICE; assert the two literals agree.

    `bin/tessera-watch` (P3) reports a checkpoint that is over budget; since 2026-08-10
    `scripts/mnemos/checkpoint.py` warns about it at WRITE time, which is the only
    position from which the news can arrive before the harm. Two mechanisms, one number,
    and they cannot share a constant: `bin/` is stdlib-only (`bin-scripts-are-stdlib-only`)
    so tessera-watch cannot import mnemos.

    Unavoidable duplication is fine; UNGUARDED duplication is the shape this repo keeps
    paying for (the fixer and the detector drifting apart). If these diverge the failure
    is quiet in the worst direction: the writer says nothing while the watcher goes red,
    or the writer cries wolf on payloads P3 considers fine.
    """
    found = {}
    for path, name in (("bin/tessera-watch", "RESTORE_BUDGET_BYTES"),
                       ("scripts/mnemos/checkpoint.py", "CHECKPOINT_BUDGET_BYTES")):
        # Guarded, and the guard is the point: an unguarded read_text() here crashed the
        # WHOLE doccheck process under a synthetic ROOT (caught by
        # test_p8_leaves_docchecks_root_where_it_found_it, 2026-08-10). That is the same
        # class fixed across tessera-watch the day before — one check taking the process
        # down means 44 others never run, and this file's contract is that a check
        # REPORTS, never raises.
        #
        # The `except OSError` is NOT belt-and-braces. The first version guarded only
        # `exists()`, and `bin/tessera-verify` refuted the "never raises" claim within the
        # hour: a DIRECTORY at that path, or `chmod 000`, both exist and both raise. Fixing
        # absent-but-not-unreadable is fixing the row and not the pattern (#11) — in the
        # commit whose message claimed the class was handled.
        # One read, not exists()-then-read: the two-step version reports "unreadable" for
        # an absent file unless it keeps a separate exists() branch, and a separate branch
        # is also a TOCTOU gap. FileNotFoundError IS the absence, so name it that way.
        source = ROOT / path
        try:
            text = source.read_text()
        except FileNotFoundError:
            return [f"{path} is missing — the budget guard cannot compare"]
        except (OSError, UnicodeDecodeError) as exc:
            # UnicodeDecodeError subclasses ValueError, NOT OSError. The version that
            # caught only OSError was refuted by bin/tessera-verify with binary content at
            # the path: it escaped, propagated out of run(), and 0 of 45 checks completed —
            # under a comment claiming the class was fixed. THIRD row-fix of this same
            # class in one session. The row is fixed here; the PATTERN is that doccheck's
            # run() has no per-check isolation, which `tessera-watch.evaluate()` was given
            # on 2026-08-09 for exactly this reason. See docs/observatory.md.
            return [f"{path} is unreadable ({type(exc).__name__}) — "
                    f"the budget guard cannot compare"]
        m = re.search(rf"^{name} = ([\d_]+)", text, re.M)
        if not m:
            return [f"{path} no longer defines {name} — the budget guard cannot compare"]
        found[path] = int(m.group(1).replace("_", ""))

    values = set(found.values())
    if len(values) > 1:
        pretty = ", ".join(f"{p} = {v:,}" for p, v in sorted(found.items()))
        return [f"delivery budget has diverged between its two definitions: {pretty}"]
    return []


def check_icpg_test_exists_paths_are_real() -> list[str]:
    """Every `test_exists("path")` predicate in the iCPG graph names a file on disk.

    THIS EXISTS TO MAKE A JUSTIFICATION TRUE, and the ordering was the whole point.
    `scripts/mnemos/checkpoint.py`'s `STATIC_PREDICATE` filter drops static constraints
    from the checkpoint payload on the grounds that they are "asserted by something
    stronger" — doccheck plus the pre-commit gate. That was true for `file_exists(` and
    NOT for `test_exists(`, so widening the filter first would have silently dropped a
    class nothing else asserted. The observatory records the measurement: deleting the
    one `test_exists` path today does turn doccheck red, but only INCIDENTALLY — because
    that particular file happens to be cited in two documents. A
    `test_exists("some/undocumented/test.py")` would have no cover at all.

    This makes the coverage a property of the predicate rather than a coincidence of
    citation, which is what the filter's justification actually claims.

    Skips cleanly when `.icpg/reason.db` is absent — it is gitignored runtime state that
    `install.sh` owns, and a fresh clone must stay green (verified 2026-08-10 by cloning:
    doccheck was 46/46 pre-install). A check that fails on a clean clone is the exact
    defect class this repo spent 2026-08-09 removing.
    """
    db = ROOT / ".icpg" / "reason.db"
    if not db.exists():
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT invariants, preconditions, postconditions FROM reasons").fetchall()
        conn.close()
    except (sqlite3.Error, OSError):
        # Unreadable runtime state is not a doc claim. Report nothing rather than
        # converting a local environment problem into a blocked commit.
        return []
    # PARSE THE JSON, do not regex the raw column. These are stored as JSON lists, so the
    # column literally contains `test_exists(\"path\")` — backslash before every quote —
    # and a regex written against the predicate's SOURCE form silently matches nothing.
    # The first version of this check did exactly that and reported clean over a planted
    # violation: decoration, caught only by planting. (2026-08-10.)
    pattern = re.compile(r'test_exists\(\s*["\']([^"\']+)["\']\s*\)')
    missing = set()
    for row in rows:
        for field in row:
            try:
                predicates = json.loads(field) if field else []
            except (ValueError, TypeError):
                continue
            if not isinstance(predicates, list):
                continue
            for predicate in predicates:
                for path in pattern.findall(str(predicate)):
                    if not (ROOT / path).exists():
                        missing.add(path)
    return [f".icpg: an intent asserts test_exists({p!r}) — not on disk"
            for p in sorted(missing)]


CHECKS = {
    "icpg-test-exists-paths-are-real": check_icpg_test_exists_paths_are_real,
    "bare-python3-hook-scripts-are-probed": check_bare_python3_hook_scripts_are_probed,
    "checkpoint-budget-matches-p3": check_checkpoint_budget_matches_p3,
    "mirror-links-are-symlinks": check_mirror_links_are_symlinks,
    "eager-prefix-figure-is-current": check_eager_prefix_figure_is_current,
    "tier-vocabulary-is-consistent": check_tier_vocabulary_is_consistent,
    "handoff-retires-its-own-figures": check_handoff_retires_its_own_figures,
    "drift-dimensions-have-producers": check_drift_dimensions_have_producers,
    "chaos-suite-is-reachable": check_chaos_suite_is_reachable,
    "chaos-probe-count-is-current": check_chaos_probe_count_is_current,
    "session-logs-are-repo-anchored": check_session_logs_are_repo_anchored,
    "standing-patterns-are-surfaced": check_standing_patterns_are_surfaced,
    "standing-patterns-fit-the-cap": check_standing_patterns_fit_the_cap,
    "docs-name-the-right-patterns-emitter": check_docs_name_the_right_patterns_emitter,
    "decision-surface-is-wired": check_decision_surface_is_wired,
    "decision-surface-honors-path-exemptions": check_decision_surface_honors_path_exemptions,
    "decision-surface-deps-ship-downstream": check_decision_surface_deps_ship_downstream,
    "pretooluse-hooks-reach-the-model": check_pretooluse_hooks_reach_the_model,
    "referenced-paths-exist": check_referenced_paths_exist,
    "sibling-paths-exist": check_sibling_paths_exist,
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
    "promo-adr-timeline-is-complete": check_promo_adr_timeline_is_complete,
    "adr-execution-recorded": check_adr_execution_recorded,
    "compaction-threshold-qualified": check_compaction_threshold_qualified,
    "gate-recording-not-recall": check_gate_recording_not_claimed_as_recall,
    "tessera-yml-is-tracked": check_tessera_yml_is_tracked,
    "ignored-test-suites-are-run": check_ignored_test_suites_are_run,
    "spend-guard-is-wired": check_spend_guard_is_wired,
    "spend-backstop-is-wired": check_spend_backstop_is_wired,
    "verify-scan-is-wired": check_verify_scan_is_wired,
    "verdict-channel-literals-match-contract": check_verdict_channel_literals_match_contract,
    "runtime-state-is-not-tracked": check_runtime_state_is_not_tracked,
    "no-bare-python3-with-toolchain-import": check_no_bare_python3_with_toolchain_import,
    "bin-scripts-are-stdlib-only": check_bin_scripts_are_stdlib_only,
    "safety-scripts-run-on-system-python": check_safety_scripts_run_on_the_system_python,
    "test-command-is-not-a-bare-interpreter": check_test_command_is_not_a_bare_interpreter,
    "unrunnable-hooks-report-themselves": check_unrunnable_hooks_report_themselves,
    "adr-references-resolve": check_adr_references_resolve,
    "absent-index-paths-are-declared": check_absent_index_paths_are_declared,
    "promo-deploy-marker-is-current": check_promo_deploy_marker_is_current,
    "adr-status-matches-index": check_adr_status_matches_index,
    "superseded-status-is-accountable": check_superseded_status_is_accountable,
    "insert-or-ignore-needs-a-real-key": check_insert_or_ignore_needs_a_real_key,
}


def run_detailed() -> dict[str, tuple[list[str], BaseException | None]]:
    """Every check, ISOLATED. Returns {name: (findings, exception_or_None)}.

    WHY THE ISOLATION IS HERE AND NOT AT EACH CALL SITE. `run()` used to be a one-line
    dict comprehension, so any check that raised took the process down and 0 of 45
    reported. On 2026-08-10 one new check hit that three times in a row — an unguarded
    `read_text()`, then an `exists()`-only guard (a directory and `chmod 000` both exist
    and raise), then an `OSError`-only guard (`UnicodeDecodeError` subclasses ValueError)
    — each fix committed under a comment claiming the CLASS was handled. A check's author
    can always miss one more exception type. `bin/tessera-watch.evaluate()` was given the
    same treatment on 2026-08-09; doccheck, the gate that actually blocks commits, was
    not. (#11: fix the pattern, not the row.)

    WHY A SECOND CHANNEL RATHER THAN A MARKER STRING. A crash and a false doc claim are
    different facts, and consumers must not re-derive which is which by substring — that
    is the naming-convention keying #10's corollary warns about. P8 in particular built
    its LOUD path on `run()` raising; if isolation just stopped it raising, P8 would
    silently downgrade every crash to an ordinary fire, which is the 2026-08-09
    `render()`-never-read-the-crashed-field defect one layer up.

    WHAT THIS DOES NOT COVER, stated because blanket safety would be a false claim: check
    BODIES only. A SyntaxError in this module, an exception in `render()`, or an import
    failure still take the run down — and the pre-commit hook deliberately keeps failing
    open for exactly that catastrophic case.
    """
    results: dict[str, tuple[list[str], BaseException | None]] = {}
    for name, check in CHECKS.items():
        try:
            results[name] = (list(check()), None)
        except Exception as exc:                      # noqa: BLE001 — that is the point
            results[name] = ([f"check crashed: {type(exc).__name__}: {exc}"], exc)
    return results


def run() -> dict[str, list[str]]:
    """Findings only, crashes flattened in as findings. Kept for consumers that only ask
    'is anything wrong' — `run_detailed()` is what distinguishes wrong from broken."""
    return {name: found for name, (found, _) in run_detailed().items()}


def render(results: dict) -> str:
    """Accepts either shape: {name: findings} or {name: (findings, exc)}."""
    detailed = {
        name: value if isinstance(value, tuple) else (value, None)
        for name, value in results.items()
    }
    crashed = [(n, f[0]) for n, (f, e) in detailed.items() if e is not None]
    violations = [(n, v) for n, (vs, e) in detailed.items() if e is None for v in vs]

    if not violations and not crashed:
        return f"✓ docs honest — {len(CHECKS)} checks, 0 false claims"

    lines = []
    if crashed:
        # Its OWN section. Folding crashes into the false-claim count would make the
        # headline itself an untrue claim about what happened.
        lines.append(f"{len(crashed)} check(s) CRASHED and could not report:")
        lines += [f"  💥 [{name}] {msg}" for name, msg in crashed]
        if violations:
            lines.append("")
    if violations:
        lines.append(f"Docs make {len(violations)} claim(s) that are no longer true:")
        lines += [f"  🔴 [{name}] {v}" for name, v in violations]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Assert docs' checkable claims are still true.")
    ap.add_argument("--json", action="store_true", help="machine output")
    ap.add_argument("--stamp-deploy", action="store_true",
                    help="record the promo page as deployed (run AFTER uploading)")
    args = ap.parse_args()
    if args.stamp_deploy:
        return stamp_deploy()
    detailed = run_detailed()
    if args.json:
        print(json.dumps({n: f for n, (f, _) in detailed.items()}, indent=2))
    else:
        print(render(detailed))
    # A crashed check BLOCKS (decision 2026-08-10). The pre-commit rule it reverses —
    # "a crashing checker must not wedge every commit" — was written when a crash killed
    # the WHOLE run; an isolated, named crash beside 44 working checks is a defect to fix,
    # and `--no-verify` is still the documented escape.
    return 1 if any(found for found, _ in detailed.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
