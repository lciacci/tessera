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


# ── the decision -> amendment edge (2026-07-26) ──────────────────────────────────────────

def test_amendments_link_an_adr_to_later_records_that_revisit_it():
    """The edge that was missing when a session acted on ADR-0008 and never saw the later
    observatory entry deferring it. Asserted against the REAL records, not a fixture: the
    point is that this repo's own decisions are routinely revisited."""
    import decision_amendments as da
    am = da.build_amendments()
    assert "ADR-0004" in am, "ADR-0004 is referenced all over the observatory; the edge is dead"
    assert len(am["ADR-0004"]) >= 2
    assert any(t.startswith("observatory:") for t in am["ADR-0004"])


def test_amendments_ignore_self_reference_and_earlier_adrs():
    """An ADR citing itself is not an amendment, and an EARLIER ADR citing a later one is
    background, not a revision — only later records revise."""
    import decision_amendments as da
    am = da.build_amendments()
    for adr_id, refs in am.items():
        assert not any(r.startswith(adr_id + ":") for r in refs), f"{adr_id} lists itself"
        for r in refs:
            if r.startswith("ADR-"):
                assert r.split(":")[0] > adr_id, f"{adr_id} revised by earlier {r.split(':')[0]}"


def test_amendment_lines_render_only_for_revisited_adrs():
    import decision_amendments as da
    assert da.render_amendments("ADR-9999", {}) == []
    lines = da.render_amendments("ADR-0001", {"ADR-0001": ["observatory: x", "observatory: y"]})
    assert lines and "REVISITED by 2" in lines[0]


def test_amendment_list_is_capped():
    """ADR-0008 has 15 referring records; an uncapped list would bury the decision itself."""
    import decision_amendments as da
    many = [f"observatory: e{i}" for i in range(20)]
    lines = da.render_amendments("ADR-0001", {"ADR-0001": many})
    assert len(lines) == da.MAX_AMENDMENTS + 2 and "and 16 more" in lines[-1]


def test_adr_reference_check_is_not_vacuous(tmp_path):
    """A fresh check's green proves nothing until something has been seen to make it red.

    Also pins the external-ADR scope: Open GSD's ADR-1244 is cited in the observatory as
    provenance and must NOT be flagged, while a dangling Tessera-range id must be.
    """
    import re as _re
    ours = _re.compile(r"ADR-(0\d{3})")
    assert ours.findall("cites ADR-1244 (theirs)") == [], "external ADRs must be out of scope"
    assert ours.findall("cites ADR-0099") == ["0099"], "a dangling Tessera id must be caught"
    on_disk = {p.name[:4] for p in (ds.ROOT / "docs" / "adr").glob("0*.md")}
    assert "0099" not in on_disk, "precondition: ADR-0099 must not exist for this to bite"


# ── execution warning: "decided" and "done" are different facts ────────────────────────

def test_not_yet_warns_loudly():
    """The failure this exists to stop: an unshipped ADR read as settled. On 2026-07-26 a
    session read ADR-0008's verdict and acted on it; the cut had sat unexecuted 12 days."""
    w = ds._execution_warning("- **Status:** Accepted\n- **Executed:** not yet\n")
    assert "NOT EXECUTED" in w and "settled" in w


def test_partially_executed_carries_the_remainder():
    w = ds._execution_warning(
        "- **Status:** Accepted\n- **Executed:** partially — the cut is DEFERRED to D1\n")
    assert "PARTIALLY EXECUTED" in w and "DEFERRED to D1" in w


def test_a_shipped_adr_is_annotated_silently():
    """A shipped ADR needs no annotation — noise on every hit is how a real warning gets
    skipped (the same reasoning that stopped P3 firing forever on an unfixable state)."""
    assert ds._execution_warning(
        "- **Status:** Accepted\n- **Executed:** 2026-07-26 — `bin/thing`\n") == ""


def test_an_adr_with_no_executed_line_is_silent_here():
    """doccheck's adr-execution-recorded is what demands the line; this renderer must not
    also shout about it, or one omission produces two different complaints."""
    assert ds._execution_warning("- **Status:** Accepted\n") == ""
