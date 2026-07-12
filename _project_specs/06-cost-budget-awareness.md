# Spec 06: External spend authorization

**Status:** v1 shipped 2026-07-12
**Priority:** Tier 1 — promoted from Tier 3 on 2026-07-11 (ADR-0005)
**Effort:** Small
**Contract:** `docs/contracts/spend-authorization.md`

> **Retargeted 2026-07-12, before implementation.** This spec used to be about *Claude token
> budgets* — declare `tokens`/`api_calls` on a ReasonNode, accumulate from the transcript,
> hard-stop when the meter runs out. That was the right spec for its original Tier 3 framing
> (*"agents stuck in loops burn real money"*). **It is not the spec ADR-0005 promoted.**
>
> ADR-0005 promoted this on one finding: *an unsupervised agent in conclave is an agent that
> boots GPUs on its own.* **A token budget cannot stop `terraform apply enable_gpu=true`.** The
> agent commits hundreds of dollars of AWS spend inside a few thousand tokens — comfortably
> within any token ceiling. Every one of the old spec's five success criteria was
> token-denominated; not one mentioned cloud spend. Built as written, it would have shipped
> green with the GPU boot path untouched.
>
> The token budget is real but minor, and it is a *different mechanism*. It has been split out
> to **spec 10**, at Tier 3, where it was correctly filed to begin with.

## The problem

In conclave, **14 of 25 recorded gates (56%) are `terraform apply` / `terraform destroy`**
against g6e GPUs. Every one was a human saying yes to *one specific boot*. Spend is the one
class of decision that is irreversible in the way that matters: money leaves; a wrong refactor
can be reverted.

Delete the human and nothing stands between the agent and the instance.

## What already existed — and why we did not rebuild it

conclave shipped a cost layer at v0.5. Verified end to end on 2026-07-12, not taken on faith:

- `infra/budget.tf` — $100/mo cap, alerts at 50/80%, 100% → SNS
- `infra/hardstop.tf` — SNS → Lambda → `ec2:StopInstances` on `aws:ResourceTag/project=conclave`
- provider `default_tags { project = "conclave" }` — **the GPU carries the tag the IAM policy
  keys on.** The stop chain is intact.
- `infra/gpu.tf` — two idle-stop alarms (GPU-util primary, CPU backstop), native `ec2:stop`
- `enable_gpu` defaults `false`

**That is the hard ceiling, and it is in a better place than this spec could put it** — it is
*out-of-band*, outside the agent's trust domain. An agent cannot confuse its way past AWS
Budgets. A PreToolUse hook is in-band and strictly weaker. Rebuilding it in Tessera was the
wrong rung.

But it answers *"how much can conclave spend this month?"* — **not** *"is this agent, on this
run, authorized to boot a GPU at all?"* The cap is a **blast-radius bound, not an
authorization**. By its own comment, Budgets evaluates ~3×/day on lagging ACTUAL cost, so the
hardstop bounds overrun to "a few hours", not zero. Idle-stop only catches *idle* — an agent in
a busy inference loop keeps the GPU hot and never trips it.

## What v1 built

A **pre-commitment authorization gate**. Not accounting — Tessera does not meter dollars; AWS
does, and it is the only system that knows the real number.

1. **`bin/tessera-authorize`** — a human grants a run-scoped envelope up front:
   `tessera-authorize grant --usd 20 --ttl 4h --note "chunk 4 judge eval"`.
   **This is the piece that converts conclave from supervisable-only to unsupervised**: it
   collapses fourteen synchronous gates into one up-front authorization.
2. **`scripts/spend/guard.py`** + PreToolUse hook (matcher `Bash`) — classifies each command
   `committing` / `reducing` / `neutral`; denies committing commands with no live grant.
3. **Cost-reducing commands are never blocked.** See the invariant below.
4. **Denied → escalation.** The model is told to raise a `spend_unauthorized` packet (spec 07)
   and explicitly **not** to route around the block.
5. **Every grant, revoke, and denial is an event** in `.tessera/logs/<session>.jsonl`.
   `spend_denied` is the friction journal for spend.

## The invariant — and the flaw that produced it

> **A spend gate must never be able to block the exit.**

The old spec's Step 4 hard-stopped by *"rejecting further Edit/Write/Bash"*. **Teardown is a
Bash command** — four of those conclave gates are `aws-teardown`. That design would freeze an
agent with a live GPU and block its own teardown, **causing the exact runaway spend it existed
to prevent.** conclave's idle-stop would have eventually caught it — by luck, not design.

Cost-reducing commands are therefore allowed unconditionally: no authorization, no expiry
check, no exceptions. `test_teardown_always_allowed_even_with_no_authorization` is the check.

## Why the TTL is enforced and the dollar figure is not

Pricing a boot up front — spot vs on-demand, AZ, unknown duration — is a rabbit hole, and AWS
already knows the real number. Tessera enforces **time**, which is the bound it can honestly
hold; for a GPU, cost is ~linear in runtime, so a time-boxed envelope *is* a spend bound. The
cloud budget is the backstop when the estimate is wrong.

Three layers, three trust domains. Do not collapse them.

## Success criteria — all met

1. ✅ `terraform apply -var enable_gpu=true` with no live grant → **blocked** (exit 2), with the
   escalation path in stderr. Live-fired, not inferred.
2. ✅ `terraform destroy` / `enable_gpu=false` / `stop-instances` → **allowed with no grant.**
3. ✅ `terraform destroy && terraform apply` → **blocked.** (A first-match classifier reads
   `destroy`, says "reducing", and boots a GPU for free. Committing wins across segments.)
4. ✅ A live grant permits the boot; an expired or revoked one does not.
5. ✅ Corrupt/absent grant ⇒ not a grant (fails closed).
6. ✅ No grant declared and no spend command ⇒ no enforcement. Backward compatible.
7. ✅ 45 tests, `scripts/spend/`.

## What live-fire found that the design did not

Both of these were found by running the guard in conclave, not by reasoning about it. Neither
was predicted.

1. **A live hole in the flagship downstream.** `scripts/sweep-gpu-capacity.sh:23` runs
   `terraform apply -auto-approve` — it boots g6e GPUs, and it is the AZ-sweep named in the
   gate log. The guard sees only the command *string*, so the wrapper's name told it nothing.
   **A classifier that reads the command but not what the command runs is checking the wrong
   text.** Fixed: local scripts are read one level down. This is the spend-shaped sibling of
   *"existence is a local fact; reachable-by-the-consumer is the shared one."*

2. **The guard blocked its own wiring commit, and I misread the result.** The command that was
   supposed to install the guard into conclave contained `terraform apply` inside a quoted test
   string; the guard blocked the *entire* Bash call, so **none of the wiring ran** — and the
   probe that followed happily reported `allowed` for a GPU boot, because the wrapper fails open
   when the guard is absent. It looked like a working guard saying yes. It was a missing guard
   saying nothing. Caught only by checking whether the files were actually on disk.

## Known ceilings

- **The pattern list is a recall net, not an oracle.** A script that calls a script, or
  anything using a cloud SDK (boto3 `run_instances`) instead of the CLI, still slips through.
  Layer 3 bounds that. A miss is a finding *about the list* — fix is a pattern plus a
  regression test.
- **`echo "terraform apply" | bash` is not caught, and never was** — the pipe splits to a bare,
  neutral `bash` segment. Nor is a cloud SDK call, nor a script calling a script. This guard
  stops an agent that boots a GPU *by mistake or without authorization*; it is **not** built to
  defeat one actively trying to evade it, and such an agent has easier routes. Layer 3 bounds
  all of it.

## The false-positive posture, and why it changed

v1 stripped nothing and blocked every *mention* of a boot command. It produced **four false
positives against its own author in one session**: a test heredoc, the command that installed
it into conclave, the commit message describing it, and the gate-log entry describing the false
positive. Each blocked work that committed no spend at all.

The original argument for the noise was that stripping quotes opens `bash -c "…"` as a bypass.
Checking that argument rather than trusting it: **the "no evasion" property was already only
partly true** — `echo "…" | bash` splits to a bare, neutral `bash` segment either way. The noise
was buying less than it appeared to.

So quoted text and heredoc bodies are now treated as **data**, *unless the command is
wrapper-led* (`bash -c`, `python3 -c`, `eval`, a heredoc fed to a shell), in which case they are
code and nothing is stripped. Wrapper-ness is decided on the **whole command, never per
segment** — `python3 -c "a; b"` splits on the `;` inside its own quotes, and judging the
fragment in isolation reopens the very bypass this is only safe without. That mistake was made
and caught by the tests before it shipped.
- **The hook wrapper fails open** (no `jq`/`python3`/guard) — a hook that wedges every Bash
  call is its own outage. `guard.py` itself fails closed.
- **`tessera-authorize` is human-invoked, by design.** The agent cannot self-authorize. If a
  future flow needs an agent to raise its own envelope, that is a new decision, not an
  extension.

## Deferred

- **Per-command cost estimation.** Deliberately not built — see above.
- **Budget-aware fatigue (the 5th Mnemos dimension).** Belonged to the token-budget framing;
  moved to spec 10.
- **`icpg budgets list`.** Nothing to list until there is accounting, and there is none.

## Depends on

- Spec 07 (escalation) — shipped. This spec is its trigger.
- Nothing else.
