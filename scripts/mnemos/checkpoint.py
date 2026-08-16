"""Checkpoint write/load for Mnemos session persistence."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from .models import CheckpointNode, _now, _uuid
from .signals import read_recent_signals
from .store import MnemosStore, post_constraint_content

# Goals are never-evict (models.py) AND one is auto-minted per ingested session
# (store.extract_session_goals), so the list only grows: 98 nodes / 10.9KB by
# 2026-07-26 — 60% of the checkpoint, and what truncated the Layer-2 SessionStart
# delivery. The restore blob had outgrown its own delivery channel.
MAX_CHECKPOINT_GOALS = 8

# `bridge-icpg` runs backgrounded on EVERY SessionStart and imports active iCPG
# ReasonNodes as GoalNodes with origin='loaded' and the sentinel task 'icpg-bridge'.
# They are historical intents, never "what this session is doing".
BRIDGE_ORIGIN = 'loaded'


def _select_goals(goals: list, task_id: str | None) -> tuple[list, int, int]:
    """Goals for the render: this task's first, then recency, bridge imports never.

    Returns (shown, bridged_excluded, older_omitted).

    FOUND 2026-07-27, by reading what a live compaction actually delivered. Sorting
    by `created_at` alone is a proxy for relevance, and it held only while nothing
    wrote goals in bulk. A re-bootstrap regenerates every ReasonNode id, so the
    bridge's content-keyed dedup missed all 43, minted them at import time, and
    **44 goals sharing one timestamp took all 8 slots** — the checkpoint's stated
    goal became "Phase 3: scaffold .tessera/", from the project's opening days.

    Constraints stayed correct through the same import (3 new vs 53) because their
    dedup key is the invariant text, which survives a rebuild. Same bridge, two
    keys, one of them coupled to a regenerated id. That is the actual bug, and the
    ordering here is the guard against its next variant.

    Excluded, not evicted: nodes stay in the store (ADR-0007) and the count is
    STATED, so an exclusion cannot read as an empty backlog.
    """
    bridged = sum(1 for n in goals if n.origin == BRIDGE_ORIGIN)
    live = [n for n in goals if n.origin != BRIDGE_ORIGIN]
    live.sort(key=lambda n: n.created_at or '', reverse=True)
    if task_id:
        # Stable, so recency still orders within each group.
        live.sort(key=lambda n: n.task_id != task_id)
    shown = live[:MAX_CHECKPOINT_GOALS]
    return shown, bridged, len(live) - len(shown)


# SECOND DEFINITION, DELIBERATE AND GUARDED. `bin/tessera-watch` holds the other
# (RESTORE_BUDGET_BYTES) and derives it — see its comment for the derivation, which two
# wrong re-anchors preceded. bin/ is stdlib-only by doccheck `bin-scripts-are-stdlib-only`
# and cannot import mnemos, so the copy is unavoidable; doccheck
# `checkpoint-budget-matches-p3` asserts the two literals agree, because a budget that
# drifts between the writer and the watcher is worse than either number alone.
CHECKPOINT_BUDGET_BYTES = 8_000


def _warn_if_over_budget(size: int) -> None:
    """Say so AT WRITE TIME when the payload will not fit its delivery channel.

    P3 can only ever report a spill that already happened: `tessera-watch` runs at
    SessionStart, so its warning arrives in the same breath as the truncated checkpoint
    it is warning about — and worse, the checkpoint is rewritten mid-session, so a
    payload that goes over at 13:15 is not evaluated by anything until the next session
    starts. This one runs at the moment the artifact is produced, which is the only
    position from which the news can arrive early. Same meter-before-marker rule the
    caching work landed on.

    stderr, not stdout: the caller is a Stop hook whose stdout is a delivery channel of
    its own. Warn only — a checkpoint that is too big must still be WRITTEN, because a
    spilled checkpoint beats no checkpoint, and a size guard that can refuse to save
    state is a worse failure than the one it guards.
    """
    if size <= CHECKPOINT_BUDGET_BYTES:
        return
    print(
        f'mnemos: checkpoint payload is {size:,}b, over the '
        f'{CHECKPOINT_BUDGET_BYTES:,}b delivery budget — SessionStart will hand the '
        f'model a truncated preview. Written anyway. Largest fields shrink via '
        f'`mnemos nodes --type constraint` / `--type goal`.',
        file=sys.stderr)


# WIDENED 2026-08-10, and the ORDERING was the point. This named one family while the
# class had two: `test_exists("path")` leaked through a filter written for
# `file_exists("path")` — standing pattern #11, inside the filter itself.
#
# The deferral said widening had to wait because the justification for dropping these
# ("asserted by something stronger") was true of `file_exists` and NOT of `test_exists`.
# Widening first would have silently dropped a class nothing else asserted. doccheck's
# `icpg-test-exists-paths-are-real` now makes that claim structural rather than a
# coincidence of which files happen to be cited in two documents — so the justification
# is true today, and only now.
STATIC_PREDICATE = re.compile(r"\b(?:file_exists|test_exists)\(")


def _fulfilled_post_contents(icpg_store) -> set[str]:
    """ConstraintNode contents whose iCPG intent is FULFILLED. Empty if iCPG is absent.

    An intent that is still `executing`, `proposed` or `drifted` keeps its postconditions:
    `drifted` in particular means a predicate is FAILING, which is the one state where a
    POST most needs to be in front of the agent. Only `fulfilled` is history.

    The subtraction is not decoration. Two intents can carry the same postcondition text
    under the same 40-char goal prefix, and the bridge dedups them to ONE node — so if
    either owner is still open, the node is still live and must not be dropped on the
    other's account. Fail-safe in the other direction too: a constraint whose intent was
    deleted from iCPG matches nothing and is KEPT.
    """
    fulfilled: set[str] = set()
    live: set[str] = set()
    for reason in icpg_store.list_reasons():
        if reason.status in ('rejected', 'abandoned'):
            continue
        bucket = fulfilled if reason.status == 'fulfilled' else live
        for post in reason.postconditions:
            bucket.add(post_constraint_content(reason.goal, post))
    return fulfilled - live


def _scope_relevant(node, recent_paths: set) -> bool:
    """Does this constraint's iCPG scope touch anything the session is working on?

    Unscoped constraints are ALWAYS relevant: with no scope there is nothing to compare
    against, and guessing would drop a standing property on no evidence. Same rule when
    `recent_paths` is empty — a session with no file signals yet gets everything, because
    "I don't know what you're touching" is not evidence that nothing matters.

    (An earlier version justified the unscoped rule by saying the per-file channel "is
    keyed on scope". It is not — it is keyed on recorded symbol edges. The rule is right;
    the reason given for it was the same wrong belief retracted in `_select_constraints`,
    and it is corrected here rather than left as a second copy of it.)

    Prefix matching deliberately over-matches (`scripts/restore` also hits
    `scripts/restore_x.py`). Every ambiguity here should err toward KEEPING a constraint
    visible; the cost of a false keep is bytes, the cost of a false drop is a missed
    invariant.
    """
    tags = getattr(node, 'scope_tags', None) or []
    if not tags or not recent_paths:
        return True
    return any(path == tag or path.startswith(tag)
               for tag in tags for path in recent_paths)


def _select_constraints(nodes: list, historical: set[str] = frozenset(),
                        recent_paths: set = frozenset()) -> tuple:
    """Constraints for the render, minus static repo facts, fulfilled postconditions, and
    invariants scoped away from what this session is touching.

    Returns (shown, {'static': n, 'historical': n, 'offscope': n}).

    **THE INVARIANT HALF, added 2026-08-10.** Dropping fulfilled POSTs took the payload
    12,909b → 7,780b, and bridging one new intent put it back to 8,556b inside the same
    session: invariants are ~139b each, at least one per intent, and nothing bounds them.
    They are also the constraints that MUST NOT be cut by recency — 23 distinct bodies out
    of 24, every one a standing property, so a cap would pick winners by age on the
    payload's most valuable field.

    Scope is the discriminator. **THE ORIGINAL JUSTIFICATION FOR THIS CUT WAS FALSE AND IS
    RETRACTED HERE.** It read: "there is a better-targeted channel for the ones dropped —
    `mnemos-pre-edit.sh` runs `icpg query constraints <file>` on every Edit/Write, so a
    scoped invariant is delivered exactly when its files come into play. Verified, not
    assumed." The verification behind that sentence was one CLI call on one file that
    returned *an* intent's invariants — true, and it did not establish what it was used
    for. **Measured properly 2026-08-10: 2 of 18 dropped invariants are reachable that
    way.** `get_reasons_for_file` resolves by recorded `CREATES`/`MODIFIES` symbol edges,
    NOT by `reason.scope`, and in this repo the two sets barely overlap — symbol recording
    needs exactly one executing intent at Stop time, so most intents never got symbols in
    most of their scoped files.

    So what this cut currently buys is SIZE, and the note in the payload now says exactly
    that instead of promising a fallback that mostly is not there.

    **DECIDED 2026-08-10: keep it as a size-only cut. Treat the omitted set as genuinely
    omitted.** The obvious repair — union scope-matching into `get_reasons_for_file` —
    was scoped, measured, and declined, and the measurement is why:

      | files reachable | today (symbol edges) | with a scope union |
      |---|---:|---:|
      | any linkage     |  94 | 719 |
      | via exact-file scope entries | | 51 |
      | via DIRECTORY expansion only | | 668 |

    668 of 719 come from directory-prefix scope entries — bare `scripts/` alone is on 4
    intents. A scope union does not deliver "the invariants for this file"; for most files
    it delivers every invariant of every intent that touched the tree, taking a typical
    file from 0-2 predicates to a median of 15 (max 29). That is the pre-edit channel
    getting louder in the least useful way.

    Three further reasons, none of which were visible before reading the governing records:
    the `executing`-only refinement floated to control that noise is an INVENTED THRESHOLD
    with no evidence and no way to measure it today (0 intents are executing); the pairing
    check meant to justify the union reads `reason.scope` on BOTH sides, so it is a mirror,
    not an instrument (ADR-0017's own method finding); and the real question underneath —
    whether the SYMBOL is the right unit of linkage at all — is already open, with
    evidence, at `docs/observatory.md` -> "Is the SYMBOL the right unit for a shell-heavy
    repo?". Deciding it inside a checkpoint-budget item would be the fourth re-scope that
    entry's stopping rule exists to prevent.

    That entry also carries the structural half: **77 of 83 shell files have ZERO symbols in
    the graph** (measured 2026-08-10; the entry's older 46-of-78 figure is stale), so for
    those files the symbol channel returns nothing. Do NOT read that as purely a corpus
    property — 85 shell symbols are *extractable* across 40 files while the graph holds 6,
    so the dominant cause is recording, not authorship. The extractor was tested and is
    healthy. Which means there are two candidate remedies, not one, and this docstring is
    not the place that picks between them.

    (One correction to the note above, kept because the blast-radius claim was load-bearing
    in declining the union: `get_reasons_for_file` has two *Python* callers, but THREE
    shell call sites — `mnemos-pre-edit.sh` runs both `query context` and
    `query constraints`, and `icpg-inject-context.sh` runs `query context` too.)

    Applies to `INV:` only: an open intent's POST is what the session is working toward,
    and narrowing that would weaken the guarantee built one commit earlier.

    **The POST half, added 2026-08-10 (P3 part 3).** `bridge-icpg` mints a ConstraintNode
    per postcondition and nothing removes it at fulfilment, so the checkpoint listed 39
    postconditions — 5,238b, 39.6% of a 12,909b payload against an 8,000b budget — under a
    heading that reads *"Active Constraints (DO NOT VIOLATE)"*, while all 30 intents in
    this repo were `fulfilled` and ZERO were executing.

    The split is semantic, not size-driven, and it is the schema's own
    (`.claude/skills/icpg/SKILL.md`): a postcondition is *"what must be true when
    fulfilled"* — once its intent closes it describes a change already made — whereas an
    invariant is *"what must remain true throughout AND AFTER"*, so invariants survive
    their intent and are untouched here. `docs/contracts/` carries no iCPG contract, so
    this encodes a reading of the skill's schema rather than contradicting a written one.

    What is NOT claimed: that a fulfilled postcondition is dead. `icpg drift check` skips
    only `rejected`/`abandoned` (`drift.py:92`), so these predicates are still evaluated
    by the decision-drift dimension. This is exclusion from ONE render — the session-scoped
    "do not violate" list — not retirement. The note says so in the payload itself.

    ---

    `file_exists("path")` invariants are bridged in bulk from iCPG and they DOMINATE the
    payload: measured across 7 checkpoints on 2026-08-07 they were 53/53, 53/53, 56/56,
    53/53, 61/77 and 62/80 — four of the seven were 100% — and the constraint field was
    5.3-8.7KB of a checkpoint whose whole delivery channel caps at 10,000 characters. So
    the never-evict guarantee was spending the budget on assertions that a repo path
    exists, and Constraints/Progress/Files were the fields that never arrived.

    Dropping them loses nothing the agent needs: every one is a static fact about the
    repo, `doccheck`'s `referenced-paths-exist` asserts that class, and a pre-commit hook
    blocks on it — a guarantee strictly stronger than a line in a payload that spilled.
    They also stay in the store and in iCPG; this is exclusion from one render.

    **The count is STATED, never silently dropped** — same rule as `_select_goals`, and
    for the same reason: this repo's signature failure is that an empty field reads as
    "nothing to report" (F-001). A checkpoint whose constraints quietly vanished would be
    indistinguishable from a project with no invariants.
    """
    # `historical` is tested FIRST, and the order is a fix, not a preference. With the
    # static test first, a fulfilled postcondition whose predicate text happens to contain
    # `file_exists(` was counted under the OTHER notice and announced as an *invariant* —
    # refuted by `bin/tessera-verify` 2026-08-10, which is also where the ordering question
    # got waved through as "preserves existing behaviour" while writing this. The total
    # omitted count was right and the attribution was wrong, in the one sentence whose
    # entire job is telling the reader what went missing (#12).
    shown: list[str] = []
    dropped = {'static': 0, 'historical': 0, 'offscope': 0}
    for node in nodes:
        content = node.content or ''
        if content in historical:
            dropped['historical'] += 1
        elif STATIC_PREDICATE.search(content):
            dropped['static'] += 1
        elif content.startswith('INV:') and not _scope_relevant(node, recent_paths):
            dropped['offscope'] += 1
        else:
            shown.append(content)
    return shown, dropped


def _render_goals(shown: list) -> str:
    """One goal per line, so distinct goals cannot read as one sentence.

    PRESENTATION ONLY — selection is untouched. `_select_goals` decides WHICH goals appear
    and in what order (the live session's first; see test_checkpoint_goal_cap); this decides
    only how they are drawn.

    Why it needed changing (2026-08-15). The field was `'; '.join(...)` under a heading that
    reads "Goal", singular. A real checkpoint rendered seven goals from seven different past
    sessions as one semicolon-joined run-on, and the boundaries between them were close to
    invisible — which is what made a mid-word truncation so costly, because

        ...from the checkpoin; Read the top section of...

    reads as one malformed sentence rather than as two goals with the first one cut. The
    truncation is fixed at the ingest layer; this stops the RENDERING from hiding the next
    one. Two independent defects had to line up to produce that string, and removing either
    is enough.

    NOT decided here, deliberately: whether historical goals belong in a checkpoint at all.
    That is the selection question, it is the same budget adjudicated 2026-08-10, and it is
    parked with Lorenzo's stated position recorded in docs/observatory.md.

    The single-goal case — the common one downstream — renders as plain text with no list
    decoration, because a bullet on a list of one is noise.
    """
    if not shown:
        return 'No active goal'
    # `or 'No active goal'` is NOT redundant. The old `'; '.join(...) or ...` covered a lone
    # goal with empty content; returning shown[0].content bare reintroduced an empty string,
    # which _format_checkpoint renders as a '### Goal' heading with nothing under it and
    # mnemos-pre-compact.sh's `if goal:` drops entirely. An empty field reads as "nothing to
    # report" rather than "the record is broken" — F-001's shape.
    if len(shown) == 1:
        return shown[0].content or 'No active goal'
    earlier = '\n'.join(f'  - {n.content}' for n in shown[1:])
    # The header states ONLY what _select_goals guarantees: recency order, bridge imports
    # excluded. An earlier draft called the lead line "this session's task", which the
    # default call path does not provide — write_checkpoint's task_id defaults to None, and
    # with no task_id _select_goals skips the live-session sort and shown[0] is merely the
    # newest goal (test_without_a_task_id_selection_degrades_to_recency codifies exactly
    # that). The incident that prompted this whole fix is the proof: shown[0] was
    # "what's next", which was nobody's task. Nor is "one per prior session" true — nothing
    # dedupes by task_id, and `mnemos add goal --task-id` can mint several for one session.
    return (f'{shown[0].content or "(empty goal)"}\n'
            f'[earlier goals, most recent first — NOT necessarily this session\'s task]\n'
            f'{earlier}')


def write_checkpoint(
    store: MnemosStore,
    fatigue_score: float = 0.0,
    icpg_store=None,
    task_id: str | None = None
) -> CheckpointNode:
    """Write a CheckpointNode capturing current MnemoGraph state.

    Always includes: GoalNode content, all ConstraintNodes, current sub-goal.
    Optionally includes: iCPG state, git state, compressed ResultNodes.

    Writes to:
        .mnemos/checkpoint-latest.json  (always overwritten)
        .mnemos/checkpoints/<id>.json   (archived copy)

    Returns the created CheckpointNode.
    """
    all_goals = store.get_by_type('goal')
    shown, bridged, omitted = _select_goals(all_goals, task_id)
    if not task_id and shown:
        task_id = shown[0].task_id
    task_id = task_id or 'unknown'

    goal_text = _render_goals(shown)
    notes = []
    if omitted:
        notes.append(f'+{omitted} older goal(s) omitted')
    if bridged:
        notes.append(f'{bridged} bridged iCPG intent(s) excluded')
    if notes:
        goal_text += (f'\n[{"; ".join(notes)} from this checkpoint; '
                      '`mnemos nodes --type goal` lists all]')

    # Gather constraints (never evicted). Fulfilled-intent postconditions need iCPG to
    # identify; with no iCPG store every POST is kept, which is the fail-safe direction.
    # GUARDED, and the asymmetry is why. `_get_icpg_state` below already wraps its iCPG
    # read in `except Exception`; this one did not, so ANY iCPG failure — corrupt db,
    # schema drift, a NULL column that makes icpg's own `json.loads` raise — aborted the
    # whole checkpoint write. That is the exact opposite of this filter's stated fail-safe
    # ("cannot determine status → keep everything"): it turned a degraded filter into no
    # checkpoint at all. Losing the POST filter costs bytes; losing the checkpoint costs
    # the session. (arbiter 2026-08-10 — its specific NULL mechanism is unreachable, since
    # icpg raises in its own reader first, but the missing guard was real.)
    historical = set()
    if icpg_store and icpg_store.exists():
        try:
            historical = _fulfilled_post_contents(icpg_store)
        except Exception:
            historical = set()
    # Task narrative and recent files from signals. Computed HERE, above the constraint
    # selection, because scope-relevance needs to know what the session is touching.
    narrative, recent_files = build_task_narrative(store.project_dir)
    root = str(Path(store.project_dir).resolve())
    recent_paths = {
        f['path'][len(root):].lstrip('/') if f['path'].startswith(root) else f['path']
        for f in recent_files if f.get('path')
    }

    constraint_nodes = store.get_by_type('constraint')
    constraints, dropped = _select_constraints(
        constraint_nodes, historical, recent_paths)
    if dropped['static']:
        constraints.append(
            # "constraint(s)", not "invariant(s)": a POST from a still-open intent can
            # carry a file_exists predicate too, and this notice covers it. Calling that
            # an invariant is the same mislabel the reordering above fixes.
            # Names BOTH predicates, because the filter now covers both. A notice that
            # under-states what it dropped is #12 in the one sentence whose entire job is
            # saying what went missing — the same mislabel this notice was already fixed
            # for once (invariant→constraint, 2026-08-10).
            f'[{dropped["static"]} static constraint(s) omitted from this checkpoint '
            '(file_exists / test_exists) — repo facts asserted by doccheck '
            '`referenced-paths-exist` and `icpg-test-exists-paths-are-real` + pre-commit; '
            '`mnemos nodes --type constraint` lists all]')
    if dropped['historical']:
        constraints.append(
            f'[{dropped["historical"]} postcondition(s) omitted from this checkpoint — '
            'their iCPG intents are FULFILLED, so they describe changes already made, '
            'not standing constraints. Still stored, and still evaluated by iCPG\'s '
            'decision-drift dimension; `icpg query constraints <file>` and '
            '`mnemos nodes --type constraint` list all]')
    if dropped['offscope']:
        constraints.append(
            f'[{dropped["offscope"]} standing invariant(s) omitted from this checkpoint — '
            'their iCPG scope does not touch any file this session has read or edited. '
            'DO NOT ASSUME THE PRE-EDIT HOOK WILL SURFACE THEM: it resolves by recorded '
            'CREATES/MODIFIES symbol edges, NOT by iCPG scope, and only 2 of 18 were '
            'reachable that way when measured 2026-08-10. Run '
            '`mnemos nodes --type constraint` to see all of them if you are working '
            'outside this session\'s files]')

    # Gather result summaries (compressed or active)
    result_nodes = store.get_by_type('result')
    results = []
    for rn in result_nodes[:20]:  # Cap at 20 most recent
        if rn.summary:
            results.append(rn.summary)
        elif rn.content:
            results.append(rn.content[:200])

    # Current sub-goal from working nodes
    working_nodes = store.get_by_type('working')
    current_subgoal = working_nodes[0].content if working_nodes else ''

    # Working memory
    working_memory = '\n'.join(
        n.content for n in working_nodes[:3]
    )

    # (narrative/recent_files computed above — constraint scope-relevance needs them)

    # Git state
    git_state = _get_git_state(store.project_dir)

    # iCPG state
    icpg_state = None
    if icpg_store and icpg_store.exists():
        icpg_state = _get_icpg_state(icpg_store)

    # Node summary (counts by type and status)
    stats = store.get_stats()
    node_summary = {
        'total': stats['total_nodes'],
        'active': stats['active'],
        'compressed': stats['compressed'],
        'by_type': stats['by_type']
    }

    cp = CheckpointNode(
        id=_uuid(),
        task_id=task_id,
        goal=goal_text,
        active_constraints=constraints,
        active_results=results,
        decisions=_session_decisions(store.project_dir, task_id),
        current_subgoal=current_subgoal,
        working_memory=working_memory,
        task_narrative=narrative,
        recent_files=recent_files,
        fatigue_at_checkpoint=fatigue_score,
        git_state=git_state,
        icpg_state=icpg_state,
        node_summary=node_summary,
        created_at=_now()
    )

    # Persist to DB
    store.save_checkpoint(cp)

    # Write to JSON files
    cp_data = _checkpoint_to_dict(cp)
    _warn_if_over_budget(len(json.dumps(cp_data, indent=2)))

    # Latest checkpoint (overwrite)
    latest_path = store.mnemos_dir / 'checkpoint-latest.json'
    latest_path.write_text(json.dumps(cp_data, indent=2))

    # Archived copy
    archive_dir = store.mnemos_dir / 'checkpoints'
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / f'{cp.id}.json'
    archive_path.write_text(json.dumps(cp_data, indent=2))

    return cp


def load_checkpoint(
    project_dir: str = '.', path: str | None = None
) -> str | None:
    """Load latest checkpoint and format as context for session injection.

    Returns formatted markdown string, or None if no checkpoint exists.
    """
    if path:
        cp_path = Path(path)
    else:
        cp_path = Path(project_dir).resolve() / '.mnemos' / 'checkpoint-latest.json'

    if not cp_path.exists():
        return None

    try:
        data = json.loads(cp_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    return _format_checkpoint(data)


def _format_checkpoint(data: dict) -> str:
    """Format checkpoint data as structured markdown for context injection."""
    lines = []
    lines.append('## Mnemos Session Resume')
    lines.append(f'Checkpoint: {data.get("id", "unknown")[:8]}')
    lines.append(f'Created: {data.get("created_at", "unknown")}')
    lines.append(f'Fatigue at checkpoint: {data.get("fatigue_at_checkpoint", 0):.2f}')
    lines.append('')

    # Goal
    lines.append('### Goal')
    lines.append(data.get('goal', 'No goal recorded'))
    lines.append('')

    # Constraints
    constraints = data.get('active_constraints', [])
    if constraints:
        lines.append('### Active Constraints (DO NOT VIOLATE)')
        for c in constraints:
            lines.append(f'- {c}')
        lines.append('')

    # What was being worked on (task narrative)
    narrative = data.get('task_narrative', '')
    if narrative:
        lines.append('### What You Were Working On')
        lines.append(narrative)
        lines.append('')

    # Current task
    subgoal = data.get('current_subgoal', '')
    if subgoal:
        lines.append('### Current Sub-Goal')
        lines.append(subgoal)
        lines.append('')

    # Working memory
    working = data.get('working_memory', '')
    if working:
        lines.append('### Working Memory')
        lines.append(working)
        lines.append('')

    # Decisions surfaced this session. Placed ABOVE Progress deliberately: progress is
    # what was done, decisions are what is OPEN, and a reader who gets only the first
    # screen needs the second. This is the field five restore receipts named.
    decisions = data.get('decisions', [])
    if decisions:
        lines.append('### Decisions Surfaced (gates — what was proposed, and what is open)')
        for d in decisions:
            lines.append(f'- {d}')
        lines.append('')

    # Progress (result summaries)
    results = data.get('active_results', [])
    if results:
        lines.append('### Progress So Far')
        for r in results:
            lines.append(f'- {r}')
        lines.append('')

    # Recent files
    recent = data.get('recent_files', [])
    if recent:
        lines.append('### Key Files (from recent activity)')
        for f in recent[:10]:
            parts = []
            if f.get('edits', 0) > 0:
                parts.append(f'edited {f["edits"]}x')
            if f.get('reads', 0) > 0:
                parts.append(f'read {f["reads"]}x')
            detail = ', '.join(parts) if parts else 'touched'
            lines.append(f'- {f.get("path", "?")} ({detail})')
        lines.append('')

    # Git state
    git = data.get('git_state', {})
    if git.get('branch'):
        lines.append('### Git State')
        lines.append(f'Branch: {git["branch"]}')
        if git.get('uncommitted'):
            lines.append('Uncommitted files:')
            for f in git['uncommitted'][:10]:
                lines.append(f'  - {f}')
        lines.append('')

    # iCPG state
    icpg = data.get('icpg_state')
    if icpg:
        lines.append('### iCPG Context')
        if icpg.get('active_reason'):
            lines.append(f'Active intent: {icpg["active_reason"]}')
        if icpg.get('unresolved_drift'):
            lines.append(f'Unresolved drift: {icpg["unresolved_drift"]}')
        if icpg.get('stats'):
            s = icpg['stats']
            lines.append(
                f'Graph: {s.get("reasons", 0)} intents, '
                f'{s.get("symbols", 0)} symbols'
            )
        lines.append('')

    # Node summary
    summary = data.get('node_summary', {})
    if summary:
        lines.append('### MnemoGraph Summary')
        lines.append(
            f'Nodes: {summary.get("active", 0)} active, '
            f'{summary.get("compressed", 0)} compressed, '
            f'{summary.get("total", 0)} total'
        )
        by_type = summary.get('by_type', {})
        if by_type:
            parts = [f'{t}:{c}' for t, c in by_type.items()]
            lines.append(f'Types: {", ".join(parts)}')

    return '\n'.join(lines)


def _get_git_state(project_dir: Path) -> dict:
    """Get current git branch and uncommitted files."""
    state = {}
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_dir)
        )
        if result.returncode == 0:
            state['branch'] = result.stdout.strip()

        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_dir)
        )
        if result.returncode == 0:
            files = [
                f.strip() for f in result.stdout.strip().split('\n')
                if f.strip()
            ]
            state['uncommitted'] = files

        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_dir)
        )
        if result.returncode == 0:
            staged = [
                f.strip() for f in result.stdout.strip().split('\n')
                if f.strip()
            ]
            if staged:
                state['staged'] = staged

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return state


def _get_icpg_state(icpg_store) -> dict:
    """Extract summary iCPG state for checkpoint."""
    state = {}
    try:
        stats = icpg_store.get_stats()
        state['stats'] = stats

        # Find most recent executing reason
        executing = icpg_store.list_reasons(status='executing')
        if executing:
            r = executing[-1]
            state['active_reason'] = f'{r.id[:8]} -- {r.goal}'

        # Unresolved drift count
        drift = icpg_store.get_unresolved_drift()
        state['unresolved_drift'] = len(drift)
    except Exception:
        pass
    return state


def build_task_narrative(project_dir: str | Path) -> tuple[str, list[dict]]:
    """Build a human-readable task narrative from recent signals.

    Reads signals.jsonl and produces:
    1. A narrative string describing recent activity
    2. A list of recent files with read/edit counts

    Returns:
        (narrative_text, recent_files_list)
    """
    signals = read_recent_signals(str(project_dir), limit=50)
    if not signals:
        return ('', [])

    # Count file interactions
    file_edits: Counter = Counter()
    file_reads: Counter = Counter()
    tool_counts: Counter = Counter()
    error_count = 0
    total_outcomes = 0

    for s in signals:
        tool = s.get('tool', '')
        fp = s.get('file_path', '')
        tool_counts[tool] += 1

        if fp:
            if tool in ('Edit', 'Write'):
                file_edits[fp] += 1
            elif tool == 'Read':
                file_reads[fp] += 1

        if 'success' in s:
            total_outcomes += 1
            if not s['success']:
                error_count += 1

    # Build narrative
    parts = []

    # Most-edited files
    top_edits = file_edits.most_common(5)
    if top_edits:
        edit_parts = []
        for fp, count in top_edits:
            name = Path(fp).name
            edit_parts.append(f'{name} ({count}x)')
        parts.append(f'Editing: {", ".join(edit_parts)}')

    # Most-read files
    top_reads = file_reads.most_common(5)
    if top_reads:
        read_parts = []
        for fp, count in top_reads:
            name = Path(fp).name
            read_parts.append(f'{name} ({count}x)')
        parts.append(f'Reading: {", ".join(read_parts)}')

    # Tool activity
    other_tools = {t: c for t, c in tool_counts.items()
                   if t not in ('Edit', 'Write', 'Read')}
    if other_tools:
        tool_parts = [f'{t}:{c}' for t, c in
                      sorted(other_tools.items(), key=lambda x: -x[1])]
        parts.append(f'Other tools: {", ".join(tool_parts[:5])}')

    # Focus area (most common directory)
    all_files = list(file_edits.keys()) + list(file_reads.keys())
    if all_files:
        dir_counts: Counter = Counter()
        for fp in all_files:
            parent = str(Path(fp).parent)
            # Shorten to relative if possible
            try:
                parent = str(Path(parent).relative_to(Path.cwd()))
            except ValueError:
                pass
            dir_counts[parent] += 1
        top_dir = dir_counts.most_common(1)[0]
        parts.append(f'Focus area: {top_dir[0]}/')

    # Errors
    if error_count > 0:
        parts.append(f'Errors: {error_count}/{total_outcomes} tool calls failed')

    narrative = '. '.join(parts) + '.' if parts else ''

    # Build recent files list
    all_touched = set(file_edits.keys()) | set(file_reads.keys())
    recent_files = []
    for fp in all_touched:
        entry = {'path': fp}
        if file_edits[fp]:
            entry['edits'] = file_edits[fp]
        if file_reads[fp]:
            entry['reads'] = file_reads[fp]
        recent_files.append(entry)
    # Sort by total activity
    recent_files.sort(
        key=lambda x: x.get('edits', 0) + x.get('reads', 0),
        reverse=True
    )

    return (narrative, recent_files[:15])


def format_for_post_compact_injection(
    project_dir: str = '.',
    checkpoint_path: str | None = None
) -> str | None:
    """Format checkpoint as a rich injection block for post-compaction context.

    Called by mnemos-post-compact-inject.sh after compaction is detected.
    Returns a structured block that Claude can parse and resume from.
    """
    if checkpoint_path:
        cp_path = Path(checkpoint_path)
    else:
        cp_path = Path(project_dir).resolve() / '.mnemos' / 'checkpoint-latest.json'

    if not cp_path.exists():
        return None

    try:
        data = json.loads(cp_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    lines = []
    lines.append('=== MNEMOS: CONTEXT RESTORED AFTER COMPACTION ===')
    lines.append('')
    lines.append('Compaction just occurred. Your previous context was summarized.')
    lines.append('Resume from this checkpoint -- DO NOT re-derive information already captured below.')
    lines.append('')

    # Goal
    lines.append('## Goal')
    lines.append(data.get('goal', 'No goal recorded'))
    lines.append('')

    # Constraints
    constraints = data.get('active_constraints', [])
    if constraints:
        lines.append('## Active Constraints (DO NOT VIOLATE)')
        for c in constraints:
            lines.append(f'- {c}')
        lines.append('')

    # Task narrative
    narrative = data.get('task_narrative', '')
    if narrative:
        lines.append('## What You Were Working On')
        lines.append(narrative)
        lines.append('')

    # Current sub-goal
    subgoal = data.get('current_subgoal', '')
    if subgoal:
        lines.append('## Current Sub-Goal')
        lines.append(subgoal)
        lines.append('')

    # Working memory
    working = data.get('working_memory', '')
    if working:
        lines.append('## Working Memory')
        lines.append(working)
        lines.append('')

    # Progress
    results = data.get('active_results', [])
    if results:
        lines.append('## Progress So Far')
        for r in results:
            lines.append(f'- {r}')
        lines.append('')

    # Recent files
    recent = data.get('recent_files', [])
    if recent:
        lines.append('## Key Files (from recent activity)')
        for f in recent[:10]:
            parts = []
            if f.get('edits', 0) > 0:
                parts.append(f'edited {f["edits"]}x')
            if f.get('reads', 0) > 0:
                parts.append(f'read {f["reads"]}x')
            detail = ', '.join(parts) if parts else 'touched'
            lines.append(f'- {f.get("path", "?")} ({detail})')
        lines.append('')

    # Git state
    git = data.get('git_state', {})
    if git.get('branch'):
        lines.append('## Git State')
        lines.append(f'Branch: {git["branch"]}')
        if git.get('uncommitted'):
            lines.append('Uncommitted:')
            for gf in git['uncommitted'][:10]:
                lines.append(f'  - {gf}')
        else:
            lines.append('Working tree clean.')
        lines.append('')

    # iCPG
    icpg = data.get('icpg_state')
    if icpg:
        lines.append('## iCPG Context')
        if icpg.get('active_reason'):
            lines.append(f'Active intent: {icpg["active_reason"]}')
        if icpg.get('unresolved_drift'):
            lines.append(f'Unresolved drift: {icpg["unresolved_drift"]}')
        lines.append('')

    # Checkpoint metadata
    lines.append(f'Checkpoint: {data.get("id", "?")[:8]} at {data.get("created_at", "?")}')
    lines.append(f'Fatigue at checkpoint: {data.get("fatigue_at_checkpoint", 0):.2f}')
    lines.append('')
    lines.append('=== Resume work from this checkpoint. Ask the user to confirm the task if unclear. ===')

    return '\n'.join(lines)


def write_compaction_marker(project_dir: str = '.') -> None:
    """Write the just-compacted marker file for post-compaction detection."""
    marker = Path(project_dir).resolve() / '.mnemos' / 'just-compacted'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        'timestamp': time.time(),
        'reason': 'pre_compact_hook'
    }))


def check_compaction_marker(project_dir: str = '.') -> bool:
    """Check if a fresh compaction marker exists (< 5 minutes old)."""
    marker = Path(project_dir).resolve() / '.mnemos' / 'just-compacted'
    if not marker.exists():
        return False
    try:
        data = json.loads(marker.read_text())
        age = time.time() - data.get('timestamp', 0)
        return age < 300  # 5 minutes
    except (json.JSONDecodeError, OSError):
        return False


def consume_compaction_marker(project_dir: str = '.') -> bool:
    """Atomically consume the compaction marker (rename then delete).

    Returns True if marker was consumed, False if already consumed or missing.
    """
    marker = Path(project_dir).resolve() / '.mnemos' / 'just-compacted'
    consumed = marker.with_suffix('.consumed')
    try:
        marker.rename(consumed)
        consumed.unlink(missing_ok=True)
        return True
    except (OSError, FileNotFoundError):
        return False


# A gate note is prose the model wrote; the whole value is reading it, so truncating
# hard defeats the point. Capped anyway because the payload has a measured ceiling —
# and the cap is per-note plus a count, never a silent drop of the tail.
DECISION_NOTE_CHARS = 220
DECISION_CAP = 8


def _session_decisions(project_dir, task_id: str) -> list[str]:
    """This session's surfaced gates, newest last, as `kind — note` lines.

    THE FIELD FIVE RESTORE RECEIPTS ASKED FOR. `decisions` did not exist in the schema,
    so no amount of byte-budget work could ever deliver it — T2 read `insufficient` five
    times and twice named this field by name.

    Sourced from `.tessera/logs/<session>.jsonl`, the suggestion-gate channel, which is
    already produced by `scripts/gate/emit.py` and already backstopped by a Stop hook.
    That matters more than the rendering: this reads an EXISTING channel rather than
    asking the model to remember a new one, which is principle #17 and the reason the
    gate log itself exists.

    Never raises. A checkpoint that dies because an audit log is unreadable is a worse
    failure than one missing a field — the same rule the constraint filter above follows.
    """
    if not task_id or task_id == 'unknown':
        return []
    log = Path(project_dir) / '.tessera' / 'logs' / f'{Path(task_id).name}.jsonl'
    try:
        raw = log.read_text(encoding='utf-8', errors='replace')
    except (OSError, ValueError):
        return []
    out: list[str] = []
    for line in raw.splitlines():
        if '"suggestion_gate"' not in line:
            continue
        try:
            data = json.loads(line).get('data', {})
        except ValueError:
            continue
        if not data.get('fired'):
            continue  # a HELD gate was considered and not surfaced — not a decision
        note = (data.get('note') or '').strip()
        if not note:
            continue
        kind = data.get('suggestion_kind') or 'gate'
        out.append(f'{kind}: {note[:DECISION_NOTE_CHARS]}')
    if len(out) > DECISION_CAP:
        # Oldest first, so the tail kept is the LIVE end of the session. The count is
        # stated — a silently shortened list reads as "that is all there was".
        dropped = len(out) - DECISION_CAP
        out = out[-DECISION_CAP:]
        out.insert(0, f'[{dropped} earlier gate(s) omitted — '
                      f'`python3 scripts/gate/emit.py` log has all]')
    return out


def _checkpoint_to_dict(cp: CheckpointNode) -> dict:
    """Serialize CheckpointNode to JSON-safe dict."""
    return {
        'id': cp.id,
        'task_id': cp.task_id,
        'goal': cp.goal,
        'active_constraints': cp.active_constraints,
        'active_results': cp.active_results,
        'decisions': cp.decisions,
        'current_subgoal': cp.current_subgoal,
        'working_memory': cp.working_memory,
        'task_narrative': cp.task_narrative,
        'recent_files': cp.recent_files,
        'fatigue_at_checkpoint': cp.fatigue_at_checkpoint,
        'git_state': cp.git_state,
        'icpg_state': cp.icpg_state,
        'node_summary': cp.node_summary,
        'created_at': cp.created_at
    }
