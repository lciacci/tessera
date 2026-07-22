#!/usr/bin/env python3
"""Tests for the ADR-0004 settings auto-patch.

The failure this guards: `tessera-hooks thaw` deletes local hook copies. If settings.json has
no `elif` reaching ~/.claude/templates, every mnemos hook then resolves to nothing and exits 0
— SILENTLY, while still looking wired. This patcher is what makes a grandfathered repo
thawable, so a bug here disables instrumentation across a whole project without a symptom.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import patch_settings as ps  # noqa: E402

LOCAL_ONLY = ('if [ -x ".claude/scripts/mnemos-pre-edit.sh" ]; then '
              'exec ".claude/scripts/mnemos-pre-edit.sh"; fi; exit 0')


def _settings(cmd, statusline=None):
    d = {"hooks": {"PreToolUse": [{"hooks": [{"command": cmd}]}]}}
    if statusline:
        d["statusLine"] = {"type": "command", "command": statusline}
    return d


def test_local_only_gets_the_global_fallback():
    out, changed, unknown = ps.patch(_settings(LOCAL_ONLY))
    assert changed == ["mnemos-pre-edit.sh"]
    assert unknown == []
    cmd = out["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert 'elif [ -x "$HOME/.claude/templates/mnemos-pre-edit.sh" ]' in cmd
    assert 'exec "$HOME/.claude/templates/mnemos-pre-edit.sh"' in cmd
    assert cmd.endswith("fi; exit 0"), "must preserve the trailing no-op exit"
    # The local branch still wins — freeze must keep working after a patch.
    assert cmd.index('.claude/scripts/') < cmd.index('templates/')


def test_already_patched_is_untouched():
    """Idempotent: running it twice must not double-append a branch."""
    once, _, _ = ps.patch(_settings(LOCAL_ONLY))
    cmd = once["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    twice, changed, _ = ps.patch(_settings(cmd))
    assert changed == []
    assert twice["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == cmd


def test_statusline_bare_path_is_patched():
    """Statusline was local-only while every sibling had the fallback — the observatory
    calls that the literal root cause of F-003's first sighting."""
    out, changed, unknown = ps.patch(
        _settings(LOCAL_ONLY, statusline=".claude/scripts/mnemos-statusline.sh"))
    assert "mnemos-statusline.sh (statusLine)" in changed
    assert unknown == []
    cmd = out["statusLine"]["command"]
    assert 'templates/mnemos-statusline.sh' in cmd
    assert cmd.startswith("sh -c ")


def test_unrecognised_shape_is_reported_not_rewritten():
    """A settings patcher that guesses is worse than one that stops."""
    weird = 'bash -lc "some/other/wrapper mnemos-pre-edit.sh --flag"'
    out, changed, unknown = ps.patch(_settings(weird))
    assert changed == []
    assert unknown == [weird]
    assert out["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == weird, "must not mangle it"


def test_non_mnemos_hooks_are_left_alone():
    """Gate-scan and spend hooks are project-local by design; thaw must not touch them."""
    gate = 'if [ -x ".claude/scripts/tessera-gate-scan.sh" ]; then exec ".claude/scripts/tessera-gate-scan.sh"; fi; exit 0'
    out, changed, unknown = ps.patch(_settings(gate))
    assert changed == [] and unknown == []
    assert out["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == gate


def test_main_refuses_and_writes_nothing_on_unknown(tmp_path, capsys):
    p = tmp_path / "settings.json"
    weird = 'bash -lc "wrapper mnemos-pre-edit.sh"'
    original = json.dumps(_settings(weird))
    p.write_text(original)
    assert ps.main([str(p)]) == 1
    assert p.read_text() == original, "refusal must leave the file byte-identical"


def test_main_dry_run_writes_nothing(tmp_path):
    p = tmp_path / "settings.json"
    original = json.dumps(_settings(LOCAL_ONLY))
    p.write_text(original)
    assert ps.main([str(p), "--dry-run"]) == 0
    assert p.read_text() == original


def test_main_patches_and_is_valid_json(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(_settings(LOCAL_ONLY)))
    assert ps.main([str(p)]) == 0
    reloaded = json.loads(p.read_text())   # must not corrupt the file
    assert "templates/mnemos-pre-edit.sh" in \
        reloaded["hooks"]["PreToolUse"][0]["hooks"][0]["command"]


if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
