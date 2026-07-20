"""Correction-of-agent detection for Mnemos haziness.

Two detectors on the same passive pipe (`claude_log`):

- `regex_match` — the original keyword heuristic (front-loaded objection). High
  precision, low recall. It is the single home for that logic now; `claude_log`
  and `haziness` call here.
- `CorrectionDetector` — a local-qwen classifier that catches the redirections
  the regex misses (probing questions, reframes, "but that would require X").
  Recall-first, fails open to the regex, local-only (turns never leave the box).

Only user turns that FOLLOW an agent action are eligible: a standalone opening
question cannot correct an action that has not happened. The classifier is only
spent on eligible turns the regex already missed — so it adds zero cost to the
common (already-detected) case and stays quiet on non-correction sessions.
"""

from __future__ import annotations

import os
import re
import time

_LEAD_RE = re.compile(
    r"^\s*(no|wait|stop|actually|undo|revert|rollback|wrong|don'?t)\b",
    re.IGNORECASE,
)
# Mid-turn markers, checked ONLY in the first chars: real corrections front-load
# the objection; content references ("the Don't Hardcode section", "do X instead
# of Y" as a fresh instruction) sit mid-sentence and must not match. 'don't'
# lives in _LEAD only — too common as plain content to match anywhere. (Guarded
# by test_correction.py's finding-#1 cases.)
_PHRASE_RE = re.compile(r"\b(not that|instead)\b", re.IGNORECASE)
_PHRASE_WINDOW = 60


def regex_match(cleaned: str) -> int:
    """Original front-loaded-objection heuristic. 1 if it looks like a
    correction, else 0. Only meaningful for user turns < 500 chars."""
    if not cleaned or len(cleaned) >= 500:
        return 0
    if _LEAD_RE.match(cleaned) or _PHRASE_RE.search(cleaned[:_PHRASE_WINDOW]):
        return 1
    return 0


# A recall-leaning rubric. Calibrated on a 27-turn hand-labeled backtest
# (b6d7b6f5): this wording + qwen3:8b lands prec/rec ~0.5 and a density that
# matches the human count — the 3B tier-classify model FAILS here (it parrots
# whichever polarity the prompt ends on, giving constant-yes or constant-no).
_PROMPT = """Did this USER message push back on, redirect, correct, reject, question, or express doubt about what the assistant just did or proposed? A correction includes probing questions that imply the approach was off ("but wouldn't that break X?", "there were 70, no?", "why did you...?", "is that all up to date?").
It does NOT include: plain approvals ("yes", "go", "please"), or a fresh instruction/new task with no reference to prior work.
Answer only yes or no.
Message: {text}
Answer:"""

# qwen3:8b, not the 3B tier-classify model — this judgment needs the bigger
# model. Override with MNEMOS_CORRECTION_MODEL. A qwen3 model must run with
# think disabled or it burns the token budget on a hidden reasoning block.
_MODEL = os.environ.get("MNEMOS_CORRECTION_MODEL", "qwen3:8b")
_THINK = False if "qwen3" in _MODEL else None


def classify(cleaned: str, *, generate) -> bool | None:
    """Ask qwen whether `cleaned` is a correction. True/False, or None if the
    model was unreachable / returned junk (caller falls back to the regex)."""
    raw = generate(_PROMPT.format(text=cleaned[:1500]), model=_MODEL,
                   num_predict=8, timeout=10.0, think=_THINK)
    if not raw:
        return None
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    m = re.search(r"\b(yes|no)\b", raw, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower() == "yes"


# Phase 2 — typing. The four disposition types of a correction (spec 13). A
# view/diagnostic dimension: it does NOT feed the haziness composite. Single
# dominant label; recall-first (Phase 1) already decided the turn IS a
# correction, so this only sorts it.
TYPES = ("misunderstood", "defied", "overreached", "wrong")

_TYPE_PROMPT = """The user's message corrected or pushed back on what the assistant just did. Classify the ONE closest reason:
- misunderstood: the assistant misread the request and did the wrong thing.
- defied: the assistant ignored an instruction or did the opposite of what was asked.
- overreached: the assistant did more than asked — extra scope, unrequested changes.
- wrong: what the assistant did was factually or technically incorrect / broken.
Answer with only one word: misunderstood, defied, overreached, or wrong.
Message: {text}
Answer:"""


def classify_type(cleaned: str, *, generate) -> str | None:
    """Pick which of TYPES a (known) correction is. One of TYPES, or None if the
    model was unreachable / returned a word not in TYPES."""
    raw = generate(_TYPE_PROMPT.format(text=cleaned[:1500]), model=_MODEL,
                   num_predict=8, timeout=10.0, think=_THINK)
    if not raw:
        return None
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).lower()
    for t in TYPES:
        if t in raw:
            return t
    return None


class CorrectionDetector:
    """Per-ingest classifier with a wall-clock budget. When the budget is spent
    (or the classifier is disabled / Ollama is down) it stops calling qwen and
    the regex result stands — never worse than today."""

    # Disable only after this many CONSECUTIVE nulls — one junk/unparseable
    # answer or a single blip must not silently drop a whole --reclassify --all
    # run to regex-only; a genuinely-down Ollama still trips it within seconds.
    _MAX_CONSECUTIVE_FAILS = 3

    def __init__(self, *, generate, enabled: bool, budget_s: float = 180.0,
                 reason: str = ""):
        self.generate = generate
        self.enabled = enabled
        self.reason = reason  # why disabled, "" when enabled
        self._deadline = time.monotonic() + budget_s if enabled else 0.0
        self._fails = 0

    def status(self) -> str:
        """One-line trace of how detection actually ran — persisted per ingest
        (spec 16: a fail-open path must leave a trace, or a dead pipe reads as
        a clean one for weeks)."""
        if not self.enabled:
            if self._fails >= self._MAX_CONSECUTIVE_FAILS:
                return "disabled-mid:consecutive-nulls"
            return f"regex-only:{self.reason or 'disabled'}"
        if time.monotonic() > self._deadline:
            return "budget-exhausted"
        return "ran"

    def qwen_says_correction(self, cleaned: str) -> bool:
        """True only on a confident yes within budget. Any failure → False, so
        the caller's regex verdict is preserved (fail-open)."""
        if not self.enabled or time.monotonic() > self._deadline:
            return False
        verdict = classify(cleaned, generate=self.generate)
        if verdict is None:  # unreachable or junk; tolerate a few, then give up
            self._fails += 1
            if self._fails >= self._MAX_CONSECUTIVE_FAILS:
                self.enabled = False
            return False
        self._fails = 0
        return verdict

    def correction_type(self, cleaned: str) -> str | None:
        """Type a turn already known to be a correction. One of TYPES, or None
        (Ollama down / over budget / unparseable) — a null type never drops the
        correction, it just leaves it untyped. Shares the same budget AND the
        consecutive-fail disable as qwen_says_correction: an all-regex-matched
        run (which never calls qwen_says_correction) still trips off a dead
        Ollama within _MAX_CONSECUTIVE_FAILS instead of eating the whole budget
        in per-call timeouts."""
        if not self.enabled or time.monotonic() > self._deadline:
            return None
        verdict = classify_type(cleaned, generate=self.generate)
        if verdict is None:
            self._fails += 1
            if self._fails >= self._MAX_CONSECUTIVE_FAILS:
                self.enabled = False
            return None
        self._fails = 0
        return verdict


def _import_routing():
    """scripts.model_routing lives at the REPO root, not inside the mnemos
    package — under the .venv console script the root is not on sys.path, so a
    bare `from scripts...` raised ModuleNotFoundError and (07-17→07-20)
    silently killed every Stop-hook ingest before its first fail-open guard,
    while `python -m` runs from the repo root kept working. F-001's cousin:
    resolve the root from this file (the editable install keeps that true)."""
    import sys
    from pathlib import Path
    try:
        from scripts.model_routing import _ollama_up, ollama_generate
    except ModuleNotFoundError:
        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        from scripts.model_routing import _ollama_up, ollama_generate
    return _ollama_up, ollama_generate


def make_detector(*, force: bool = False) -> CorrectionDetector:
    """Build a detector. Enabled when Ollama is up, unless
    MNEMOS_CORRECTION_CLASSIFIER=0 disables it. `force` overrides both (used by
    --reclassify, where the whole point is to run the classifier). NEVER raises:
    an unreachable toolchain degrades to regex-only WITH a reason — ingest must
    survive any environment the hook runs it in."""
    try:
        _ollama_up, ollama_generate = _import_routing()
    except Exception:
        return CorrectionDetector(generate=None, enabled=False,
                                  reason="import-error")
    if not force and os.environ.get("MNEMOS_CORRECTION_CLASSIFIER") == "0":
        return CorrectionDetector(generate=ollama_generate, enabled=False,
                                  reason="env-disabled")
    enabled = force or _ollama_up()
    return CorrectionDetector(generate=ollama_generate, enabled=enabled,
                              reason="" if enabled else "ollama-down")
