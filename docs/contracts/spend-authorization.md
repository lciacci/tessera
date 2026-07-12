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

### A mention is not an invocation

Quoted strings and heredoc bodies are **data** and are stripped before the committing check.
`grep -r "terraform apply" .`, a commit message describing a GPU change, and a heredoc writing
a test file all pass — they commit no spend.

**Unless the command is wrapper-led**, in which case that text is *code*, and nothing is
stripped:

```
bash -c "terraform apply"        BLOCKED    the quotes hold code
python3 -c "os.system('…')"      BLOCKED
eval 'terraform apply'           BLOCKED
bash <<'EOF' … EOF               BLOCKED    heredoc fed to a shell runs
cat >> t.py <<'PY' … PY          allowed    heredoc fed to cat is a file being written
git commit -m "… terraform …"    allowed    git does not exec its message
```

**Wrapper-ness is decided on the WHOLE command, never per segment.** `python3 -c "a; b"` splits
on the `;` *inside its own quotes*, and the resulting fragment no longer looks like a wrapper —
judging fragments in isolation reopens the exact bypass the stripping is only safe without.
Global, and conservative: if any part of the command can execute its own literals, none of it
is stripped.

> The first version of this guard stripped nothing and blocked every mention. It produced four
> false positives against its own author in one session — a test heredoc, the command that
> installed it into conclave, the commit message describing it, and the gate-log entry
> describing the false positive. The reason it was safe to soften: the "no evasion" property
> was already only partly true (`echo … | bash` splits to a bare, neutral `bash` segment either
> way), so the noise was buying less than it appeared to.

**Residual, known:** `echo "terraform apply" | bash` is not caught, and never was. Nor is a
cloud SDK (boto3 `run_instances`), nor a script calling a script. Layer 3 bounds all of them.
This guard stops an agent that boots a GPU **by mistake or without authorization** — it is not
built to defeat one actively trying to evade it, and an agent doing that has easier routes.

If a false positive still blocks non-spend work, **use a non-Bash tool** (Write/Edit commit no
external spend and are not gated). Do **not** grant yourself a spend envelope you do not need,
and do not reword a genuine spend command to slip past the pattern.

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

> **The log is the one artifact that must never be manufactured.** `scripts/spend/conftest.py`
> strips `CLAUDE_CODE_SESSION_ID` for the whole suite, because without it every hook test wrote
> a *real* `spend_denied` to the production log — 26 of one session's 31 denials were made by
> pytest. Same lesson as the Mnemos trial's `manual`/`auto` compaction split: **a test must
> never become evidence about the thing it tests.**

## The backstop — a denial must be dispositioned

The guard's deny path ends in a *prose instruction* ("raise a packet and stop"). That is model
recall, and this repo has watched model recall fail twice (the gate recorder missed ~85%;
doccheck's lesson sat in prose through five more bugs). **A mechanism whose failure path rides
recall has no failure path.**

Stop hook `.claude/scripts/tessera-spend-backstop.sh` → `scripts/spend/backstop.py`:

| denied → | verdict |
|---|---|
| a human granted an envelope (`spend_authorized` *after* the denial) | ✓ the supervised path |
| an escalation packet was raised this session | ✓ the unsupervised path |
| **neither** | ✗ the block vanished silently — **exit 2** |

A grant *before* the denial does not count — an expired envelope is what **caused** it. Counting
it would silence the hook on precisely the case it exists for.

The only quiet disposition besides those two is *"that was a false positive of the guard's
patterns"*, which the hook explicitly invites. **A backstop that forces a bogus packet is worse
than none.** See `docs/contracts/escalation.md`.

## Hook

PreToolUse, matcher `Bash` → `.claude/scripts/tessera-spend-guard.sh` → `scripts/spend/guard.py`.
Exit 0 = allow, exit 2 = block with stderr fed to the model.

**The wrapper fails OPEN** (no `jq`, no `python3`, guard missing, bad cwd) — a hook that wedges
every Bash call is its own outage, and layer 3 bounds the damage. **`guard.py` itself fails
CLOSED**: if it runs at all, no readable grant means no spend. That split is deliberate; it is
the only place in Tessera where an unreadable file must not be shrugged off.

On deny, the model is told both paths: ask for an envelope if a human is present, raise a
`spend_unauthorized` escalation packet if not — **and explicitly not to route around it.**
