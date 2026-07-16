"""skill_overrides — compute a project's `skillOverrides` from its Tessera profile.

Claude Code unions ALL global `~/.claude/skills` into every project (ADR-0009), so a
downstream cannot restrict skills by *placement* — only by *settings*. This computes the
`skillOverrides` block that turns "off" every installed skill OUTSIDE the project's
profile, and injects it into the project's `.claude/settings.json`.

Composable model (matches the existing `.tessera/project.yml` fields):
    selected = universal  ∪  profile-bundle  ∪  extensions_added  −  extensions_removed
An "extension" is a named skill-group (stack tag) defined in `skill-profiles.json`;
an unknown tag is treated as a bare skill name. Everything installed but unselected → "off".
A skill turned "off" is hidden from Claude, the / menu, and SDK callers — its *listing*
name still costs budget (only uninstalling removes that; see ADR-0009's deferred "Goal B").

STDLIB ONLY (json, pathlib, argparse) — no PyYAML, per the F-001 interpreter split: this
runs under whatever bare `python3` the scaffold invokes. The project.yml list fields are
read by a 3-line parser, not a YAML lib.
"""
import argparse
import json
from pathlib import Path


def load_profile_map(path):
    """Load the profile → skill mapping (universal set, profiles, extensions)."""
    return json.loads(Path(path).read_text())


def _inline_list(line):
    """Parse `key: [a, b, c]` (or `[]`) → ['a','b','c']."""
    inner = line.split(":", 1)[1].strip().strip("[]").strip()
    return [x.strip() for x in inner.split(",") if x.strip()] if inner else []


def parse_project_yml(text):
    """Extract (profile, extensions_added, extensions_removed) — no YAML lib."""
    profile, added, removed = "standard", [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("profile:"):
            profile = s.split(":", 1)[1].strip()
        elif s.startswith("extensions_added:"):
            added = _inline_list(s)
        elif s.startswith("extensions_removed:"):
            removed = _inline_list(s)
    return profile, added, removed


def _expand(tags, extensions):
    """Expand stack tags to their skills; an unknown tag is a bare skill name."""
    skills = set()
    for tag in tags:
        skills.update(extensions.get(tag, [tag]))
    return skills


def resolve_selected(pmap, profile, added, removed):
    """The set of skill names this project keeps ON."""
    ext = pmap.get("extensions", {})
    selected = set(pmap.get("universal", []))
    selected |= _expand(pmap.get("profiles", {}).get(profile, []), ext)
    selected |= _expand(added, ext)
    return selected - _expand(removed, ext)


def compute_overrides(selected, installed):
    """Every installed skill NOT selected → "off" (pure; the testable core)."""
    return {name: "off" for name in sorted(installed) if name not in selected}


def installed_skills(skills_dir):
    """Names of skills actually installed (a dir with a SKILL.md)."""
    d = Path(skills_dir)
    return {p.name for p in d.iterdir() if (p / "SKILL.md").exists()} if d.exists() else set()


def inject(settings_path, overrides):
    """Merge skillOverrides into the target settings.json (preserving other keys)."""
    p = Path(settings_path)
    data = json.loads(p.read_text()) if p.exists() else {}
    data["skillOverrides"] = overrides
    p.write_text(json.dumps(data, indent=2) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a project's skillOverrides from its profile.")
    ap.add_argument("--project-yml", required=True)
    ap.add_argument("--settings", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--skills-dir", default=str(Path.home() / ".claude" / "skills"))
    a = ap.parse_args(argv)
    pmap = load_profile_map(a.map)
    profile, added, removed = parse_project_yml(Path(a.project_yml).read_text())
    selected = resolve_selected(pmap, profile, added, removed)
    installed = installed_skills(a.skills_dir)
    inject(a.settings, compute_overrides(selected, installed))
    print(f"skillOverrides: {len(installed - selected)} off, "
          f"{len(selected & installed)} on (profile: {profile})")


if __name__ == "__main__":
    main()
