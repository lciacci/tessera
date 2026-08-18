#!/usr/bin/env python3
"""`degraded_ack` — "I have seen these degraded events and the condition is resolved."

    python3 scripts/degraded_ack.py --component standing-patterns --reason block-missing \\
        --note "block was re-anchored in active.md the same day; re-planted and verified"

── WHY THIS EXISTS WHEN THE CONTRACT SAID IT WOULD NOT ────────────────────────────────

`docs/contracts/degraded-event.md` argued that P13 "needs no disposition verb to stay
honest", because it is WINDOWED: an event ages out after 7 days, so nothing can
accumulate the way iCPG's drift backlog reached 700 undisposed rows. That reasoning is
correct and is not overturned here. What the window cannot do is distinguish

    "the guard is missing now"          <- the alarm
    "the guard was missing on Sunday,   <- true, spent, and still firing until Sunday+7
     I fixed it on Sunday"

ADR-0025 measured the cost: 14 of 16 degraded events ever written are one detector, a
fixed condition can only be waited out or snoozed, and G-a fires on the streak with no
right answer available. **A channel that trains its reader to ignore it cannot carry an
autonomy precondition.**

── WHY A WATERMARK AND NOT A SNOOZE ───────────────────────────────────────────────────

A snooze suppresses the PREDICATE, so it blinds P13 to *new* events — which is worse
than the noise it removes, and is the specific objection ADR-0025 raises.

An ack is a **timestamp per `(component, reason)`**. It acknowledges events recorded
BEFORE it and has no effect on events recorded after. That is the same rule the spend
contract already applies to grants and dismissals ("honoured when recorded after the last
denial — a dismissal logged earlier says nothing about a later denial"), and it is chosen
because it makes the dangerous case structurally impossible: an ack cannot hide a failure
that has not happened yet. Nothing accumulates either — acks are watermarks, not an open
set — so the iCPG backlog failure mode cannot recur through this verb.

── WHY THE MODEL MAY EMIT IT ──────────────────────────────────────────────────────────

ADR-0016's axis is *what does the detector's over-firing mean*. Here it means neither
"over-counted by design" (the gate precedent) nor "the detector was wrong" (the drift
precedent): the event was **real and is now resolved**. The party that resolved it is the
session that did the fixing, and requiring a human keystroke to clear noise a human did
not create is the friction ADR-0025 objects to.

The safety argument that makes this admissible is the watermark, not trust: this verb
authorizes nothing, expires nothing, and cannot suppress a future event. `--note` is
required for the same reason `restore/emit.py` requires evidence — a bare verdict is the
failure mode, and the cheapest path must not be the empty one.

**It does not delete anything.** The degraded events stay in the log verbatim, and P13
reports the acknowledged count alongside the live one, so a reader can always see that
suppression happened and by whose reasoning. A narrowing that appears only in the source
is standing pattern #12.

Stdlib-only (CLAUDE.md's interpreter split): runs under bare `python3`, possibly 3.9.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MIN_NOTE = 25  # chars; a speed bump against reflexive acking, not a wall


def root() -> Path:
    """The repo this script belongs to. TESSERA_ROOT overrides (tests, other checkouts).

    Inlined rather than imported from `scripts/restore/paths.py` for the reason that file
    states about itself: those directories run in separate pytest processes because of
    colliding module names, and a cross-directory import resolves differently under the
    suite than under a bare invocation. Four lines is the cheaper liability.
    """
    override = os.environ.get("TESSERA_ROOT")
    return Path(override) if override else Path(__file__).resolve().parents[1]


def logs_dir() -> Path:
    return root() / ".tessera" / "logs"


def log_path(session_id: str) -> Path:
    return logs_dir() / f"{session_id}.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_ack(component: str, reason: str, note: str, *,
              session_id: str, ts: str | None = None) -> dict:
    """The contract-shaped event. `ts` IS the watermark — see the module docstring."""
    return {
        "type": "degraded_ack",
        "ts": ts or _utc_now_iso(),
        "session_id": session_id,
        "source": "model",
        "data": {"component": component, "reason": reason, "note": note},
    }


def known_pairs(directory: Path | None = None) -> set:
    """Every `(component, reason)` that has EVER written a degraded event.

    Deliberately NOT windowed, and deliberately not sharing P13's filter. Its only job is
    to catch a typo'd `--component`/`--reason`, which would otherwise write a watermark
    that silently pre-acknowledges nothing today and cannot be told apart from a real one
    later. Keeping the predicate weaker than P13's means the two cannot disagree about
    windowing — there is no shared comparison to drift.
    """
    directory = directory or logs_dir()
    pairs = set()
    if not directory.is_dir():
        return pairs
    for log in directory.glob("*.jsonl"):
        if log.name == "watch.jsonl":
            continue
        try:
            lines = log.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") != "degraded":
                continue
            data = event.get("data") or {}
            pairs.add((data.get("component"), data.get("reason")))
    return pairs


def validate(args, pairs: set) -> str | None:
    """Returns an error string, or None."""
    note = (args.note or "").strip()
    if len(note) < MIN_NOTE:
        return (f"--note must say what was resolved (>= {MIN_NOTE} chars). An ack with no "
                f"reasoning is the failure mode this verb exists to avoid.")
    if (args.component, args.reason) not in pairs:
        seen = ", ".join(sorted(f"{c}/{r}" for c, r in pairs)) or "none on record"
        return (f"no degraded event has ever been written for "
                f"{args.component}/{args.reason} — refusing to watermark nothing. "
                f"Known pairs: {seen}")
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Acknowledge resolved degraded events so P13 stops reporting them.")
    p.add_argument("--component", required=True, help="the component that was degraded")
    p.add_argument("--reason", required=True, help="the kebab-case reason it reported")
    p.add_argument("--note", help="what was resolved, and how you know")
    p.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    args = p.parse_args(argv)

    err = validate(args, known_pairs())
    if err:
        print(f"degraded_ack: {err}", file=sys.stderr)
        return 2
    if not args.session:
        print("degraded_ack: no CLAUDE_CODE_SESSION_ID and no --session", file=sys.stderr)
        return 2

    event = build_ack(args.component, args.reason, args.note.strip(), session_id=args.session)
    path = log_path(args.session)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(event) + "\n")
    print(f"degraded ack appended → {path}\n"
          f"  {args.component}/{args.reason} acknowledged through {event['ts']}\n"
          f"  events recorded AFTER this stamp will still fire P13.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
