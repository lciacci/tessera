"""The decision surface must find the ADR that governs a file — before it is edited.

BUILT 2026-07-24, the day ADR-0004 was missed on a change it directly governs. The anchoring
fix would have cd'd every downstream hook to $HOME because the two-tier distribution the ADR
describes was never read. The ADR was in the repo, referenced from CLAUDE.md, and names the
exact failure mode. Nothing made it land.

These tests assert the mechanism is not vacuous: it must find a real ADR for a real path, it
must generalise by prefix (an ADR naming a directory covers files under it), and it must be
LOUD rather than silent when it cannot answer — the lesson of that same day.
"""
import json
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


# --- truncation notice ----------------------------------------------------------------
# Until 2026-08-17 the render ended at `Read before editing:` and never said that MAX_DOCS
# had discarded anything. It cuts something on 46 of 146 index keys, and because the sort is
# ADR-filename ascending, what it cuts is the NEWEST: ADR-0022 was invisible on
# scripts/doccheck.py, ADR-0015 on bin/tessera-watch. Standing pattern #12, in the hook built
# to defeat silent failure. Counts below are HARDCODED, never computed from lookup_split —
# a test that derives its expectation from the code under test cannot fail with it.


def _idx(n_adr, n_obs, path="scripts/thing.py"):
    """An index with a known, hand-counted number of records on one path."""
    entries = [{"doc": f"docs/adr/{i:04d}-x.md", "title": f"ADR-{i:04d} (Accepted) t{i}",
                "gloss": "", "kind": "adr", "sort": f"{i:04d}-x.md", "execution": ""}
               for i in range(1, n_adr + 1)]
    entries += [{"doc": "docs/observatory.md", "title": f"obs {j}", "gloss": "",
                 "kind": "observatory", "sort": "z"} for j in range(n_obs)]
    return {path: entries}


def test_notice_names_the_cut_adrs_and_counts_the_rest():
    idx = _idx(n_adr=4, n_obs=5)                       # 9 records, 3 shown -> 6 cut
    shown, cut = ds.lookup_split("scripts/thing.py", idx)
    out = ds.render("scripts/thing.py", shown, {}, cut)
    assert "6 more record(s) NOT shown" in out, out
    assert "ADR-0004" in out, "the cut ADR must be named, not merely counted"
    assert "5 observatory entries" in out, out


def test_no_notice_when_nothing_is_cut():
    """Noise on every hit is how a real warning gets skipped — the reasoning that stopped P3
    firing forever on an unfixable state."""
    shown, cut = ds.lookup_split("scripts/thing.py", _idx(n_adr=2, n_obs=1))
    assert cut == []
    assert "NOT shown" not in ds.render("scripts/thing.py", shown, {}, cut)


def test_notice_itself_never_truncates_silently():
    """The notice must not commit the defect it reports. Every cut ADR id is listed in full;
    only the observatory remainder is a count, and the count is explicit."""
    idx = _idx(n_adr=9, n_obs=0)                       # 9 ADRs, 3 shown -> 6 cut, all ADRs
    shown, cut = ds.lookup_split("scripts/thing.py", idx)
    out = ds.render("scripts/thing.py", shown, {}, cut)
    for i in range(4, 10):
        assert f"ADR-{i:04d}" in out, f"ADR-{i:04d} was cut and not named"
    assert "observatory" not in out.split("NOT shown")[1].split("\n")[0]


def test_lookup_and_lookup_split_agree_on_what_is_shown():
    """lookup() is the established read used elsewhere; lookup_split must not drift from it."""
    idx = _idx(n_adr=4, n_obs=5)
    assert ds.lookup("scripts/thing.py", idx) == ds.lookup_split("scripts/thing.py", idx)[0]


def test_the_live_repo_reports_its_own_truncation():
    """Against the REAL index, not a fixture. These two files are why the notice exists."""
    idx = ds.build_index()
    for target, must_name in (("scripts/doccheck.py", "ADR-0022"),
                              ("bin/tessera-watch", "ADR-0015")):
        shown, cut = ds.lookup_split(target, idx)
        assert cut, f"{target} should still be truncated"
        out = ds.render(target, shown, {}, cut)
        assert "NOT shown" in out and must_name in out, out


def test_the_notice_reaches_the_WIRED_hook_channel(capsys):
    """The tests above all drive render() directly, which left the only channel that reaches
    the model unguarded. Review re-planted it 2026-08-17: dropping `cut` from emit_hook's
    render() call — deleting the notice from the PreToolUse envelope entirely — left all 23
    tests and doccheck green. That is standing pattern #9 inside the fix for a #12 bug: the
    mechanism runs, the audience gets nothing. This asserts the envelope, not the renderer.

    It also retires a false claim: docs/observatory.md said a re-plant 'dropping cut at the
    call site' had failed as required. It had not been tried; the break was made inside
    render(), which IS covered.
    """
    ds.emit_hook("scripts/doccheck.py")            # known-truncated in the live index
    payload = json.loads(capsys.readouterr().out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "NOT shown" in ctx, f"the truncation notice never reached the model channel: {ctx}"
    assert "ADR-0022" in ctx, "the cut ADR must be named in the envelope, not just the CLI"
