# ADR-0024: DeepSeek Harness — rejected on layer for the third time, and the mirror is that our own decision surface silently drops its newest records

- **Date:** 2026-08-17
- **Status:** Watching
- **Executed:** partially — 2026-08-17, the truncation notice shipped: `scripts/decision_surface.py` (`render_truncation`, `lookup_split`), `scripts/test_decision_surface.py`. **The other adopted concept — justification strings on exemption entries in `scripts/repo_paths.py` — is NOT built.** Corrected from `not yet` by review the same day: the notice landed in the commit that carried this ADR, so `_execution_warning` was rendering *"NOT EXECUTED — decided, never built. Do not act on it as settled."* onto `scripts/repo_paths.py`, telling an editing agent that a half-shipped decision was never begun. That is ADR-0008's 12-day gap inverted, injected as a directive.
- **Decision driver:** New tool surfaced. Lorenzo: "read active and design surfaces, don't grep, then evaluate: https://github.com/deepseek-ai/deepseek-harness".

> **Watching for:** **BOTH** of (a) an Anthropic/Claude adapter landing in `packages/llm/`, and (b) the Claude Code hook bridge supporting PreCompact **and** PreToolUse `additionalContext` **and** SessionStart plain stdout. Either alone does not move the verdict: (a) without (b) means Claude with no Tessera harness; (b) without (a) means Tessera's harness driving a model we do not use.
> **Next check:** 2026-10-16

---

## Target

- **Name:** DeepSeek Harness (`dsh`)
- **URL:** https://github.com/deepseek-ai/deepseek-harness
- **What it is:** An open-source **agent harness** — the layer Claude Code occupies — built on a vendored fork of [Cordis](https://github.com/cordiverse/cordis), where every part of the product including the agent loop is a replaceable plugin.

---

## Side-by-side summary

| Dimension | Tessera | DeepSeek Harness |
|---|---|---|
| Maturity | Solo, ~2 months dogfood, 6 downstream projects | Repo published 2026-08-13 (4 days before this ADR) carrying 12,404 commits from private development. Sole release `dsh-v0.1.0-rc.7`. Self-described "developer preview", breaking changes promised. |
| Cross-runtime | Claude Code only (hooks, `settings.json`, skills) | Its own runtime. Two LLM adapters: `llm-deepseek`, `llm-pi-ai`. **No Anthropic adapter.** |
| Original IP | Project profiles, override mechanism, gate/friction log, spend authorization, escalation packets, haziness scoring, restore receipts, `degraded` events | The Cordis plugin composition model (profiles/bundles/patch layers); capability seams as a three-role contract; ~30 executable documentation gates; the Agent Note lifecycle |
| Maintenance model | Solo | Corp-backed (DeepSeek AI), 24 contributors |
| License | MIT | MIT |
| Community size | Single user (Lorenzo) | 148,535 stars · 15,196 forks · 623 watchers, accumulated in four days |
| Primary problem solved | *The agent's own reliability* — instrumentation that makes agent failure visible (ADR-0006) | *Building and replacing every part of an agent runtime* from configuration |
| Distinct strength | Fail-loud instrumentation fired on events, not elected by a model | Documentation integrity enforced by executable gates, and required disclosure of what a component does **not** do |

---

## 1. Identity & maturity

MIT, TypeScript, DeepSeek-corp-backed, 24 contributors. The repository was created **2026-08-13** and already carries **12,404 commits**, so this is a private codebase published wholesale rather than a project developed in the open — there is no public history to read for direction, which is normally dimension 1's most informative signal. The sole release is `dsh-v0.1.0-rc.7`, published the day this ADR was written. The README states *"developer preview… THERE WILL BE COMPATIBILITY-BREAKING CHANGES"*, and their own `AGENTS.md` opens with a section titled **"Remove this section at the first tagged release"** — an explicit, self-dated marker that they have not shipped one.

**148,535 stars in four days, and this ADR deliberately assigns them no weight.** Stars accumulated that fast measure attention, not usage; there has not been enough elapsed time for anyone to have adopted the thing and formed a view. Compare ADR-0021's reading of Deep Agents, where 27.5k stars against 3.8k **forks** and 205 open issues was read as usage. Here open issues are 0 (the tracker directs to Discussions) and the fork ratio reflects a four-day spike. Treating the number as a quality signal would be the skill's named single-dimension anti-pattern.

**Bias risk is vendor loss-leader, and unlike ADR-0021's LangSmith shape it is not subtle.** The harness ships adapters for DeepSeek's own models and for `pi-ai`, and nothing else. The value of the harness to DeepSeek is inference demand. That is not a criticism of the engineering — which is exceptional — but it is decisive for a framework whose entire dogfood runs on Claude.

**A bias of my own, named because the skill requires it: excitement.** This is the most rigorously engineered agent repository I have read, and several of its documentation mechanisms are direct upgrades to work Tessera has open right now. That is a reason to hold the verdict to the methodology, not a reason to reach it faster.

---

## 2. Problem-space overlap

| Overlap area | Tessera approach | Their approach | Classification | Notes |
|---|---|---|---|---|
| The harness itself | Claude Code, per principle #10 (single-harness focus) | Own runtime, agent loop as a replaceable plugin | **Conflicting** | Two harnesses cannot drive one session. Principle #1 (native primitives first) and ADR-0014 §2 (harness-layer content buys no provider portability) both point the same way. |
| Hook lifecycle | Bash/Python hooks on Claude Code events | Typed Cordis interception points; shell-hook bridges as a *compatibility path* their own README discourages | **Conflicting** | Their bridge maps 7 of Claude Code's 30 events. See §3. |
| Compaction / context recovery | Mnemos three-layer defense on PreCompact/SessionStart/PreToolUse | `packages/compaction` — pressure detection at `agent/pre-step`, overflow recovery at `agent/request-error`, tool-result pruning before summary selection | **Different bet** | Theirs is inside the loop and therefore cannot miss an event; ours is outside it and therefore portable. Theirs is the better mechanism *given* you own the loop. |
| Documentation truth | `scripts/doccheck.py` asserts claims docs make about the repo | ~30 `verify-*` gates **plus** generated reference docs regenerated from source | **Compatible** | Same problem, they are a rung higher on the same ladder. This is where the value is. |
| Decision records | ADRs (immutable, append-only `Executed:`) + observatory | Agent Notes with a `proposed/implemented/rejected/archived` lifecycle, path-encoded status, machine-verified format and classification | **Compatible** | Directly informs Tessera's open ADR-authority problem. |
| Standing lessons | 12 standing patterns, hook-injected every session (principle #17) | `deepseek-harness/docs/defensive-patterns.md`, read on demand via an `AGENTS.md` pointer | **Different bet** | Convergent evidence the artifact is right. Ours wins on channel; theirs wins on scope discipline (a 550-word gate-enforced ceiling). |

**Tessera does not address (gaps in our design they fill):**
- Generated documentation — deriving claim-bearing sections from source so a class of drift cannot occur, rather than asserting each claim after the fact.
- A lifecycle for decision records, including `proposed`/`rejected` states and an explicit mechanism for demoting a record **out of** authority.
- Documented per-component token and KV-cache cost.
- Machine-checkable cross-references between documents.

**They do not address (gaps in their design we fill):**
- **Instrumentation of the human-agent working relationship.** Nothing in `dsh` records whether the agent surfaced a decision before committing to it (gate log), whether a handoff sufficed (T2 restore receipts), whether a component could not do its job (`degraded`), or an escalation packet for asynchronous blockage. All ~30 of their gates check the code artifact. This is ADR-0006's territory and it is entirely unduplicated here.
- Project profiles and any notion of a sensitive-data posture.
- Spend authorization.

---

## 3. Integration cost

The interesting fact is that this dimension is **measurable rather than estimated**, because `packages/hooks/hooks-claude-code` is a Claude Code hook bridge and its README documents both the mapping and its gaps.

Against Tessera's actually-wired hooks:

| Tessera hook | Channel it uses | Bridge behaviour |
|---|---|---|
| 5 × SessionStart surfacers, 6 registrations (mnemos-resume, findings, watch, standing patterns ×2) | **bare stdout** | Only JSON `additionalContext` is consumed → **nothing delivered**. Also runs detached, so context "can miss the first request" (their `TODO(session-start-gating)`). |
| `icpg-session-base.sh` — the 6th SessionStart registration | stamps the SessionStart SHA on disk | **A separate and larger loss, missed by the first draft of this table.** It is not a surfacer: the iCPG Stop-hook recorder anchors symbol attribution on the SHA it stamps (ADR-0019). Under the bridge, SessionStart runs detached with no ordering guarantee against the first tool call, so intent recording is not merely silent — it is unanchored. |
| `tessera-decision-surface.sh`, `mnemos-pre-edit.sh`, `mnemos-post-compact-inject.sh` | PreToolUse `hookSpecificOutput.additionalContext` | **"`additionalContext` is ignored"** → all three silent. |
| `mnemos-pre-compact.sh` | PreCompact | **Event unsupported** — one of 23 unmapped events. |
| Stop gates (`tessera-gate-scan`, `tessera-verify-scan`, `tessera-restore-scan`), exit 2 | Stop | Maps to `steer()`, but **the consecutive-block cap is not implemented** (`TODO(stop-loop-guard)`): "an unconditionally blocking hook therefore force-continues every step unless it self-limits." |

**Adopt fully (replace Tessera with it):**
- Switching cost: rewrite the harness as TypeScript Cordis plugins **and** stop using Claude, since no Anthropic adapter exists.
- What is lost: every hook-delivered instrument. Note the *shape* of the loss — the hooks would still run and still exit 0. This is standing pattern #9 (*a mechanism that RUNS has not necessarily REACHED its audience*) reproduced at an integration seam, and it would present as a working migration.
- What is gained: an owned loop, and compaction that cannot miss its own event.

**Adopt patterns (steal ideas, keep Tessera):** six candidates, §4. Two land on files with open findings; four are new work. Effort is days, in Python, in Tessera's idiom.

**Hybridize (run alongside):** not available. Two harnesses cannot drive one session.

**Continue without:** zero cost. Nothing in Tessera degrades by not adopting.

---

## 4. Pattern-level vs implementation-level

| Pattern | Verdict | Notes |
|---|---|---|
| Cross-references are relative Markdown links, never bare prose or numbers, gated by `verify-md-links` | **Idea-only** | Their stated reason is *"so they are mechanically checkable."* This is the general form of live queue item 2: `referenced-paths-exist` misses `docs/design-principles.md:672`'s phantom `tdd-loop-check.sh` **only because the backtick carries no `scripts/` prefix**. A link has no such ambiguity. Also dissolves the phantom-index-key class. **Larger than the minimal fix for item 2 — see §6.** |
| Exemption lists carry a per-entry justification string, and a stale entry fails the gate | **Idea-only** | `NO_LIMITATIONS`/`NO_MODEL_EXPERIENCE_SECTION` are `{path: reason}` maps, and the gate errors when a key no longer names a real package. This is the structural remedy for the 2026-08-15 `PATH_ALLOWLIST` defect, where "not required to exist on disk" was generalised to "not ours" from one comment block and silenced a live 16KB file. A required reason makes the two semantics unmergeable. |
| `## Known Limitations and Deferred Work` as a required, gate-enforced section | **Idea-only** | **Standing pattern #12 mechanized.** Their hook bridge announces "23 of Claude Code's current 30 events unsupported" in its own output — which is why §3 of this ADR is measured rather than guessed. |
| `## Model Experience` — "What the model sees / Token effect / KV Cache effect" required per package | **Idea-only** | Novel; I have not seen it elsewhere. Lands on live Tessera work: the 2026-07-27 effort/cache reread measurement, the 0%-cache-read fleet finding, the ~15.6k eager prefix. |
| Generated doc regions headed "do not edit by hand" | **Idea-only** | The rung above doccheck: an assertion catches drift, derivation removes the class. |
| Agent Note lifecycle: `{proposed\|implemented\|rejected\|archived}/{class}/date-topic.md`, mandatory `## Alternatives considered`, frozen archive with an append-only hash manifest | **Idea-only** | Two things Tessera lacks: a `proposed`/`rejected` lifecycle, and a way to demote a record **out of** authority — the problem `⚠ REVISITED by N later record(s)` currently attacks from the opposite end. Their decision/fact split is also sharper than our `Executed:` line: an implemented note is *kept current with shipped facts — paths, names, structure — never the decision*. |
| Word budgets on always-loaded docs (`doc-budgets.manifest.json`; root `AGENTS.md` ≤ 1,950 words, gate-enforced) | **Watching, not adopting** | ADR-0021 declined a threshold on the eager prefix on principle-#3 grounds: size is the artifact, dilution is the pain. That reasoning holds in general. The case where it may not: for an always-loaded file, words shipped **are** the delivered payload, not a proxy for it. Recorded in the observatory, not decided here. |
| The Cordis plugin model, capability seams, the harness | **Skip** | Layer. |
| "Document current state, not change history" + the slop checklist hunting "previously / now / no longer" | **Skip, but named** | Directly opposed to Tessera's house style, where the trail is load-bearing. Not proposing a change. Worth stating that a 312KB `active.md`, a checkpoint that overflowed its delivery channel, and a handoff whose heading must be structurally first are the costs their tier taxonomy exists to avoid, and Tessera has paid all three. |

---

## 5. Lock-in & maintenance

**If we adopt (patterns only):** nothing. Every adopted item is a convention plus a Python check in `scripts/doccheck.py`. No runtime dependency, no exit cost.

**If we adopt (the harness):** everything — loop, tools, persistence, and the model. Exit would be a second rewrite. Compounded by a self-declared pre-release stance whose own words are *"Backends reject old on-disk formats"* and *"`SESSION_FORMAT_VERSION` at `0` with no compatibility promise."*

**If we do not adopt:** unchanged. Tessera keeps its own maintenance burden, which was already all on us.

---

## 6. Decision

**Verdict: Reject as a harness. Adopt two patterns; record the rest. Watching on the harness with the two-part condition above.**

*Arithmetic, stated because an earlier draft said "two now, four recorded" and it did not reconcile with §4:* §4 marks **six** of their patterns Idea-only. **One** of the six is adopted here (exemption justifications); **five** remain recorded, including steal #1 (links), which §6 separately declines as a sweep. The **second** adopted item — the truncation notice — is not theirs at all; it is Tessera's own mirror finding. So: 1 of 6 adopted, 5 recorded, plus 1 adopted from the mirror.

**Reasoning.**

This is the third consecutive evaluation rejected on **layer** — ADR-0021 (Deep Agents), ADR-0023 (Switchyard), now this. That consistency is worth a moment of suspicion rather than satisfaction: a framework that rejects everything on the same ground may be using the ground as a shield. The check is whether the rejection survives contact with a measurement, and here it does, twice over. First, there is no Anthropic adapter, so adoption means not running Claude. Second, and more usefully, their own hook bridge documents that **7 of Claude Code's 30 events** are mapped, and the four Tessera relies on most are unsupported or partial in exactly the ways that would silence Tessera's instruments while leaving every hook exiting 0. The layer objection is not a reflex here; it is a table.

**The mirror, and it is the more valuable half of this ADR.** Checking whether an ADR would even be a viable channel for the two patterns worth building surfaced a live defect in Tessera's own decision surface. `decision_surface.MAX_DOCS = 3`, sorted `(kind != "adr", adr_filename)` ascending — ADRs first, **oldest first**. Of 146 index keys, **46 are truncated by that cap** and on **23** of them a new ADR would be hidden outright; the render carries no notice that anything was dropped. Concretely: **ADR-0022, "A crashed doccheck check blocks the commit", is invisible on `scripts/doccheck.py`** (12 matched, 3 shown), and **ADR-0015, which created the P3 predicate `tessera-watch` owns, is invisible on `bin/tessera-watch`** (14 matched, 3 shown). This ADR would have joined them. **Three counts had to be separated to state that honestly, and the first two attempts got it wrong** — a stale figure, then a correction that re-ran the original script and inherited its wrong denominator (direct attachment, ignoring the prefix matching `lookup()` performs, understating by ~3×). Both were caught by review, not by re-measuring; `docs/observatory.md` carries the full accounting. That is standing pattern #12 — a report entirely true, silently narrowed, the narrowing absent from the output — committed by the hook built to defeat silent failure, in the same session as an evaluation praising DeepSeek for mechanizing the disclosure of exactly this. Recorded as its own observatory entry.

**Why two patterns are separated from the other four.** Steals #1 and #2 are not new scope; they are candidate remedies for findings already open. But their channels differ, and that difference decides how each is queued. `scripts/repo_paths.py` **is not in the decision-surface index at all** — zero governing records, despite live queue item 1 opening with "read `scripts/repo_paths.py`'s module docstring before touching the decision surface." Naming it here gives it its only record and a guaranteed first-position surface on first edit. `scripts/doccheck.py` is already over the cap, so recording steal #1 against it would be decoration; its real channel is queue item 2 in `active.md`, which rides `tessera-watch-surface.sh` and fires at every SessionStart. This ADR points at that item rather than duplicating it into a channel that drops it.

**One thing this ADR makes worse, stated rather than hidden.** Live queue item 3 records that four ADR `Next check:` dates ride on human recall and that registering one changed nothing. This ADR's 2026-10-16 is inert prose parsed by no predicate, and adding it is not progress on that item. **The count was also wrong in a way this ADR's own review exposed: it is nine live, not four** — six had never been counted, including ADR-0005 (autonomy readiness) and ADR-0006 (the instrumentation charter) — and a purpose-written parser still missed one on punctuation, because the field exists in three prose shapes. See `docs/observatory.md` → "An ADR's `Next check:` date is inert prose".

**Concepts adopted (with implementation notes):**
- **Exemption entries carry a justification, and a stale entry fails the check.** Convert `PATH_ALLOWLIST`/`FOREIGN_PATHS` in `scripts/repo_paths.py` from bare sets to `{path: reason}`, and add a doccheck assertion that every key still names something real. Closes the class behind the 2026-08-15 defect. Guard must be re-planted against a break **in** the filter, not beside it — the 08-15 lesson.
- **A truncation notice on the decision surface.** Render `…and N more (cut by MAX_DOCS)` with the names. Deliberately **notice-only**: additive output cannot suppress a live record, which is precisely how the 08-15 allowlist "fix" went wrong. Raising the cap or changing the sort is a separate decision and is not taken here.

**Concepts considered and rejected (with reasoning):**
- **The harness.** Layer, plus no Anthropic adapter, plus a measured 7-of-30 hook bridge.
- **Word budgets as a gate.** Same proxy ADR-0021 declined. Recorded in the observatory with the one argument that might overturn it.
- **Current-state-only documentation.** Genuine tension with Tessera's trail-keeping, but the trail has earned its keep repeatedly and this is not the evidence that would retire it.
- **A link-conversion sweep across `docs/` as this ADR's execution.** The minimal fix for queue item 2 is narrowing `DOC_SKIP` so the foreign-path check runs on ADRs. Bundling the larger convention into this evaluation would be scope creep dressed as adoption.

**Re-evaluate trigger conditions:**
- **Both** an Anthropic adapter in `packages/llm/` **and** hook-bridge support for PreCompact + PreToolUse `additionalContext` + SessionStart stdout.
- The bridge's unsupported-event list drops below 10 of 30.
- The first **tagged** (non-`rc`) release — their own "Remove this section at the first tagged release" line is the marker.
- Next cadence review: 2026-10-16.

---

## References

- https://github.com/deepseek-ai/deepseek-harness — `README.md`, `AGENTS.md`, `deepseek-harness/docs/AGENTS.md`, `deepseek-harness/docs/architecture.md`, `deepseek-harness/docs/defensive-patterns.md`, `.agents/notes/README.md`, `packages/hooks/hooks-claude-code/README.md`, `deepseek-harness/scripts/doc-budgets.manifest.json`. **Their paths carry the repo prefix on purpose:** written bare, `decision_surface._PATH` indexes them as *Tessera* paths, which is the ADR-0023 defect. The first draft of this ADR did exactly that, and `DOC_SKIP` meant doccheck could not see it — the observatory entry carrying the same four paths went red instantly. See `docs/observatory.md` → "Word budgets on an always-loaded doc", closing note.
- https://github.com/cordiverse/cordis — the vendored plugin framework
- `docs/adr/0021-deep-agents-evaluation.md` — prior rejection on layer; the prefix-measurement mirror this ADR's word-budget entry re-opens
- `docs/adr/0023-switchyard-evaluation.md` — prior rejection on layer
- `docs/adr/0014-review-backend-seam.md` — §2, harness-layer content buys no provider portability
- `docs/adr/0006-instrumentation-not-control.md` — the framing under "they do not address"
- `docs/observatory.md` — "The decision surface silently drops its newest records", "Word budgets on an always-loaded doc"
