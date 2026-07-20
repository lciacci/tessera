#!/usr/bin/env python3
"""should_fire passive extraction — auto-label suggestion_gate events.

`should_fire` (the gate-calibration ground truth: did the gate fire when it
should have?) is `null` at emit time and, left to manual labeling, stays null
forever — the P7 backlog proved hand-labeling-as-a-separate-act is dead. This
fills it passively, the same shape spec-13 used for corrections: read the user's
DISPOSITION (the first human turn after the gate) and let a local-qwen classifier
judge whether pausing was warranted.

Provenance is load-bearing (docs/contracts/gate-event.md): `labeled_by='classifier'`
keeps these ~0.5-precision auto-labels SEPARABLE from trusted hand-labels, and a
classifier verdict NEVER overwrites a human one. Fail-open to null, wall-clock
budget — mirrors scripts/mnemos/correction_detect. Stdlib only (gate/ isolation);
the Ollama call is a lazy import so the gate test process never touches it.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOGS = Path(".tessera/logs")

# Ground truth = "did a real decision get made?", never the labeler's opinion of the
# gate (the 2026-07-12 lesson). CALIBRATED against 26 human-labeled gates: the first
# rubric ("go ahead / obviously = no") scored recall 0.08 — it read terse option-picks
# ("1a 2a", "go with 2", "commit") as dismissals, when SELECTING a surfaced option IS
# the decision the gate existed for. So engagement — including a terse pick — is yes;
# only an explicit "you didn't need to ask" is no.
_PROMPT = """A coding assistant paused to surface a decision to the user before acting (a "gate"). From the user's REPLY, decide whether pausing was warranted — was a real decision genuinely at stake?
Answer "yes" if the user ENGAGED with the decision: chose among options, picked a path, approved a specific proposal, deliberated, or corrected course. Selecting an option counts as yes even when terse — "go with 2", "1a 2b", "commit", "yes create it", "start spec 12" are all a choice being made.
Answer "no" ONLY if the reply shows the pause was unnecessary: the user dismissed it as obvious or told the assistant not to ask ("why are you asking", "you didn't need to check that", "just do it without asking").
What the assistant asked: {note}
The user's reply: {reply}
Answer only yes or no.
Answer:"""

_MODEL = os.environ.get("MNEMOS_CORRECTION_MODEL", "qwen3:8b")
_THINK = False if "qwen3" in _MODEL else None


def _parse_ts(s: str | None) -> datetime | None:
    """ISO-8601 → aware datetime. Normalises trailing Z so it parses on 3.7+."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def classify_should_fire(note: str | None, reply: str, *, generate) -> bool | None:
    """qwen verdict: did the gate deserve to fire? True/False, or None on
    unreachable/junk (caller leaves should_fire null — fail-open)."""
    raw = generate(_PROMPT.format(note=note or "(no note)", reply=reply[:1500]),
                   model=_MODEL, num_predict=8, timeout=10.0, think=_THINK)
    if not raw:
        return None
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    m = re.search(r"\b(yes|no)\b", raw, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower() == "yes"


def human_turns(transcript_path: str) -> list[tuple[datetime, str]]:
    """[(ts, text)] for real user messages, oldest first. Excludes tool_result
    carriers (content not str), hook feedback (isMeta), and harness-injected
    turns (promptSource=system)."""
    out: list[tuple[datetime, str]] = []
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") != "user" or ev.get("isSidechain"):
                    continue
                if ev.get("isMeta") or ev.get("promptSource") == "system":
                    continue
                content = (ev.get("message") or {}).get("content")
                ts = _parse_ts(ev.get("timestamp"))
                if isinstance(content, str) and ts:
                    out.append((ts, content))
    except OSError:
        return []
    out.sort(key=lambda t: t[0])
    return out


def find_disposition(turns: list[tuple[datetime, str]], gate_ts: datetime) -> str | None:
    """The user's reply to a gate: the first human turn strictly after it."""
    for ts, text in turns:
        if ts > gate_ts:
            return text
    return None


def _already_labeled(data: dict) -> bool:
    """A human label (should_fire set) or a prior classifier pass. Either way,
    never re-touch — a classifier verdict must not overwrite a human one."""
    return data.get("should_fire") is not None or bool(data.get("labeled_by"))


def _joinable(data: dict) -> bool:
    """Retro-logged gates (scan adjudication) carry an emit-time ts, not the
    gate moment — the disposition join is invalid for them, permanently. The
    2026-07-20 backfill mislabeled these wholesale; skip, never guess."""
    return not data.get("retro")


def _label_one(ev: dict, turns: list[tuple[datetime, str]], *, generate) -> bool:
    data = ev.get("data") or {}
    if _already_labeled(data) or not _joinable(data):
        return False
    gate_ts = _parse_ts(ev.get("ts"))
    reply = find_disposition(turns, gate_ts) if gate_ts else None
    if not reply:
        return False
    verdict = classify_should_fire(data.get("note"), reply, generate=generate)
    if verdict is None:
        return False
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    data.update({"should_fire": verdict, "should_fire_basis": reply[:200],
                 "labeled_by": "classifier", "labeled_ts": now_iso})
    ev["data"] = data
    return True


def label_gate_log(path: Path, turns: list[tuple[datetime, str]], *, generate,
                   budget_s: float = 120.0) -> int:
    """Fill should_fire on every null gate event in one log, in place and
    idempotent. Non-gate lines pass through untouched. Returns count labeled."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return 0
    deadline = time.monotonic() + budget_s
    out: list[str] = []
    n = 0
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if ev.get("type") == "suggestion_gate" and time.monotonic() <= deadline:
            if _label_one(ev, turns, generate=generate):
                n += 1
                out.append(json.dumps(ev, ensure_ascii=False))
                continue
        out.append(line if ev.get("type") != "suggestion_gate"
                   else json.dumps(ev, ensure_ascii=False))
    if n:
        path.write_text("\n".join(out) + "\n")
    return n


def _find_transcript(session_id: str, projects_root: str | None = None) -> str | None:
    root = projects_root or str(Path.home() / ".claude" / "projects")
    hits = glob.glob(str(Path(root) / "*" / f"{session_id}.jsonl"))
    return hits[0] if hits else None


def label_session(session_id: str, *, generate, projects_root: str | None = None) -> dict:
    log = LOGS / f"{session_id}.jsonl"
    if not log.exists():
        return {"session": session_id, "labeled": 0, "skipped": "no-log"}
    tpath = _find_transcript(session_id, projects_root)
    if not tpath:
        return {"session": session_id, "labeled": 0, "skipped": "no-transcript"}
    n = label_gate_log(log, human_turns(tpath), generate=generate)
    return {"session": session_id, "labeled": n}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Passively label suggestion_gate should_fire.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--session", help="one session id")
    g.add_argument("--all", action="store_true", help="every gate log under .tessera/logs")
    p.add_argument("--projects-root", help="override ~/.claude/projects")
    args = p.parse_args(argv)

    from scripts.model_routing import _ollama_up, ollama_generate
    if not _ollama_up():
        print("Ollama down — should_fire stays null (fail-open).", file=sys.stderr)
        return 0
    sessions = [args.session] if args.session else sorted(f.stem for f in LOGS.glob("*.jsonl"))
    total = 0
    for s in sessions:
        r = label_session(s, generate=ollama_generate, projects_root=args.projects_root)
        total += r["labeled"]
        if r["labeled"] or "skipped" not in r:
            print(r)
    print(f"labeled {total} gate(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
