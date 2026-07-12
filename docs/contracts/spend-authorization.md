# Contract: external-spend authorization

**Status:** Canonical. Owned by Tessera (the producer). Defined here; consumers conform.

The authorization layer between an agent and *external, irreversible* spend — booting a GPU,
starting an instance. Spec 06; promoted to Tier 1 by ADR-0005.

## Why this exists

In conclave, **14 of 25 recorded gates (56%) are `terraform apply` / `terraform destroy`**
against g6e GPUs. Every one was a human saying yes to *one specific boot*. Delete the human
and nothing stands between the agent and the instance. Spend is the one class of decision that
is irreversible in the way that matters: money leaves, whereas a wrong refactor can be reverted.

**This is an authorization layer, not an accounting layer.** Tessera does not meter dollars.
AWS does, and it is the only system that knows the real number — spot vs on-demand, AZ,
actual runtime. Tessera answers a different question: *is this run authorized to commit
external spend at all?*

## The three layers

Each in a different trust domain. Do not collapse them.

| Layer | Where | Bounds |
|---|---|---|
| **1. This guard** | in-band, PreToolUse | *authorization* — may this run commit spend at all |
| **2. `tessera-escalate`** | async human gate (spec 07) | what a blocked agent does instead of routing around |
| **3. Cloud budget** | out-of-band (conclave: `budget.tf` → SNS → `hardstop.tf` lambda; `gpu.tf` idle-stop) | *blast radius* — the ceiling an agent cannot talk its way past |

Layer 3 is the real backstop and it is **stronger** than layer 1, because it is outside the
agent's trust domain. Layer 1 exists because layer 3 is a *monthly* cap, not a per-run
authorization: it bounds the damage, it does not decide whether the boot should happen.

## The invariant

> **A spend gate must never be able to block the exit.**

Cost-**reducing** commands — `terraform destroy`, `terraform apply -var enable_gpu=false`,
`aws ec2 stop-instances` — are **allowed unconditionally**. No authorization required, no
expiry check, no exceptions.

This is not a nicety. Spec 06 as originally written hard-stopped by *"rejecting further
Edit/Write/Bash"* on budget overrun. Teardown is a Bash command. That design would freeze an
agent with a live GPU and block its own teardown — **causing the exact runaway spend it
existed to prevent.** Any future change to the guard must preserve this invariant;
`test_teardown_always_allowed_even_with_no_authorization` is the check.

## Command classification

`scripts/spend/guard.py::classify` → `committing` | `reducing` | `neutral`.

The command is split on shell separators (`&&`, `||`, `;`, `|`, newline) and each segment
classified. **`committing` wins across segments** — otherwise
`terraform destroy && terraform apply` reads as a teardown and boots a GPU for free. Within a
single segment, `reducing` wins, so `terraform apply -var enable_gpu=false` reads as the
teardown it is.

A bare `terraform apply` is **committing**: `enable_gpu` may be true in a `.tfvars` the guard
cannot see.

### Wrapper scripts are read one level down

The guard only ever sees the Bash command **string**, so `./scripts/sweep-gpu-capacity.sh` is
opaque by name. **conclave's sweep script runs `terraform apply -auto-approve` on line 23** — it
boots g6e GPUs, it is the AZ-sweep named in the gate log, and a name-only classifier waves it
straight through. Found 2026-07-12 while live-firing this guard *in conclave*; it was a live
hole in the flagship downstream, and it is the reason "existence is a local fact, reachable is
the shared one" now has a spend-shaped sibling: **a classifier that reads the command but not
what the command runs is checking the wrong text.**

So: if a segment invokes a local `.sh`/`.py`/`.bash` file that exists, the guard reads it
(comments stripped) and classifies its contents. **One level, no recursion.**

> **The pattern list is a recall net, not an oracle.** A script that calls a script that boots
> a GPU still slips through, as does anything using a cloud SDK (boto3 `run_instances`) rather
> than the CLI. Layer 3 is what bounds the misses. A miss is a finding *about the list*, and
> the fix is a pattern plus a regression test — same standing rule as `doccheck.py`.

### Mentions read as invocations. This is accepted.

The guard does **not** strip quoted strings before classifying, so `grep -r "terraform apply" .`
is blocked, and so is a heredoc that merely quotes the command. Both bit the author while
building this.

Stripping quotes would silence that — and would open `bash -c "terraform apply"` as a clean
bypass. Distinguishing a mention from an invocation in untyped shell text is not reliably
possible. **On a spend boundary, an evasion hole is a far worse trade than a noisy block:** a
false block is an annoyance with an escape hatch, a false allow boots a GPU.

If a false positive blocks you and no spend is involved, **use a non-Bash tool** (Write/Edit
commit no external spend and are not gated). Do **not** grant yourself a spend envelope you do
not need, and do not reword the command to slip past the pattern.

## The grant

`.tessera/spend-auth.json` — **gitignored**. A live authorization is run-scoped state, not a
shared fact. The audit trail is the event log (below), not the file.

```jsonc
{
  "granted_at": "2026-07-12T19:32:31Z",
  "expires_at": "2026-07-12T23:32:31Z",  // ENFORCED
  "usd": 20.0,                            // audit + agent context; NOT enforced
  "note": "chunk 4 judge eval",
  "granted_by": "lorenzociacci",
  "session_id": "uuid"                    // nullable
}
```

**The TTL is what is enforced; the dollar figure is not.** This is the honest bound Tessera can
hold. For a GPU, cost is ~linear in runtime, so a time-boxed envelope *is* a spend bound — and
the cloud budget is the backstop when the estimate is wrong. Do not add dollar arithmetic here
without a reason that survives the question *"why not let AWS, which knows, do it?"*

Fails **closed**: absent, unreadable, corrupt, or expiry-less ⇒ **not a grant**.

```bash
tessera-authorize grant --usd 20 --ttl 4h --note "what this run needs to boot"
tessera-authorize show      # exit 1 if no live envelope
tessera-authorize revoke
```

## Events

Appended to `.tessera/logs/<session-id>.jsonl`, same shape as the gate and override channels
(`type` / `ts` / `session_id` / `source` / `data`). `source` is `spend-guard`.

| `type` | Emitted when | `data` |
|---|---|---|
| `spend_authorized` | a grant is issued | the grant object |
| `spend_revoked` | a grant is revoked | `{revoked_at}` |
| `spend_denied` | the guard blocks a command | `{command, reason}` — command truncated to 200 chars |

`spend_denied` is the friction journal for spend (principle #12): it records every time an
agent tried to commit spend it was not authorized for. **A burst of `spend_denied` under an
unsupervised run is the signal that the envelope was set too small** — it is data, not a fault.

## Hook

PreToolUse, matcher `Bash` → `.claude/scripts/tessera-spend-guard.sh` → `scripts/spend/guard.py`.
Exit 0 = allow, exit 2 = block with stderr fed to the model.

**The wrapper fails OPEN** (no `jq`, no `python3`, guard missing, bad cwd) — a hook that wedges
every Bash call is its own outage, and layer 3 bounds the damage. **`guard.py` itself fails
CLOSED**: if it runs at all, no readable grant means no spend. That split is deliberate; it is
the only place in Tessera where an unreadable file must not be shrugged off.

On deny, the model is told both paths: ask for an envelope if a human is present, raise a
`spend_unauthorized` escalation packet if not — **and explicitly not to route around it.**
