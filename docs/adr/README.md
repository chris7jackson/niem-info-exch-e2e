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
- ✅ Affect system structure or design patterns
- ✅ Define cross-cutting concerns (auth, logging, error handling)
- ✅ Impact performance, scalability, or security architecture
- ✅ Establish architectural patterns that others should follow
- ✅ Solve recurring architectural problems
- ✅ Define deployment or infrastructure architecture

Don't create an ADR for:
- ❌ Implementation details of a single component
- ❌ Temporary solutions or experiments
- ❌ Library/framework choices (use [TDR](../tdr/README.md) instead)
- ❌ Development tooling decisions (use [TDR](../tdr/README.md) instead)

## ADR vs TDR

**ADR (Architecture):** System design, patterns, structure
- Example: "Batch processing with controlled concurrency"

**TDR (Tooling):** Libraries, frameworks, tools
- Example: "Use defusedxml for XML parsing"

See [Tooling Decision Records](../tdr/README.md) for library and tooling choices.

## Index of ADRs

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [001](001-batch-processing-architecture.md) | Batch Processing Architecture | Accepted | 2025-10-20 |
