# templates/tessera — downstream scaffold

Stand up a new Tessera-managed project:

```
bin/tessera-new-project <target-dir> [project-name] [profile]
```

It lays down the harness layer — `.claude/` (mnemos hooks copied from this checkout's live
source + stack-agnostic `settings.json`), `scripts/gate/` (suggestion-gate recorder), `.tessera/`
(profile + logs), `CLAUDE.md` (from `CLAUDE.md.template`), `.gitignore`, and `git init`. It does
**not** scaffold an app/stack — generate that with the platform's own tool (Android Studio,
create-vite, …) and layer the harness on top.

Files here:

- `CLAUDE.md.template` — downstream CLAUDE.md; `{{PROJECT_NAME}}`/`{{PROFILE}}` auto-filled,
  `{{PROJECT_DESCRIPTION}}`/`{{COMMANDS}}` filled by hand.
- `settings.base.json` — stack-agnostic hooks + permissions; add your stack's build/test allows.
- `gitignore.base` — stack-agnostic ignores; add your stack's artifacts.
- `*.template` — `.tessera/` config (`project.yml`, `config.yml`, `security-exceptions.yml`).

First built distilling the hand-scaffold of Howler (dogfood #1) — see its `docs/SCAFFOLD-NOTES.md`.
