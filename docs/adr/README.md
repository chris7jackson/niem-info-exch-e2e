# Architecture Decision Records (ADR)

This directory contains Architecture Decision Records for the NIEM Information Exchange project.

## What is an ADR?

An Architecture Decision Record (ADR) documents an important architectural decision made along with its context and consequences.

## Format

Each ADR follows this structure:

```markdown
# ADR-XXX: Title

## Status
Accepted | Proposed | Deprecated | Superseded by ADR-YYY

## Context
What is the issue we're facing? What factors are at play?

## Decision
What architectural decision did we make?

## Consequences
What are the positive and negative consequences of this decision?

## Alternatives Considered
What other options did we evaluate?

## Future Considerations
What might change this decision in the future?
```

## Naming Convention

ADRs are numbered sequentially:
- `001-batch-processing-architecture.md`
- `002-authentication-strategy.md`
- etc.

## When to Create an ADR

Create an ADR for decisions that:
- ✅ Affect multiple components or the entire system
- ✅ Are difficult or expensive to reverse
- ✅ Impact performance, scalability, or security
- ✅ Establish patterns that other developers should follow
- ✅ Solve a recurring architectural problem

Don't create an ADR for:
- ❌ Implementation details of a single component
- ❌ Temporary solutions or experiments
- ❌ Technology choices that are easily reversible

## Index of ADRs

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [001](001-batch-processing-architecture.md) | Batch Processing Architecture | Accepted | 2025-10-20 |
