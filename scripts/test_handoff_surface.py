"""The SessionStart handoff surfacer must never stitch a new heading onto old priorities.

FOUND 2026-07-12, on the one artifact that tells tomorrow what to do.

The surfacer took its HEADING from `grep -m1` (the first handoff block — correct) and its
PRIORITY LIST from an awk that scanned the WHOLE FILE for `^## Next session`. When the newest
handoff didn't use that exact heading, awk fell through to the PREVIOUS handoff's section and
printed its priorities.

The output was perfectly coherent: today's title over yesterday's todo list. A fresh session
would have been told to go do "Spec 06 (BLOCKS unsupervised work)" and "the venv (P9 is
firing)" — both finished that same day. Neither half was wrong on its own.

**It did not break. It produced something plausible.** That is the failure class this repo
spent a whole session on (docs/observatory.md → "Fail-open everywhere"), sitting on the
handoff itself — and nothing could have told us.
"""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SURFACE = REPO / ".claude" / "scripts" / "tessera-watch-surface.sh"

TWO_HANDOFFS = """# Active Focus

## Handoff — pick up here (2026-07-12, today)

Some prose.

### Where to pick up

1. **THE CURRENT THING** — do this one.
2. **The other current thing.**

---

## Handoff — 2026-07-11 (yesterday, superseded)

## Next session — priorities

1. **STALE PRIORITY** — this was finished yesterday.
2. **ALSO STALE.**
"""

NO_LIST = """# Active Focus

## Handoff — pick up here (2026-07-12)

Prose only. Someone forgot the numbered list.

---

## Handoff — 2026-07-11

## Next session — priorities

1. **STALE PRIORITY** — must NOT be surfaced.
"""


def _surface(tmp_path: Path, handoff: str) -> str:
    (tmp_path / "_project_specs" / "todos").mkdir(parents=True)
    (tmp_path / "_project_specs" / "todos" / "active.md").write_text(handoff)
    out = subprocess.run(["bash", str(SURFACE)], cwd=tmp_path, input="{}",
                         capture_output=True, text=True)
    return out.stdout


def test_never_surfaces_a_previous_handoffs_priorities(tmp_path):
    """THE BUG. Extraction must be scoped to the first handoff block."""
    out = _surface(tmp_path, TWO_HANDOFFS)
    assert "THE CURRENT THING" in out
    assert "STALE PRIORITY" not in out, "surfaced a superseded handoff's priorities"
    assert "ALSO STALE" not in out


def test_says_so_LOUDLY_when_the_handoff_has_no_priority_list(tmp_path):
    """A surfacer that silently prints nothing is indistinguishable from one that has nothing
    to print. That is the fail-open class. It must be loud instead — and it must still not
    reach into the previous handoff to fill the gap, which is what the bug did."""
    out = _surface(tmp_path, NO_LIST)
    assert "NO PRIORITY LIST" in out
    assert "STALE PRIORITY" not in out


def test_the_real_repo_surfaces_its_current_priorities(tmp_path):
    """The live handoff must actually surface. Seeding this green once is what makes a future
    red mean something."""
    out = subprocess.run(["bash", str(SURFACE)], cwd=REPO, input="{}",
                         capture_output=True, text=True).stdout
    assert "TESSERA HANDOFF" in out
    assert "NO PRIORITY LIST" not in out, "the live handoff has no numbered priority list"
