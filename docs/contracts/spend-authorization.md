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

## Self-authorization is refused — enforced, not requested *(ADR-0016, 2026-07-27)*

**That last sentence used to be the only thing stopping self-authorization.** Driving the real
hook with `bin/tessera-authorize grant …` returned **rc=0, allow**. There is no tty check, and
`granted_by` is `os.environ["USER"]` — the same value whichever party typed it. The
deny-by-default control on external spend had an authorization verb the agent could invoke on
itself, held back by prose. That is principle #17 on the highest-stakes gate in the repo.

The `grant` and `dismiss` verbs are now on the guard's deny list and are refused
**unconditionally** — including while an envelope is live, since otherwise a live envelope
would let the agent grant itself a bigger or longer one. This is a distinct policy branch, not
a `COMMITTING` pattern, for exactly that reason.

**Enforcement is structural.** PreToolUse fires on the *agent's* Bash calls only; a human in
their own terminal never passes through this hook, so the human path is untouched. `show` and
`revoke` are deliberately **not** blocked — `revoke` reduces authorization, and a spend gate
must never be able to block the exit.

**Known ceiling, inherited:** the pattern matches command text, so a runtime-assembled
invocation slips past, as it does for every other pattern here. It stops the mistake, which is
what this guard is for.

**That sentence was read as covering more than it did, and the gap was live for one day
(2026-07-27).** `bin/tessera-verify`, working on an unrelated claim, found `python3
bin/tessera-authorize grant` returned **ALLOW** — and so did `.venv/bin/python …`, `env …`,
`command …`, and `uv run …`. Five bypasses of a control this document called "refused
unconditionally", every one a plain static literal you could type by hand. **A runtime-assembled
invocation is a ceiling; a statically-visible one is a hole, and the paragraph above made the
second look like the first.** `INVOKED_SCRIPT` already carried the interpreter group
`SELF_AUTHORIZING` was missing — two patterns in one file, one of them right, and nothing
compared them. Fixed by adding a bounded launcher group; regression-tested in both directions
(`test_an_interpreter_prefix_does_not_launder_self_authorization`,
`test_the_launcher_group_does_not_block_ordinary_interpreter_calls`).

**Still open, and the enumeration is now MEASURED to be a treadmill.** Immediately after the five
forms above were closed, seven more were probed and every one passed: `script -q /dev/null …`,
`stdbuf -o0 …`, `nohup …`, `time …`, `nice …`, `xargs -I{} …`, and `script … python3 …`. The
launcher set is every exec-wrapper on the system; it cannot be enumerated. Stacking 4+ launchers
also exceeds the `{0,3}` bound.

**Do not read this as "evasion only, therefore fine."** `time`, `nohup` and `nice` are typed by
habit, not by an adversary — so the enumeration does not fully cover even the *mistake* case this
guard is scoped to. The honest status is: five common forms closed, an unbounded tail open.

**The tradeoff is now stated precisely, and it is the design gate, not a patch.** Two directions,
both with measured costs:

| direction | catches | breaks |
|---|---|---|
| **enumerate launchers** (today) | the forms on the list | nothing — but the tail is unbounded |
| **match the verb anywhere in quote-stripped text** | every launcher, no list | writing about the guard inside a wrapper-led heredoc — the documented false positive that hit 4× in one session |

Quoted prose (`git commit -m "… tessera-authorize grant …"`) survives *both*, because quotes are
stripped before the check. The casualty of direction 2 is specifically a `python3 - <<'PY'`
heredoc whose body discusses the verb — i.e. maintaining this contract. See `docs/observatory.md`
→ "The spend guard matches command TEXT". **ADR-0006's tier ranking is the tiebreaker: both
directions are tier 4, so neither is the answer — the question is whether a tier-1 or tier-2 form
exists.** `isatty()` is not it: the agent allocates a pty with `script -q /dev/null` or
`pty.spawn`, both verified 2026-07-27.

**A false positive it caused immediately, and the fix:** the first version matched the verb
*anywhere* in the command, and blocked the very commit documenting this feature — a
`python3 - <<PY` heredoc is wrapper-led, so its body is code and nothing is stripped. It now
matches only in **command position** (optionally behind `bash -c "`), because naming is not
invoking. A guard that blocks writing about itself is one people learn to route around.

## Dismissing a false positive

The backstop's report invites *"if the denial was a FALSE POSITIVE, say so plainly and finish —
that is a legitimate disposition"*, and until 2026-07-27 nothing could hear it: `undispositioned()`
cleared only on a grant-after-denial or an escalation packet, so the hook re-fired every Stop.
Both of those exits are wrong for a false positive — a grant authorizes spend nobody requested,
a packet manufactures the bogus escalation this contract calls worse than none.

```bash
tessera-authorize dismiss --reason "pytest fixture; no spend was attempted"
```

Writes a `spend_dismissed` **event**, never the envelope: a dismissal authorizes nothing, has no
TTL, and cannot boot anything. Honoured when recorded **after** the last denial — the same rule
as a grant, since a dismissal logged earlier says nothing about a later denial.

**A human runs it**, by construction. If you are the agent and a denial was a false positive,
say so in your final message and let the human decide.

**FIRST REAL RUN: 2026-07-27, and the human path is now tested end to end.** ADR-0016 named three
open triggers on this verb; all three are answered:

- **`spend_dismissed` is off n=0.** Event written with `dismissed_by: lorenzociacci` — the field
  is correct, and it is the one thing separating this from a grant.
- **The backstop went silent, and silent for the RIGHT REASON.** `rc=0`, no stderr.
- **Blocking the agent did not break the human.** One `!`-prefixed command, no friction.

**The prose exit had already been shown insufficient in the same session**, which is the ADR's
premise confirmed on live data rather than argued: the agent dispositioned the same two denials in
its final message exactly as the paragraph above instructs, and the hook re-fired at the next Stop,
because nothing can hear prose.

> **The fire counter is the discriminator, and this was nearly missed.** A dispositioned backstop
> and an *exhausted* one both present as `rc=0` with no output. They are distinguishable, but only
> by a side effect: `main()` returns before `_bump_fires()` when `undispositioned()` is empty, so a
> genuine dismissal leaves the counter UNCHANGED (2 → 2) while a cap-exhausted one increments
> (2 → 3). Checking `rc` alone cannot tell a working control from a dead one — the same
> ordinary-looking success this repo keeps paying for. **Read `.tessera/.spend-backstop-fires`, not
> just the exit code.**

**Escalation packets must now be spend-shaped to clear a denial.** `_escalated()` used to accept
any packet at all; a session raising an unrelated escalation silenced its own spend backstop by
accident. A denial is answered by a packet *about* the denial.

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
