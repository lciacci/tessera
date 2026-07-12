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
DOC_GLOBS = ("docs/**/*.md", "CLAUDE.md")
DOC_SKIP = ("docs/adr/",)

# A backticked token is treated as a repo path only if it starts with one of these.
REPO_DIRS = ("docs/", "scripts/", "bin/", ".claude/", "templates/", "hooks/",
             "_project_specs/", ".tessera/", "commands/", "skills/", "rules/", "agents/")

# Tokens that are illustrative, not paths: placeholders and brace-expansions.
PLACEHOLDER = re.compile(r"[{}]|/X$|NNNN|YYYY|TITLE|\.\.\.")

# Paths that legitimately aren't on disk. Every entry is a deliberate exemption with a
# reason — an unexplained allowlist is how a checker rots into theater.
PATH_ALLOWLIST = {
    # Runtime-created, never committed.
    ".mnemos", ".tessera/logs", ".tessera/escalations",
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


CHECKS = {
    "referenced-paths-exist": check_referenced_paths_exist,
    "adr-index-complete": check_adr_index_complete,
    "compaction-threshold-qualified": check_compaction_threshold_qualified,
    "gate-recording-not-recall": check_gate_recording_not_claimed_as_recall,
    "tessera-yml-is-tracked": check_tessera_yml_is_tracked,
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
