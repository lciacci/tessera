"""skill_overrides — compute a project's `skillOverrides` from its Tessera profile.

Claude Code unions ALL global `~/.claude/skills` into every project (ADR-0009), so a
downstream cannot restrict skills by *placement* — only by *settings*. This computes the
`skillOverrides` block that turns "off" every installed skill OUTSIDE the project's
profile, and injects it into the project's `.claude/settings.json`.

Composable model (matches the existing `.tessera/project.yml` fields):
    selected = universal  ∪  profile-bundle  ∪  extensions_added  −  extensions_removed
An "extension" is a named skill-group (stack tag) defined in `skill-profiles.json`;
an unknown tag is treated as a bare skill name. Everything installed but unselected → "off".
The `universal` set is inviolable — `extensions_removed` cannot turn off a core skill.
A skill turned "off" is hidden from Claude, the / menu, and SDK callers — its *listing*
name still costs budget (only uninstalling removes that; ADR-0009's deferred "Goal B").

STDLIB ONLY (json, sys, pathlib, argparse) — no PyYAML, per the F-001 interpreter split.
The project.yml scalar/list fields are read by a small parser, INLINE style (`[a, b]`) only;
block-style YAML (`- a`) is not parsed and is warned about, never silently dropped.
"""
import argparse
import json
import sys
from pathlib import Path


def load_profile_map(path):
    """Load the profile → skill mapping (universal set, profiles, extensions)."""
    return json.loads(Path(path).read_text())


def _clean(val):
    """Strip an inline `# comment`, surrounding quotes, and whitespace from a scalar."""
    return val.split("#", 1)[0].strip().strip('"').strip("'").strip()


def _inline_list(val):
    """Parse `[a, b, c]` (or `[]`) → ['a','b','c'], tolerating a trailing comment/quotes."""
    inner = val.split("#", 1)[0].strip().strip("[]").strip()
    return [_clean(x) for x in inner.split(",") if x.strip()]


def parse_project_yml(text):
    """Extract (profile, extensions_added, extensions_removed) — inline lists only, no YAML lib."""
    profile = "standard"
    fields = {"extensions_added": [], "extensions_removed": []}
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("profile:"):
            profile = _clean(s.split(":", 1)[1])
        elif any(s.startswith(k + ":") for k in fields):
            key, _, val = s.partition(":")
            v = _clean(val)
            if val.split("#", 1)[0].strip().startswith("["):
                fields[key.strip()] = _inline_list(val)
            elif v:
                print(f"warn: {key.strip()} must be inline [a, b], got {v!r} — ignored", file=sys.stderr)
    if not any(fields.values()) and any(l.lstrip().startswith("- ") for l in text.splitlines()):
        print("warn: found '- ' items but no inline [..] extensions — use inline style", file=sys.stderr)
    return profile, fields["extensions_added"], fields["extensions_removed"]


def _expand(tags, extensions):
    """Expand stack tags to their skills; an unknown tag is a bare skill name."""
    skills = set()
    for tag in tags:
        skills.update(extensions.get(tag, [tag]))
    return skills


def resolve_selected(pmap, parsed):
    """The set of skill names this project keeps ON. `universal` is inviolable."""
    profile, added, removed = parsed
    ext = pmap.get("extensions", {})
    universal = set(pmap.get("universal", []))
    selected = universal | _expand(pmap.get("profiles", {}).get(profile, []), ext) | _expand(added, ext)
    return selected - (_expand(removed, ext) - universal)


def compute_overrides(selected, installed):
    """Every installed skill NOT selected → "off" (pure; the testable core)."""
    return {name: "off" for name in sorted(installed) if name not in selected}


def installed_skills(skills_dir):
    """Names of skills actually installed (a dir with a SKILL.md; follows symlinks)."""
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
    parsed = parse_project_yml(Path(a.project_yml).read_text())
    selected = resolve_selected(pmap, parsed)
    installed = installed_skills(a.skills_dir)
    missing = sorted(s for s in selected if s not in installed)
    if missing:
        print(f"warn: {len(missing)} selected skill(s) not installed (typo or cross-machine?): "
              f"{', '.join(missing)}", file=sys.stderr)
    inject(a.settings, compute_overrides(selected, installed))
    print(f"skillOverrides: {len(installed - selected)} off, "
          f"{len(selected & installed)} on (profile: {parsed[0]})")


if __name__ == "__main__":
    main()
