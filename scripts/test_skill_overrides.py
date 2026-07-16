"""Tests for skill_overrides — the profile → skillOverrides curation (ADR-0009).

The contract that matters: everything INSTALLED but OUTSIDE the resolved profile is turned
"off", and the resolution is universal ∪ profile ∪ added − removed. A bug here silently
either leaks the wrong stack's skills into a project or turns off ones it needs.
"""
import json
from pathlib import Path

import skill_overrides as so

MAP = {
    "universal": ["base", "mnemos", "security"],
    "profiles": {"standard": [], "web": ["react-web"]},
    "extensions": {
        "react-web": ["react-web", "ui-web"],
        "python": ["python"],
    },
}


def test_parse_project_yml_scalar_and_lists():
    text = "profile: web\nextensions_added: [python, ui-testing]\nextensions_removed: []\n"
    assert so.parse_project_yml(text) == ("web", ["python", "ui-testing"], [])


def test_parse_defaults_when_fields_absent():
    assert so.parse_project_yml("hook_distro: global\n") == ("standard", [], [])


def test_parse_strips_quotes_and_inline_comments():
    # A quoted scalar and a commented list must not leak quotes/comment text (fail-loud review).
    text = 'profile: "web"  # chosen\nextensions_added: [python]  # just python\n'
    assert so.parse_project_yml(text) == ("web", ["python"], [])


def test_parse_warns_on_block_style_instead_of_silently_dropping(capsys):
    # Block-style YAML lists are not parsed — but must WARN, never silently → [].
    so.parse_project_yml("extensions_added:\n  - python\n  - supabase\n")
    assert "inline" in capsys.readouterr().err.lower()


def test_resolve_universal_only_for_standard():
    assert so.resolve_selected(MAP, ("standard", [], [])) == {"base", "mnemos", "security"}


def test_resolve_expands_profile_and_added_tags():
    selected = so.resolve_selected(MAP, ("web", ["python"], []))
    assert selected == {"base", "mnemos", "security", "react-web", "ui-web", "python"}


def test_removed_subtracts_expanded_tag():
    selected = so.resolve_selected(MAP, ("web", [], ["react-web"]))
    assert "react-web" not in selected and "ui-web" not in selected
    assert "base" in selected


def test_removed_cannot_turn_off_a_universal_skill():
    # extensions_removed naming a core skill must NOT disable it — universal is inviolable.
    assert "base" in so.resolve_selected(MAP, ("standard", [], ["base"]))


def test_unknown_tag_is_treated_as_bare_skill():
    # extensions_added naming a skill with no tag entry still selects that skill.
    assert "flutter" in so.resolve_selected(MAP, ("standard", ["flutter"], []))


def test_compute_overrides_turns_off_only_unselected_installed():
    selected = {"base", "python"}
    installed = {"base", "python", "flutter", "ai-models"}
    assert so.compute_overrides(selected, installed) == {"ai-models": "off", "flutter": "off"}


def test_selected_but_not_installed_is_not_listed():
    # A profile can name a skill that isn't installed; it simply isn't in the off map.
    assert so.compute_overrides({"base"}, {"flutter"}) == {"flutter": "off"}


def test_installed_skills_reads_dirs_with_skill_md(tmp_path):
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "SKILL.md").write_text("x")
    (tmp_path / "not-a-skill").mkdir()  # no SKILL.md
    assert so.installed_skills(tmp_path) == {"python"}


def test_inject_preserves_other_settings_keys(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash"]}}))
    so.inject(settings, {"flutter": "off"})
    data = json.loads(settings.read_text())
    assert data["permissions"] == {"allow": ["Bash"]}
    assert data["skillOverrides"] == {"flutter": "off"}
