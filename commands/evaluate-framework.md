---
name: evaluate-framework
description: Run a structured evaluation of an external framework, library, or pattern against Tessera's design — produces an ADR
---

# /evaluate-framework

Run the framework-evaluation skill against a specific target. Produces an ADR documenting the decision and reasoning.

## Usage

/evaluate-framework <target>

Where <target> can be:
- A repository URL (e.g., https://github.com/open-gsd/gsd-core)
- A project name (e.g., GSD)
- A pattern or concept (e.g., subagent isolation for context management)
- A reference to a prior ADR (e.g., ADR-0001) to re-evaluate

## What it does

1. **Loads the framework-evaluation skill** as the methodology.
2. **Walks through the six dimensions** of the methodology with you, gathering evidence and surfacing questions.
3. **Drafts an ADR** following docs/adr/_template.md, numbered sequentially.
4. **Commits the ADR** to docs/adr/ once you confirm the content.

## Output

A new ADR file at docs/adr/<NNNN>-<slug>.md (e.g., docs/adr/0001-gsd-evaluation.md).

The ADR contains:
- Identity & maturity summary
- Problem-space overlap matrix
- Integration-cost analysis per path (adopt fully / adopt patterns / hybridize / continue without)
- Pattern-level vs implementation-level breakdown
- Lock-in and exit-cost analysis
- Decision (adopt fully / adopt patterns / watching / reject)
- Concepts to steal (with implementation notes)
- What to skip and why
- Re-evaluate trigger conditions

## When to invoke

- Periodically (e.g., quarterly) to scan the agentic-coding landscape for drift
- When a new tool, framework, or pattern enters your awareness
- When a prior ADR's re-evaluate trigger has fired
- When a new project raises the question of which tool to use

## Anti-patterns to watch for

The skill warns about several biases worth re-naming here:
- Confirmation bias (you have an instinct about which way you want it to land)
- Sunk-cost protection (the design work already done doesn't make the answer)
- Excitement bias (shiny doesn't mean better)
- Familiarity bias (your docs are clear because you wrote them)
- Single-dimension judgment (no one metric is the answer)
- Skipping the re-evaluate trigger (a decision without triggers is a decision forever)

If you notice any of these in your reasoning while running the eval, name them in the ADR section. Honesty about bias is itself part of the trail.
