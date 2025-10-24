# GitHub Labels Guide

This document defines the comprehensive label taxonomy for organizing and managing issues in this repository.

## Label Philosophy

Labels serve multiple purposes:
- **Categorization**: What type of issue is this?
- **Prioritization**: How urgent/important is this?
- **Status Tracking**: What state is this issue in?
- **Effort Estimation**: How much work is required?
- **Discovery**: Help contributors find issues to work on

## Label Categories

### 1. Type Labels (What)

Define the nature of the issue.

| Label | Color | Description | Used For |
|-------|-------|-------------|----------|
| `bug` | 🔴 `#d73a4a` | Something isn't working correctly | Bug reports, defects, errors |
| `feature` | 🟢 `#0e8a16` | New functionality or capability | New features, major additions |
| `enhancement` | 🔵 `#0075ca` | Improvement to existing feature | Enhancements, improvements |
| `documentation` | 📘 `#0075ca` | Documentation improvements | Docs updates, guides, README |
| `security` | 🔒 `#ee0701` | Security-related issue | Vulnerabilities, hardening |
| `performance` | ⚡ `#fbca04` | Performance optimization | Speed, efficiency, resource usage |
| `refactor` | 🔧 `#fbca04` | Code quality improvement | Technical debt, cleanup |
| `testing` | 🧪 `#d4c5f9` | Testing improvements | Test coverage, test infrastructure |
| `infrastructure` | 🏗️ `#006b75` | Infrastructure/DevOps | CI/CD, deployment, cloud |
| `dependencies` | 📦 `#0366d6` | Dependency updates | Library/package updates |
| `configuration` | ⚙️ `#c5def5` | Configuration changes | Config files, env vars, settings |

### 2. Priority Labels (When)

Indicate urgency and importance.

| Label | Color | Description | Response Time | Examples |
|-------|-------|-------------|---------------|----------|
| `priority:critical` | 🔥 `#b60205` | Urgent, blocking issue | Immediate (24h) | Production down, data loss, security breach |
| `priority:high` | 🟠 `#d93f0b` | Important, should be next | 1-3 days | Major bug, key feature needed soon |
| `priority:medium` | 🟡 `#fbca04` | Normal priority | 1-2 weeks | Standard features, improvements |
| `priority:low` | 🟢 `#0e8a16` | Nice to have, not urgent | When time permits | Minor enhancements, small fixes |

**Priority Decision Matrix:**

```
          │ Low Impact  │ Med Impact  │ High Impact │
──────────┼─────────────┼─────────────┼─────────────┤
Urgent    │   Medium    │     High    │   Critical  │
Soon      │    Low      │    Medium   │     High    │
Someday   │    Low      │     Low     │    Medium   │
```

### 3. Status Labels (Current State)

Track the issue lifecycle.

| Label | Color | Description | Next Action |
|-------|-------|-------------|-------------|
| `needs-triage` | 🔍 `#d4c5f9` | Needs initial review | Maintainer reviews and assigns priority |
| `needs-discussion` | 💬 `#d4c5f9` | Requires discussion/clarification | Team discusses approach |
| `blocked` | 🚫 `#d93f0b` | Blocked by another issue/dependency | Identify and resolve blocker |
| `ready` | ✅ `#0e8a16` | Ready to be worked on | Assign to developer |
| `in-progress` | 🔄 `#0075ca` | Currently being worked on | Continue development |
| `needs-review` | 👀 `#fbca04` | PR created, needs code review | Review and approve PR |
| `needs-testing` | 🧪 `#f9d0c4` | Needs QA/testing | Test in staging/production |

### 4. Effort Labels (How Much)

Estimate work required (T-shirt sizing).

| Label | Color | Description | Time Range | Complexity |
|-------|-------|-------------|------------|------------|
| `effort:xs` | `#c2e0c6` | Extra small | <2 hours | Trivial fix, typo, config change |
| `effort:s` | `#bfd4f2` | Small | 2-4 hours | Simple bug fix, minor feature |
| `effort:m` | `#fef2c0` | Medium | 4-8 hours | Standard feature, moderate fix |
| `effort:l` | `#f9d0c4` | Large | 8-16 hours | Complex feature, significant refactor |
| `effort:xl` | `#d4c5f9` | Extra large | 16-32 hours | Major feature, architecture change |
| `effort:xxl` | `#e99695` | Extra extra large | 32+ hours | Epic-level work, requires planning |

**Effort Estimation Guidelines:**
- Include design, implementation, testing, and documentation time
- Consider: familiarity with codebase, technical complexity, dependencies
- When in doubt, estimate higher
- Use `effort:xl` and `effort:xxl` sparingly; consider breaking into smaller issues

### 5. Contributor Labels (Who)

Help contributors find suitable issues.

| Label | Color | Description | Target Audience |
|-------|-------|-------------|-----------------|
| `good-first-issue` | 🌱 `#7057ff` | Good for newcomers | First-time contributors |
| `help-wanted` | 🙋 `#008672` | Community contributions welcome | Any contributor |
| `complex` | 🧩 `#d93f0b` | Requires deep knowledge | Experienced contributors only |

**Good First Issue Criteria:**
- Small scope (`effort:xs` or `effort:s`)
- Well-defined problem and solution
- Clear acceptance criteria
- Doesn't require deep domain knowledge
- Good documentation available

### 6. Special Labels (Meta)

Additional categorization.

| Label | Color | Description | Usage |
|-------|-------|-------------|-------|
| `breaking-change` | ⚠️ `#d93f0b` | Will break backward compatibility | Major version bump required |
| `question` | ❓ `#d876e3` | Seeking information or clarification | Convert to discussion if appropriate |
| `duplicate` | 📋 `#cfd3d7` | Duplicate of another issue | Link to original issue and close |
| `wontfix` | 🚫 `#ffffff` | Will not be fixed/implemented | Explain reasoning before closing |
| `production` | 🏭 `#b60205` | Affecting production environment | Requires immediate attention |
| `staging` | 🎭 `#fbca04` | Affecting staging environment | Test before production fix |
| `research` | 🔬 `#0075ca` | Requires investigation/research | Spike/exploration needed first |

## Label Usage Guidelines

### Applying Labels

**Required Labels (every issue should have):**
1. **Type label**: One of `bug`, `feature`, `enhancement`, etc.
2. **Priority label**: One of `priority:critical`, `priority:high`, `priority:medium`, `priority:low`
3. **Status label**: Start with `needs-triage`, progress through lifecycle

**Optional Labels:**
- **Effort label**: Add when effort can be estimated
- **Contributor label**: Add `good-first-issue` or `help-wanted` when appropriate
- **Special labels**: Add `breaking-change`, `production`, etc. as needed

### Label Combinations Examples

**Critical Production Bug:**
```
bug + priority:critical + production + needs-triage
→ priority:critical + in-progress + effort:s
→ priority:critical + needs-review
```

**Good First Issue Feature:**
```
feature + priority:low + good-first-issue + help-wanted + effort:s + needs-triage
→ priority:low + ready
```

**Complex Enhancement:**
```
enhancement + priority:medium + complex + effort:xl + needs-discussion
→ priority:medium + ready + effort:xl
→ priority:medium + in-progress + effort:xl
```

## Workflow Examples

### Bug Report Workflow
1. User creates issue with `bug` label (auto-applied by template)
2. Maintainer triages: adds `priority:high`, removes `needs-triage`
3. Maintainer estimates: adds `effort:m`
4. Developer starts work: adds `in-progress`
5. Developer creates PR: adds `needs-review`
6. PR merged, issue closed

### Feature Request Workflow
1. User creates issue with `feature` + `needs-triage` (auto-applied)
2. Team discusses: adds `needs-discussion`
3. Approach decided: adds `priority:medium`, `effort:l`, `ready`
4. Developer picks up: adds `in-progress`
5. Blocked by another issue: adds `blocked`
6. Blocker resolved: removes `blocked`, continues `in-progress`
7. PR created and merged, issue closed

## Creating Labels

Use these commands to create labels via GitHub CLI:

```bash
# Type labels
gh label create bug --color d73a4a --description "Something isn't working correctly"
gh label create feature --color 0e8a16 --description "New functionality or capability"
gh label create enhancement --color 0075ca --description "Improvement to existing feature"
gh label create documentation --color 0075ca --description "Documentation improvements"
gh label create security --color ee0701 --description "Security-related issue"
gh label create performance --color fbca04 --description "Performance optimization"
gh label create refactor --color fbca04 --description "Code quality improvement"
gh label create testing --color d4c5f9 --description "Testing improvements"
gh label create infrastructure --color 006b75 --description "Infrastructure/DevOps"
gh label create dependencies --color 0366d6 --description "Dependency updates"
gh label create configuration --color c5def5 --description "Configuration changes"

# Priority labels
gh label create priority:critical --color b60205 --description "Urgent, blocking issue"
gh label create priority:high --color d93f0b --description "Important, should be next"
gh label create priority:medium --color fbca04 --description "Normal priority"
gh label create priority:low --color 0e8a16 --description "Nice to have, not urgent"

# Status labels
gh label create needs-triage --color d4c5f9 --description "Needs initial review"
gh label create needs-discussion --color d4c5f9 --description "Requires discussion/clarification"
gh label create blocked --color d93f0b --description "Blocked by another issue/dependency"
gh label create ready --color 0e8a16 --description "Ready to be worked on"
gh label create in-progress --color 0075ca --description "Currently being worked on"
gh label create needs-review --color fbca04 --description "PR created, needs code review"
gh label create needs-testing --color f9d0c4 --description "Needs QA/testing"

# Effort labels
gh label create effort:xs --color c2e0c6 --description "Extra small (<2h)"
gh label create effort:s --color bfd4f2 --description "Small (2-4h)"
gh label create effort:m --color fef2c0 --description "Medium (4-8h)"
gh label create effort:l --color f9d0c4 --description "Large (8-16h)"
gh label create effort:xl --color d4c5f9 --description "Extra large (16-32h)"
gh label create effort:xxl --color e99695 --description "Extra extra large (32h+)"

# Contributor labels
gh label create good-first-issue --color 7057ff --description "Good for newcomers"
gh label create help-wanted --color 008672 --description "Community contributions welcome"
gh label create complex --color d93f0b --description "Requires deep knowledge"

# Special labels
gh label create breaking-change --color d93f0b --description "Will break backward compatibility"
gh label create question --color d876e3 --description "Seeking information or clarification"
gh label create duplicate --color cfd3d7 --description "Duplicate of another issue"
gh label create wontfix --color ffffff --description "Will not be fixed/implemented"
gh label create production --color b60205 --description "Affecting production environment"
gh label create staging --color fbca04 --description "Affecting staging environment"
gh label create research --color 0075ca --description "Requires investigation/research"
```

## Bulk Label Creation Script

Save this as `create-labels.sh`:

```bash
#!/bin/bash

# Type labels
gh label create bug --color d73a4a --description "Something isn't working correctly" --force
gh label create feature --color 0e8a16 --description "New functionality or capability" --force
gh label create enhancement --color 0075ca --description "Improvement to existing feature" --force
gh label create documentation --color 0075ca --description "Documentation improvements" --force
gh label create security --color ee0701 --description "Security-related issue" --force
gh label create performance --color fbca04 --description "Performance optimization" --force
gh label create refactor --color fbca04 --description "Code quality improvement" --force
gh label create testing --color d4c5f9 --description "Testing improvements" --force
gh label create infrastructure --color 006b75 --description "Infrastructure/DevOps" --force
gh label create dependencies --color 0366d6 --description "Dependency updates" --force
gh label create configuration --color c5def5 --description "Configuration changes" --force

# Priority labels
gh label create priority:critical --color b60205 --description "Urgent, blocking issue" --force
gh label create priority:high --color d93f0b --description "Important, should be next" --force
gh label create priority:medium --color fbca04 --description "Normal priority" --force
gh label create priority:low --color 0e8a16 --description "Nice to have, not urgent" --force

# Status labels
gh label create needs-triage --color d4c5f9 --description "Needs initial review" --force
gh label create needs-discussion --color d4c5f9 --description "Requires discussion/clarification" --force
gh label create blocked --color d93f0b --description "Blocked by another issue/dependency" --force
gh label create ready --color 0e8a16 --description "Ready to be worked on" --force
gh label create in-progress --color 0075ca --description "Currently being worked on" --force
gh label create needs-review --color fbca04 --description "PR created, needs code review" --force
gh label create needs-testing --color f9d0c4 --description "Needs QA/testing" --force

# Effort labels
gh label create effort:xs --color c2e0c6 --description "Extra small (<2h)" --force
gh label create effort:s --color bfd4f2 --description "Small (2-4h)" --force
gh label create effort:m --color fef2c0 --description "Medium (4-8h)" --force
gh label create effort:l --color f9d0c4 --description "Large (8-16h)" --force
gh label create effort:xl --color d4c5f9 --description "Extra large (16-32h)" --force
gh label create effort:xxl --color e99695 --description "Extra extra large (32h+)" --force

# Contributor labels
gh label create good-first-issue --color 7057ff --description "Good for newcomers" --force
gh label create help-wanted --color 008672 --description "Community contributions welcome" --force
gh label create complex --color d93f0b --description "Requires deep knowledge" --force

# Special labels
gh label create breaking-change --color d93f0b --description "Will break backward compatibility" --force
gh label create question --color d876e3 --description "Seeking information or clarification" --force
gh label create duplicate --color cfd3d7 --description "Duplicate of another issue" --force
gh label create wontfix --color ffffff --description "Will not be fixed/implemented" --force
gh label create production --color b60205 --description "Affecting production environment" --force
gh label create staging --color fbca04 --description "Affecting staging environment" --force
gh label create research --color 0075ca --description "Requires investigation/research" --force

echo "✅ All labels created successfully!"
```

Then run:
```bash
chmod +x create-labels.sh
./create-labels.sh
```

## Label Maintenance

### Renaming Labels
```bash
gh label edit old-name --name new-name
```

### Changing Label Colors
```bash
gh label edit label-name --color new-color
```

### Deleting Labels
```bash
gh label delete label-name
```

### Bulk Operations
Use GitHub API or third-party tools like [github-label-sync](https://github.com/Financial-Times/github-label-sync) for bulk operations across multiple repositories.

## Best Practices

1. **Be Consistent**: Always use the same labels for similar issues
2. **Start Simple**: Don't feel obligated to use every label immediately
3. **Review Regularly**: Audit labels quarterly to ensure they're being used correctly
4. **Document Changes**: Update this guide when adding/removing labels
5. **Educate Team**: Ensure all team members understand the label system
6. **Use Automation**: Consider bots to auto-label based on issue content
7. **Clean Up**: Remove outdated or unused labels

## FAQ

**Q: How many labels should an issue have?**
A: Typically 2-5 labels: type + priority + status, plus optional effort/special labels.

**Q: What if priority changes?**
A: Update the label as priorities shift. Document the reason in a comment.

**Q: Should we label PRs?**
A: PRs automatically inherit labels from linked issues. Additional PR-specific labels can be useful.

**Q: How to handle issues that don't fit any category?**
A: Use `question` label and consider creating a discussion instead.

**Q: Can contributors apply labels?**
A: Depends on repository permissions. Generally, maintainers manage labels, but contributors can suggest in comments.

## Related Documentation

- [Issue Template Guide](./TEMPLATE_GUIDE.md) - How to use issue templates
- [Contributing Guide](../../CONTRIBUTING.md) - Contribution guidelines
- [GitHub Labels Documentation](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels)
