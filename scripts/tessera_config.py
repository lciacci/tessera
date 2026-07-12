"""tessera_config — read `.tessera/config.yml`.

The profile model's config layer, built 2026-07-11 with exactly one live consumer
(`bin/tessera-test`) and no speculative knobs. The template that preceded it had six knobs —
`bcrypt_rounds`, `tls_minimum`, `coverage_threshold`, mnemos bands, gate threshold — and
**every one was dead**: commented out, read by nothing, designed top-down from the design
doc rather than from observed pain. It also lacked the one key that maps to a real failure.

The real failure, observed this session: `python3 -m pytest` on this machine resolves to
Homebrew 3.14, which has no pytest; the suite only runs under 3.13. A human guesses wrong
once and recovers. **An unsupervised agent (ADR-0005) does not get to recover by hand** — it
needs to be told the command, not to infer it. That is what this file exists for, and it is
the whole justification. Do not add a key here until something reads it.

NO PYYAML. PyYAML is installed for 3.13 and absent from the default `python3` (3.14) on this
machine — the same dual-Homebrew split that silently killed the Mnemos hooks (F-001). A
config reader that dies on the default interpreter is worse than no config reader. The
schema is deliberately FLAT so a 15-line parser suffices with zero dependencies.
"""
from pathlib import Path

CONFIG_PATH = ".tessera/config.yml"


def load(root: Path) -> dict[str, str]:
    """Parse the flat `key: value` config. Missing file → {} (config is always optional)."""
    path = Path(root) / CONFIG_PATH
    if not path.exists():
        return {}
    config = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        if value:
            config[key.strip()] = value
    return config


def get(root: Path, key: str) -> str | None:
    """One config value, or None. Callers decide whether absence is fatal."""
    return load(root).get(key)
