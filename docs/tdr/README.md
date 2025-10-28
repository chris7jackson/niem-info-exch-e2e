# Tooling Decision Records (TDRs)

This directory contains **Tooling Decision Records** documenting significant decisions about third-party libraries, frameworks, development tools, and technology choices.

## Purpose

TDRs capture the context, rationale, and consequences of tooling choices to:
- Provide clear justification for library/framework selections
- Document trade-offs and alternatives considered
- Help future developers understand "why we chose X over Y"
- Track the evolution of the technology stack
- Facilitate security reviews and compliance audits

## When to Create a TDR

Create a TDR when:
- ✅ Adding a new third-party library or framework
- ✅ Replacing an existing library with an alternative
- ✅ Choosing between multiple viable tooling options
- ✅ Making security-related tooling decisions
- ✅ Selecting development/build/deployment tools

Do NOT create a TDR for:
- ❌ Minor version updates (document in CHANGELOG instead)
- ❌ Architectural/design patterns (use ADR instead)
- ❌ Configuration changes (use git commit messages)
- ❌ Bug fixes or patches

## TDR vs ADR

| Aspect | TDR (Tooling) | ADR (Architecture) |
|--------|---------------|-------------------|
| **Focus** | Libraries, frameworks, tools | System design, patterns, structure |
| **Examples** | "Use defusedxml for XML parsing" | "Batch processing with controlled concurrency" |
| **Impact** | Implementation details | System behavior and structure |
| **Scope** | Specific component/feature | Cross-cutting concerns |

## TDR Format

Each TDR follows this structure:

```markdown
# TDR-###: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
- Problem being solved
- Current situation
- Requirements and constraints

## Decision
- What library/tool was chosen
- How it will be used

## Consequences
### Positive
- Benefits and advantages

### Negative
- Drawbacks and trade-offs

### Mitigation
- How to address negative consequences

## Alternatives Considered
- Other options evaluated
- Why they were rejected

## Implementation Status
- Current state
- Related commits

## References
- Documentation links
- Related issues/PRs

## Date
YYYY-MM-DD

## Authors
- Who made the decision
```

## Naming Convention

TDRs are numbered sequentially: `001-descriptive-name.md`

Examples:
- `001-defusedxml-for-secure-xml-parsing.md`
- `002-vitest-for-frontend-testing.md`
- `003-playwright-for-e2e-tests.md`

## Existing TDRs

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [TDR-001](./001-defusedxml-for-secure-xml-parsing.md) | defusedxml for Secure XML Parsing | Accepted | 2025-10-27 |

## Related Documentation

- [Architecture Decision Records (ADRs)](../adr/README.md) - System design decisions
- [CI/CD Pipeline Documentation](../CI_CD_PIPELINE.md) - Build and deployment tooling
- [Development Setup](../../README.md) - Getting started with the codebase
