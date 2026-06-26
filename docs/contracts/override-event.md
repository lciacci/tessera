# Contract: override event

**Status:** Canonical. Owned by Tessera (the producer). Defined here; consumers conform.

A concrete instance of the generic Tessera hook-event shape (design-principles.md:
structured event log, `type` / `source` / structured `data`, one JSON object per line in
`.tessera/logs/<session-id>.jsonl`). Sibling to [gate-event.md](gate-event.md).

Emitted when a developer states a rule exception **honestly in code** via a
`tessera:*` annotation, instead of hiding it in a PR thread (design-principles §552–554,
"the exceptions get made anyway"). The override mechanism is **audit-only**: it records
that an exception was taken and why; it does not itself bypass any gate (the native skip —
`pytest.mark.skip`, `eslint-disable`, etc. — does the skipping). Making the exception
*stated and logged* is the whole feature.

```jsonc
{
  "type": "override",               // discriminator; consumers filter on this
  "ts": "2026-06-26T18:25:00Z",     // ISO 8601
  "session_id": "uuid",
  "source": "override-scanner",     // the emitter
  "data": {
    "rule": "tdd",                  // one of: tdd | quality-gates | security
    "annotation_kind": "skip-reason", // skip-reason | ignore-line
    "file": "src/auth/login.py",    // path, repo-relative
    "line": 42,                     // 1-based line of the annotation
    "reason": "dependency injection scaffolding" // free text from the annotation; "" for ignore-line
  }
}
```

## Annotation forms recognized

| In code | rule | annotation_kind | reason |
|---|---|---|---|
| `# tessera:tdd-skip-reason="..."` | `tdd` | `skip-reason` | quoted text |
| `// tessera:quality-gates-ignore-line` | `quality-gates` | `ignore-line` | `""` |
| `// tessera:security-skip-reason="..."` | `security` | `skip-reason` | quoted text |

Comment leader (`#`, `//`, `--`, …) is ignored — only the `tessera:<rule>-<kind>` token matters.

## Producers

- **`override-scanner`** (`scripts/override/scan.py`) — scans changed files for the
  annotations above and emits one event per occurrence. Non-blocking: a scan failure never
  fails the host hook.

## Consumers

- **`scripts/override/report.py`** — `--since <window>` filters `type:"override"` across
  session logs and tabulates them (the "periodic review" of design-principles §554). The
  `tess overrides report` front-end named in the design is deferred; this script is the
  current entry point.
