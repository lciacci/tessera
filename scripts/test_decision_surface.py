"""The decision surface must find the ADR that governs a file — before it is edited.

BUILT 2026-07-24, the day ADR-0004 was missed on a change it directly governs. The anchoring
fix would have cd'd every downstream hook to $HOME because the two-tier distribution the ADR
describes was never read. The ADR was in the repo, referenced from CLAUDE.md, and names the
exact failure mode. Nothing made it land.

These tests assert the mechanism is not vacuous: it must find a real ADR for a real path, it
must generalise by prefix (an ADR naming a directory covers files under it), and it must be
LOUD rather than silent when it cannot answer — the lesson of that same day.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import decision_surface as ds


def test_finds_adr_0004_for_a_hook_script():
    """THE MISS. Editing a hook script must surface the hook-distribution ADR."""
    hits = ds.lookup(".claude/scripts/mnemos-pre-compact.sh", ds.build_index())
    assert any("ADR-0004" in h["title"] for h in hits), [h["title"] for h in hits]


def test_prefix_match_generalises_a_directory_reference():
    """An ADR naming `.claude/scripts/` must cover a script that did not exist when it
    was written — otherwise every new file starts unreachable."""
    index = {".claude/scripts": [{"doc": "d", "title": "ADR-9999 (Accepted) x",
                                  "gloss": "", "kind": "adr", "sort": "9999"}]}
    assert ds.lookup(".claude/scripts/brand-new.sh", index)


def test_unrelated_path_surfaces_nothing():
    """Silence must mean 'no decision governs this', so it has to be real silence."""
    assert ds.lookup("some/unrelated/path.txt", ds.build_index()) == []


def test_observatory_entries_are_scoped_to_their_own_section():
    """Paths must attach to the entry that names them, not to the whole 1000-line file —
    otherwise every path matches every entry and the output is noise."""
    index = ds.build_index()
    obs = [e for entries in index.values() for e in entries if e["kind"] == "observatory"]
    assert len({e["title"] for e in obs}) > 5, "observatory collapsed to too few entries"


def test_gloss_is_extracted_never_generated():
    """The one-liner must be the ADR's own words. A generated summary would be a second,
    driftable statement of the decision."""
    body = "# ADR-0001: T\n- **Status:** Accepted\n\n## Decision\n\nThe decision sentence is long enough to count here.\n\n## Next\n"
    assert ds._first_decision_line(body).startswith("The decision sentence")


def test_render_names_the_document_to_read():
    hits = [{"doc": "docs/adr/0004-x.md", "title": "ADR-0004 (Accepted) T",
             "gloss": "g", "kind": "adr", "sort": "4"}]
    out = ds.render("f.sh", hits)
    assert "docs/adr/0004-x.md" in out and "Read before editing" in out


def test_lowercase_cwd_still_resolves_F002():
    """F-002. macOS is case-insensitive; a cwd of .../claude/tessera (lowercase) must not
    make the hook go silently blank. This bit the hook itself the day it was built."""
    root = str(ds.ROOT)
    swapped = root.replace("/Claude/", "/claude/") if "/Claude/" in root else root.replace("/claude/", "/Claude/")
    if swapped == root:
        return  # path has no claude/Claude segment to swap on this machine
    assert ds.relative(swapped + "/scripts/doccheck.py") == "scripts/doccheck.py"


def test_hook_mode_emits_valid_pretooluse_envelope():
    """CRITICAL fix (review 2026-07-24): a PreToolUse hook's bare stdout goes to the debug
    log, NOT the model's context. The wired path must emit hookSpecificOutput.additionalContext
    JSON, or the whole mechanism is silent to its audience. Verified against the hooks docs."""
    import io, json, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ds.emit_hook(".claude/scripts/mnemos-pre-compact.sh")
    env = json.loads(buf.getvalue())
    hs = env["hookSpecificOutput"]
    assert hs["hookEventName"] == "PreToolUse"
    assert "ADR-0004" in hs["additionalContext"]


def test_hook_mode_is_silent_when_nothing_governs():
    """No governing decision -> emit NOTHING (not an empty envelope), so the hook stays quiet
    on files no ADR covers."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ds.emit_hook("some/unrelated/path.txt")
    assert buf.getvalue().strip() == ""
