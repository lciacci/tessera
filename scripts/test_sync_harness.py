"""Tests for bin/tessera-sync-harness — the scaffold back-fill.

The gap it closes: `tessera-new-project` ships the harness once and nothing revisits it, so
every component added later exists only in projects scaffolded after it. Measured 2026-07-22 —
tess-dashboard had no gate harness at all, howler no spend guard, and all four pre-settempo
repos lacked remap_kind.py and the SQL gate.

(Corrected same day: an earlier version of this docstring said those repos' gate suites were
BROKEN because test_gate_emit.py imports remap_kind. False, and unchecked before being written
down — they carry OLDER test_gate_emit.py copies that never import it, and howler's suite
passes. Their real gap is staleness, which this add-only tool cannot fix and does not claim to.)

The dangerous direction is OVERWRITING. This tool runs against real projects with real
customization, so "only ever adds" is the property that has to hold under test.
"""
import importlib.machinery
import importlib.util
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_loader = importlib.machinery.SourceFileLoader(
    "tessera_sync_harness", str(REPO / "bin" / "tessera-sync-harness"))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
sh = importlib.util.module_from_spec(_spec)
_loader.exec_module(sh)


def _project(tmp_path):
    """A minimal Tessera project missing everything."""
    p = tmp_path / "proj"
    (p / ".tessera").mkdir(parents=True)
    (p / ".tessera" / "project.yml").write_text("profile: standard\nhook_distro: global\n")
    (p / ".claude").mkdir()
    (p / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))
    subprocess.run(["git", "-C", str(p), "init", "-q"], capture_output=True)
    return p


def test_identity_files_are_never_backfilled():
    """CLAUDE.md, project.yml, config.yml, FINDINGS.md carry project identity. Copying a
    reference copy over them would replace a project's description, its test command, or its
    real findings with a template."""
    for f in ("CLAUDE.md", ".tessera/config.yml", ".tessera/project.yml", "docs/FINDINGS.md",
              ".claude/settings.json", ".gitignore"):
        assert f in sh.IDENTITY, f"{f} must never be back-filled"


def test_sqlfluff_is_backfilled_not_treated_as_identity():
    """lint.sh without .sqlfluff runs stock rules = 89% whitespace noise. Shipping one without
    the other is the broken half this tool exists to prevent."""
    assert ".sqlfluff" not in sh.IDENTITY


def test_missing_hooks_ignores_mnemos_and_finds_unwired_scripts():
    ref = {"hooks": {
        "Stop": [{"hooks": [{"command": 'if [ -x ".claude/scripts/tessera-gate-scan.sh" ]; then exec ".claude/scripts/tessera-gate-scan.sh"; fi'}]}],
        "SessionStart": [{"hooks": [{"command": 'if [ -x ".claude/scripts/mnemos-session-start.sh" ]; then exec x; fi'}]}],
    }}
    out = sh.missing_hooks(ref, {"hooks": {}})
    assert len(out) == 1, "mnemos wiring is ADR-0004's business, not this tool's"
    assert out[0][0] == "Stop"


def test_missing_hooks_is_idempotent_when_already_wired():
    cmd = 'if [ -x ".claude/scripts/tessera-gate-scan.sh" ]; then exec ".claude/scripts/tessera-gate-scan.sh"; fi'
    ref = {"hooks": {"Stop": [{"hooks": [{"command": cmd}]}]}}
    assert sh.missing_hooks(ref, ref) == [], "must not duplicate an existing wiring"


def test_dry_run_writes_nothing(tmp_path):
    p = _project(tmp_path)
    before = {f: f.read_bytes() for f in p.rglob("*") if f.is_file()}
    assert sh.sync(p, apply=False) == 0
    after = {f: f.read_bytes() for f in p.rglob("*") if f.is_file()}
    assert before == after, "dry run must not touch the project"


def test_apply_adds_the_gate_harness_and_wires_it(tmp_path):
    p = _project(tmp_path)
    assert sh.sync(p, apply=True) == 0

    # Both halves: the scripts AND the hook that invokes them.
    assert (p / "scripts" / "gate" / "emit.py").is_file()
    assert (p / "scripts" / "gate" / "remap_kind.py").is_file(), \
        "the CURRENT test_gate_emit.py imports it; a fresh back-fill must stay import-closed"
    assert (p / ".claude" / "scripts" / "tessera-gate-scan.sh").is_file()

    settings = json.loads((p / ".claude" / "settings.json").read_text())
    wired = [h["command"] for g in settings["hooks"].values() for gr in g for h in gr["hooks"]]
    assert any("tessera-gate-scan.sh" in c for c in wired), "script copied but never wired"


def test_apply_never_overwrites_an_existing_file(tmp_path):
    """A project may have customized deliberately. Overwriting unread content is what the
    base skill forbids — report drift, do not 'fix' it."""
    p = _project(tmp_path)
    (p / "scripts" / "gate").mkdir(parents=True)
    custom = p / "scripts" / "gate" / "emit.py"
    custom.write_text("# deliberately customized\n")
    sh.sync(p, apply=True)
    assert custom.read_text() == "# deliberately customized\n"


def test_apply_is_idempotent(tmp_path):
    p = _project(tmp_path)
    sh.sync(p, apply=True)
    snapshot = {f.relative_to(p).as_posix(): f.read_bytes()
                for f in p.rglob("*") if f.is_file() and ".git/" not in f.as_posix()}
    sh.sync(p, apply=True)
    again = {f.relative_to(p).as_posix(): f.read_bytes()
             for f in p.rglob("*") if f.is_file() and ".git/" not in f.as_posix()}
    assert snapshot == again, "a second run must be a no-op, not a duplicate-append"


def test_refuses_a_non_tessera_directory(tmp_path):
    assert sh.main([str(tmp_path)]) == 2


def test_hookspath_is_not_set_when_it_would_shadow_existing_hooks(tmp_path):
    """core.hooksPath redirects git AWAY from .git/hooks. Setting it where real hooks live
    silently disables them — and .git/hooks is untracked, so they exist on one disk and
    nothing would ever report the loss."""
    p = _project(tmp_path)
    hooks = p / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\necho real\n")
    (hooks / "pre-commit.sample").write_text("#!/bin/sh\n")   # samples don't count

    sh.sync(p, apply=True)
    got = subprocess.run(["git", "-C", str(p), "config", "core.hooksPath"],
                         capture_output=True, text=True).stdout.strip()
    assert got == "", "must not shadow a real .git/hooks hook"
    assert (hooks / "pre-push").exists()


def test_hookspath_is_set_when_only_samples_exist(tmp_path):
    p = _project(tmp_path)
    hooks = p / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit.sample").write_text("#!/bin/sh\n")

    sh.sync(p, apply=True)
    got = subprocess.run(["git", "-C", str(p), "config", "core.hooksPath"],
                         capture_output=True, text=True).stdout.strip()
    assert got == ".githooks"


# --- --update-stale: the provenance proof ------------------------------------------------


def test_known_versions_finds_historical_blobs():
    """The proof this whole mode rests on: bytes that appear in tessera's history."""
    versions = sh.known_tessera_versions("scripts/gate/emit.py")
    assert len(versions) > 1, "emit.py has changed over time; history should show several"
    current = sh._sha((REPO / "scripts" / "gate" / "emit.py").read_bytes())
    assert current in versions, "the current file must match its own latest commit"


def test_known_versions_checks_the_bin_path_too():
    """scripts/tessera-escalate is copied from bin/tessera-escalate — the scaffold renames it,
    so provenance must look under both shapes or every downstream copy reads as customized."""
    assert sh.known_tessera_versions("scripts/tessera-escalate"), \
        "must resolve via bin/<basename>"


def test_update_stale_refreshes_a_provably_unmodified_file(tmp_path):
    p = _project(tmp_path)
    sh.sync(p, apply=True)                      # bring it up to date
    target = p / "scripts" / "gate" / "emit.py"
    current = target.read_bytes()

    # Plant a genuine OLD tessera version — provably ours, just stale.
    old = subprocess.run(["git", "-C", str(REPO), "log", "--format=%H", "--",
                          "scripts/gate/emit.py"], capture_output=True, text=True).stdout.split()[-1]
    old_blob = subprocess.run(["git", "-C", str(REPO), "show", f"{old}:scripts/gate/emit.py"],
                              capture_output=True).stdout
    target.write_bytes(old_blob)

    sh.sync(p, apply=True, update_stale=True)
    assert target.read_bytes() == current, "a provably-unmodified stale file must be refreshed"


def test_update_stale_refuses_a_customized_file(tmp_path):
    """The safety property. Bytes matching no tessera version were either customized or came
    from somewhere this tool cannot vouch for — either way, not ours to overwrite."""
    p = _project(tmp_path)
    sh.sync(p, apply=True)
    target = p / "scripts" / "gate" / "emit.py"
    target.write_text("# downstream customization nobody upstream has ever seen\n")

    sh.sync(p, apply=True, update_stale=True)
    assert target.read_text() == "# downstream customization nobody upstream has ever seen\n", \
        "must never overwrite content with no known provenance"


def test_update_stale_off_by_default_leaves_stale_files(tmp_path):
    p = _project(tmp_path)
    sh.sync(p, apply=True)
    target = p / "scripts" / "gate" / "emit.py"
    target.write_text("# stale-ish\n")
    sh.sync(p, apply=True)                      # no update_stale
    assert target.read_text() == "# stale-ish\n"
