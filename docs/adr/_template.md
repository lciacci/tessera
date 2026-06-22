# ADR-NNNN: <Title>

- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Watching | Superseded by ADR-NNNN | Deprecated
- **Decision driver:** <What prompted this evaluation? Cadence review / new tool surfaced / trigger fired / project decision>

> **If Status is "Watching":**
> **Watching for:** <Specific condition that would close this — e.g., "v2.0 release that introduces extensions", "stars cross 6k", "compliance layer announced">
> **Next check:** YYYY-MM-DD (default: 60 days from this ADR's date for Watching status)

---

## Target

- **Name:** <Project or pattern name>
- **URL:** <Repo URL, docs URL, or N/A for a pattern-only eval>
- **What it is:** <One sentence>

---

## Side-by-side summary

Quick-reference table. Fill in honestly — this is the section you will scan in 6 months when context has faded.

| Dimension | Tessera | <Target> |
|---|---|---|
| Maturity | Solo, in design phase | <eval> |
| Cross-runtime | Claude Code only, design-aware | <eval> |
| Original IP | Healthcare profile, project profiles, override mechanism, audit log | <eval> |
| Maintenance model | Solo | <eval> |
| License | <current> | <eval> |
| Community size | Single user (Lorenzo) | <stars, forks, recent activity> |
| Primary problem solved | <T framing> | <their framing> |
| Distinct strength | <what T does they do not> | <what they do T does not> |

---

## 1. Identity & maturity

<One paragraph: stars, releases, last activity, maintainer model, funding, license, bias risk, recent direction.>

---

## 2. Problem-space overlap

Fill the matrix — one row per overlap area worth discussing. Classification key:

- **Compatible:** both approaches could coexist without conflict
- **Conflicting:** choosing one means rejecting the other's approach
- **Different bet:** both are plausible answers to the same question; difference is taste, tradeoff, or specific design choice

| Overlap area | Tessera approach | Their approach | Classification | Notes |
|---|---|---|---|---|
|  |  |  |  |  |

**Tessera does not address (gaps in our design they fill):**
-

**They do not address (gaps in their design we fill):**
-

---

## 3. Integration cost

**Adopt fully (replace Tessera with it):**
- Switching cost:
- What is lost (original IP, design work):
- What is gained:

**Adopt patterns (steal ideas, keep Tessera):**
- Which patterns:
- Implementation effort:

**Hybridize (run alongside):**
- Coexistence cleanliness:
- Conflict points:

**Continue without (maintain own forever):**
- Implicit maintenance burden:
- Gaps that remain:

---

## 4. Pattern-level vs implementation-level

For each interesting pattern from section 2:

| Pattern | Idea-only / Impl-too / Skip | Notes |
|---|---|---|
|  |  |  |

---

## 5. Lock-in & maintenance

**If we adopt:**
- What depends on their continued maintenance:
- Exit story if they pivot or sunset:

**If we do not adopt:**
- Cost of maintaining the equivalent ourselves:
- Lock-in risk to our own design:

---

## 6. Decision

**Verdict:** Adopt fully | Adopt patterns | Watching | Reject

**Reasoning:**
<2-3 paragraphs of honest reasoning. Name any bias you noticed in yourself during the eval. Be specific about what tipped the decision.>

**Concepts adopted (with implementation notes):**
-

**Concepts considered and rejected (with reasoning):**
-

**Re-evaluate trigger conditions:**
- <Specific condition>
- <Specific condition>
- Next cadence review: YYYY-MM-DD (default: 90 days from today for Accepted; 60 days for Watching)

---

## References

- <Links to docs, blog posts, commits, or prior ADRs that informed this evaluation>
