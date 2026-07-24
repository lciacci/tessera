"""anchor_settings is the FIXER for cwd-relative hook paths; doccheck._bare_hook_paths is the
DETECTOR. This suite's whole point is that they cannot drift — every fixer output must be clean
under the detector, or one flags what the other cannot fix (the ship-both-halves trap).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "hooks"))
sys.path.insert(0, str(REPO / "scripts"))
import anchor_settings as a
import doccheck


# Real downstream command shapes: two-tier mnemos (has global fallback) and local-only Tessera.
TWO_TIER = ('if [ -x ".claude/scripts/mnemos-session-start.sh" ]; then '
            'exec ".claude/scripts/mnemos-session-start.sh"; elif '
            '[ -x "$HOME/.claude/templates/mnemos-session-start.sh" ]; then '
            'exec "$HOME/.claude/templates/mnemos-session-start.sh"; fi; exit 0')
LOCAL_ONLY = ('if [ -x ".claude/scripts/tessera-gate-scan.sh" ]; then '
              'exec ".claude/scripts/tessera-gate-scan.sh"; fi; exit 0')
DOTSLASH = 'if [ -x "./.claude/scripts/x.sh" ]; then exec "./.claude/scripts/x.sh"; fi; exit 0'


def test_fixer_output_is_clean_under_the_detector():
    """THE GUARD. Anchor each real form, then assert the detector finds nothing left."""
    for cmd in (TWO_TIER, LOCAL_ONLY, DOTSLASH):
        fixed = a.anchor_command(cmd)
        assert fixed is not None, f"expected a rewrite for: {cmd}"
        assert doccheck._bare_hook_paths(fixed) == [], f"detector still flags: {fixed}"


def test_leaves_the_global_templates_branch_alone():
    fixed = a.anchor_command(TWO_TIER)
    assert '"$HOME/.claude/templates/mnemos-session-start.sh"' in fixed
    assert fixed.count("${CLAUDE_PROJECT_DIR:-.}") == 2  # both local-branch occurrences only


def test_is_idempotent():
    once = a.anchor_command(LOCAL_ONLY)
    assert a.anchor_command(once) is None  # already anchored → no change


def test_anchor_walks_every_hook_event():
    settings = {"hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": LOCAL_ONLY}]}],
        "SessionStart": [{"hooks": [{"type": "command", "command": TWO_TIER}]}],
    }}
    _, changed = a.anchor(settings)
    assert sorted(set(changed)) == ["SessionStart", "Stop"]
    for groups in settings["hooks"].values():
        for g in groups:
            for h in g["hooks"]:
                assert doccheck._bare_hook_paths(h["command"]) == []


def test_no_change_returns_empty():
    already = a.anchor_command(LOCAL_ONLY)
    _, changed = a.anchor({"hooks": {"Stop": [{"hooks": [{"command": already}]}]}})
    assert changed == []
