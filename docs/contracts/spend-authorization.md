# Contract: external-spend authorization — RETIRED

**Status:** **RETIRED 2026-08-18 by ADR-0029. NOT canonical. Nothing conforms to this.**
The mechanism it specifies — the in-band, pre-execution spend guard, its backstop, and
`tessera-authorize` — was deleted. **Every command, hook path and module named below is gone.**

> **DO NOT FOLLOW THE INSTRUCTIONS IN THIS FILE.** It is kept as a *design record*, not a
> specification: ADR-0029's harvest is a summary, and whoever builds the tier-1 replacement
> (a scoped credential with a TTL, rather than permission to pass a regex) wants the full
> reasoning — the three-layer taxonomy, the never-block-the-exit invariant, the measured
> ceilings, and the failure modes. That is why it survives the cut instead of being deleted.
>
> **conclave is unaffected** and keeps its own copy of the mechanism.
>
> The file is listed in `doccheck.HISTORY_DOCS`, which suppresses `referenced-paths-exist`
> on the dead paths it names. **That suppression is only honest while this banner is here** —
> without it the file reads as authoritative AND is unverifiable, which is strictly worse than
> either alone. Found in review, 2026-08-18, having been introduced by the retirement itself.

*Everything below this line describes the mechanism as it stood before removal.*

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
> than the CLI. Layer 3 is what bounds the misses.
>
> **SCOPE FROZEN 2026-08-18 (ADR-0028), and the freeze is deliberately partial.** "A miss is a
> finding about the list, and the fix is a pattern plus a regression test" was true of one half
> and false of the other, and the single phrase "the pattern list" hid the difference:
>
> - **The evasion / launcher enumeration is FROZEN.** Measured: five forms closed on
>   2026-07-27, seven more (`script`, `stdbuf`, `nohup`, `time`, `nice`, `xargs`, `script …
>   python3 …`) passed immediately. The launcher set is every exec-wrapper on the system; it
>   cannot terminate, and each addition makes this control look more complete than it is. New
>   forms are recorded as ceilings here, **not patched.**
> - **The `COMMITTING` boot verbs are NOT frozen.** The covered class must stay *enumerable* —
>   that is the whole condition under which "this guard does not cover X" is a ceiling rather
>   than a hole. A genuinely new provisioning verb is a member of the class this guard claims,
>   and is still a bug with a pattern and a regression test.
> - **Tokenisation is FROZEN as of ADR-0028** — not for lack of a defect, but because three
>   attempts to fix it produced two block→allow regressions. Reopens only with a real shell
>   parser; the pinned ceilings are its acceptance tests.
> - **Other correctness fixes are NOT frozen.** Freezing a list is not freezing the code.
>
> **Layer 1's scope is: stop an agent that commits spend by mistake or without authorization.**
> It is not a control that defeats an agent trying to evade it. If more safety is wanted, buy
> it at **layer 3**, not by lengthening a regex.

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

**THE SPLIT IS NOT QUOTE-AWARE, AND THAT IS NOW A DECIDED CEILING (2026-08-18, ADR-0028).**
`_segments()` splits the RAW command, so a quoted span containing `|`, `;` or a newline is
torn into fragments with **unbalanced quotes** — which `QUOTED` cannot match — and the text
inside reaches `COMMITTING`. `grep -E "terraform apply|aws ec2 run-instances" notes.txt` is
denied as a GPU boot. **Five denials in one session, a 100% false-positive rate, and one
blocking escalation about being unable to disposition them.**

**A fix was written and reverted after three review rounds, because every version of it made
the guard less safe.** Round 1's quote-aware split stopped catching a wrapper after a
separator — the naive tear had been catching it *by accident*. Round 2's per-segment
`WRAPPER` test added three new false positives, including denying a heredoc that merely
documents this contract. Round 3 found the one that ended it: a quote-aware splitter will not
split while a quote is open, so an ordinary **apostrophe** swallows the rest of the command,
and because `REDUCING` is checked first, any teardown token in the swallowed span classifies
the whole thing `reducing` — **allowed unconditionally**:

```
echo don't run terraform destroy || terraform apply      ALLOWED
```

All four in-repo suites stayed green through both fail-opens; each was found only by an
independent reviewer diffing classifications against the original. Correct tokenisation needs
a real shell parser, and `shlex.split` already raises `No closing quotation` on a live file
here. **So the false positive stays: it is the safe direction, it never allows spend, and a
human `dismiss` disposes it.** The ceilings — including the third class catalogued that
session, where `INVOKED_SCRIPT` reads a probe file and denies it for the strings it merely
lists — are pinned in `scripts/spend/test_segments_known_ceilings.py`.

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

### Metered API spend is OUT OF SCOPE — deliberately, decided 2026-07-29

`COMMITTING` is three literals: `terraform apply` and two `aws ec2` provisioning forms. This
guard covers **cloud infrastructure provisioning**. It has no concept of a metered per-call API
charge, so an agent running `arbiter`, or any tool billing per token, is **not** gated and needs
no envelope.

**This is a decision, not an oversight, and the distinction is the reason it is written here.**
Found 2026-07-29 when a session ran `arbiter --base main` — $1.48, 35 model calls — through the
real PreToolUse hook and was allowed. The working belief at the time was that arbiter had been
*exempted*. It never was; it was never in scope. **Those two states are indistinguishable from
outside and are not the same thing:** an exemption is a call someone made and can revisit, a
blind spot is a gap nobody chose. Naming it converts the second into the first, which is the
whole point of this section.

**The reasoning for leaving it.** Metered API spend is a different risk class from a GPU fleet:
bounded per call, self-limiting, and visible in the tool's own output (arbiter prints its token
count and cost every run). The runaway is what this guard exists to stop. Gating it would mean a
human granting an envelope before each review run — the agent structurally cannot (ADR-0016) —
which taxes the one tool whose stated positioning is being cheap to reach for.

**The cost of the decision, stated so it is not discovered later as a surprise:** the guard will
block `terraform apply` on a change that costs cents while allowing an agent to run arbiter in a
loop. Cost scales with diff size — $1.48 for 8 files here, $2.74 for 7 Python files in arbiter's
own measurements — so a large refactor is several dollars per review and nothing bounds a repeat.

**Re-evaluate when:** metered spend actually bites — an unexpected bill, a runaway loop, or any
month where API cost is noticed rather than assumed. The remedy then is a `COMMITTING` entry plus
an envelope workflow, not a rethink. Until then this stays a stated boundary and the guard stays
scoped to provisioning.

*Worded as three named literals rather than "infrastructure spend" on purpose. See
`docs/observatory.md` → "The spend guard matches command TEXT": **a ceiling is a class you
decided not to catch; a hole is a member of the class you claimed to catch, and a hedge phrased
broadly enough launders the second into the first.** "This guard does not cover API spend" is a
ceiling only while the covered set stays enumerable — if `COMMITTING` ever grows toward "spend
generally", this paragraph becomes the next place a real gap hides in plain sight.*

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
tessera-authorize dismiss --session <id> --reason "pytest fixture; no spend was attempted"
```

**`--session` IS REQUIRED FROM A HUMAN TERMINAL, and its absence made this verb inert for its
whole life (fixed 2026-08-17).** ADR-0016 made `dismiss` human-only by putting it on the guard's
deny list — correct, because PreToolUse fires only on the agent's Bash calls. But `event.emit()`
keyed on `CLAUDE_CODE_SESSION_ID`, which is set inside an *agent* session and never in a human's
terminal, so the verb was **reachable only by a human and recordable only by an agent.** It printed
`recorded — this session's spend denials are dismissed as false positives` and wrote nothing, every
time, for anyone who ran it. A disposition that marks its own homework is ADR-0015's subject, sitting
inside the control ADR-0016 built to stop dispositions riding prose. The return value is now checked
and a failed write is loud and non-zero: **a spend control may fail to record; it must never say it
recorded when it did not.** The id is the basename of the session's log in `.tessera/logs/`.

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
>
> **IT HAPPENED AGAIN, and the second instance is more instructive than the first
> (2026-08-18).** ADR-0016's human-only `dismiss` broke `emit()`'s keying, so the 08-17 fix
> added an explicit `session_id=` parameter — which takes precedence over the environment **by
> design**, and therefore walks straight past the strip above. The test that exercised it tried
> to sandbox itself with `TESSERA_SPEND_LOGS`, **a variable nothing reads** (`event.py` resolves
> `TESSERA_ROOT`), so the containment was inert and every run appended a real `spend_dismissed`
> to the production journal: **31 manufactured dispositions**, discovered only because a query
> counting them looked wrong. Standing pattern #9 inside the containment — the monkeypatch ran;
> it just set a name no consumer resolves.
>
> The strip is no longer the guarantee. **conftest now redirects `TESSERA_ROOT` to a tmp dir for
> the whole suite**, which makes the bad state unrepresentable rather than unlikely (ADR-0006
> §2). Verified by a two-stage re-plant: with both guards removed the production log is polluted
> again; with only the conftest redirect restored it is not.

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
