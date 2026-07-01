# Architecture Decision Records

Tessera uses ADRs to document substantive decisions about its design, what it adopts from the outside world, and what it deliberately rejects. Each ADR is a record of what we decided, when, and why — the trail of reasoning that future-you (or anyone else maintaining Tessera) can follow back when context has faded.

## Convention

- Each ADR is a markdown file in this directory named NNNN-<slug>.md
- Numbers are sequential and never reused (even if an ADR is deprecated)
- ADRs follow the template at _template.md
- **Once accepted, ADRs are not edited.** If a decision changes, write a new ADR that supersedes the prior one. The original stays as historical record.

## When to write an ADR

- An evaluation of an external framework, library, or pattern (via the framework-evaluation skill)
- A substantive design decision that affects Tessera architecture
- A reversal or refinement of a prior ADR (which becomes a new numbered ADR)

## When not to write an ADR

- Day-to-day implementation choices
- Decisions about a specific project being built with Tessera (those belong in that project's docs)
- Minor refinements to skills or rules (those go in commit messages)

## Index

Auto-generated below as ADRs are created. Update when adding a new ADR.

| # | Date | Title | Status |
|---|------|-------|--------|
| _template | - | ADR template (do not assign a number) | Reference |
| 0001 | 2026-06-22 | GSD evaluation | Accepted |
| 0002 | 2026-06-26 | Model effort-tier routing via dispatch-time hooks | Accepted |
| 0003 | 2026-06-26 | Tessera owns its distribution; maggy depends on Tessera | Accepted |
| 0004 | 2026-06-30 | Per-project hook distribution — global default, freeze for ship-critical | Accepted |

---

## Related

- **Principle #16 (Evaluate the ecosystem on a cadence; document the verdict)** — establishes the ADR practice as a framework discipline
- **skills/framework-evaluation** — the methodology that produces evaluation ADRs
- **/evaluate-framework** — the slash command that invokes the methodology
