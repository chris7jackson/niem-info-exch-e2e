# GitHub Issue Templates Guide

This guide explains how to use the project-agnostic GitHub issue templates to effectively create, organize, and manage issues.

## Table of Contents

- [Quick Start](#quick-start)
- [Available Templates](#available-templates)
- [Template Selection Guide](#template-selection-guide)
- [Customizing Templates](#customizing-templates)
- [Best Practices](#best-practices)
- [Template Sections Explained](#template-sections-explained)
- [FAQ](#faq)

## Quick Start

### Creating an Issue

1. Go to the **Issues** tab in your GitHub repository
2. Click **New Issue**
3. Select the appropriate template from the list
4. Fill in the template sections
5. Add relevant labels (templates include default labels)
6. Click **Submit new issue**

### Template Chooser

When you click "New Issue", you'll see a template chooser interface that groups templates by category:

- **Core Templates**: Bug reports, features, enhancements, documentation
- **Technical Templates**: Security, performance, technical debt, testing
- **Infrastructure Templates**: Infrastructure changes, dependencies, configuration

## Available Templates

### Core Templates

#### 1. Bug Report
**Use when:** Something isn't working correctly

**Key sections:**
- Bug description and severity
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Screenshots/logs

**Best for:**
- Application errors
- Incorrect functionality
- Crashes or hangs
- UI/UX bugs

**Labels:** `bug`, `needs-triage`

---

#### 2. Feature Request
**Use when:** Proposing entirely new functionality

**Key sections:**
- Feature description
- User value and user stories
- Proposed solution
- Alternatives considered
- Design considerations

**Best for:**
- New capabilities
- New API endpoints
- New user-facing features
- Major additions to functionality

**Labels:** `feature`, `needs-triage`

---

#### 3. Enhancement
**Use when:** Improving existing functionality

**Key sections:**
- What to improve
- Current vs proposed behavior
- User value and benefits
- Performance impact
- Breaking changes consideration

**Best for:**
- Making existing features better
- Improving performance
- Adding options to existing features
- Improving usability

**Labels:** `enhancement`, `needs-triage`

---

#### 4. Documentation
**Use when:** Documentation needs improvement

**Key sections:**
- Type of doc issue (missing, incorrect, unclear)
- Affected documentation
- Current vs desired state
- Audience and documentation type

**Best for:**
- Missing docs
- Outdated docs
- Confusing explanations
- New guides or tutorials

**Labels:** `documentation`, `needs-triage`

---

### Technical Templates

#### 5. Security Issue
**Use when:** Addressing security vulnerabilities or hardening

**Key sections:**
- Vulnerability description
- Severity assessment (CVE, CVSS)
- Impact analysis
- Proposed fix
- Compliance considerations

**Best for:**
- Security vulnerabilities
- Security hardening
- Compliance requirements
- Dependency security updates

**Labels:** `security`, `needs-triage`

**⚠️ Important:** For critical vulnerabilities, use [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories) instead of public issues.

---

#### 6. Performance Optimization
**Use when:** Improving speed, throughput, or resource usage

**Key sections:**
- Current performance metrics
- Target performance
- Root cause analysis
- Benchmarking plan
- Before/after comparison

**Best for:**
- Slow response times
- High resource usage
- Scalability issues
- Database query optimization
- Memory leaks

**Labels:** `performance`, `needs-triage`

---

#### 7. Technical Debt
**Use when:** Refactoring or improving code quality

**Key sections:**
- Code quality issues
- Impact on development
- Proposed refactoring
- Benefits and risks
- Implementation plan

**Best for:**
- Code refactoring
- Removing duplication
- Improving architecture
- Fixing workarounds
- Updating patterns

**Labels:** `refactor`, `needs-triage`

---

#### 8. Testing Improvement
**Use when:** Improving test coverage or test infrastructure

**Key sections:**
- Current test coverage
- Testing gaps
- Proposed improvements
- Test implementation plan
- Flaky test strategy

**Best for:**
- Adding missing tests
- Fixing flaky tests
- Test infrastructure improvements
- Performance/load testing
- E2E test gaps

**Labels:** `testing`, `needs-triage`

---

### Infrastructure Templates

#### 9. Infrastructure Change
**Use when:** Making DevOps, CI/CD, or infrastructure changes

**Key sections:**
- Type of infrastructure change
- Current vs desired state
- Technical design
- Implementation and migration plan
- Operational considerations

**Best for:**
- CI/CD pipeline changes
- Cloud infrastructure
- Containerization
- Monitoring and logging
- Deployment process

**Labels:** `infrastructure`, `needs-triage`

---

#### 10. Dependency Update
**Use when:** Updating libraries, packages, or frameworks

**Key sections:**
- Dependency details (current/target version)
- Reason for update
- Breaking changes
- Compatibility assessment
- Testing strategy

**Best for:**
- Package updates
- Security patches
- Version upgrades
- Runtime updates

**Labels:** `dependencies`, `needs-triage`

---

#### 11. Configuration Change
**Use when:** Modifying application configuration or settings

**Key sections:**
- Type of configuration
- Current vs proposed config
- Impact analysis
- Environment considerations
- Security considerations

**Best for:**
- Environment variables
- Config file changes
- Feature flags
- Build configuration
- Runtime settings

**Labels:** `configuration`, `needs-triage`

---

## Template Selection Guide

Use this decision tree to choose the right template:

```
Is something broken or not working?
├─ Yes → BUG REPORT
└─ No
   ├─ Do you want to add something new?
   │  ├─ Yes, entirely new functionality → FEATURE REQUEST
   │  └─ No, improve existing feature → ENHANCEMENT
   │
   ├─ Is it about documentation?
   │  └─ Yes → DOCUMENTATION
   │
   ├─ Is it security-related?
   │  └─ Yes → SECURITY ISSUE
   │
   ├─ Is it about performance?
   │  └─ Yes → PERFORMANCE OPTIMIZATION
   │
   ├─ Is it about code quality/refactoring?
   │  └─ Yes → TECHNICAL DEBT
   │
   ├─ Is it about testing?
   │  └─ Yes → TESTING IMPROVEMENT
   │
   ├─ Is it infrastructure/DevOps?
   │  └─ Yes → INFRASTRUCTURE CHANGE
   │
   ├─ Is it a dependency update?
   │  └─ Yes → DEPENDENCY UPDATE
   │
   └─ Is it a configuration change?
      └─ Yes → CONFIGURATION CHANGE
```

### Common Scenarios

| Scenario | Template to Use |
|----------|----------------|
| Application crashes on startup | Bug Report |
| Want to add OAuth login | Feature Request |
| Make search results load faster | Performance Optimization |
| API documentation is outdated | Documentation |
| Update React from v17 to v18 | Dependency Update |
| Replace nested loops with hashmap | Technical Debt |
| Add tests for authentication module | Testing Improvement |
| Set up GitHub Actions CI | Infrastructure Change |
| Enable HTTPS for production | Configuration Change |
| CVE found in dependency | Security Issue |

## Customizing Templates

### For Your Repository

1. **Update placeholder text:**
   - Replace `[BUG]`, `[FEATURE]`, etc. with your project-specific prefixes
   - Update repository URLs in `config.yml`
   - Customize contact links

2. **Add project-specific sections:**
   ```markdown
   ## Project-Specific Section

   **Your custom field:**
   <!-- Project-specific guidance -->
   ```

3. **Adjust labels:**
   - Modify default labels in template front matter
   - See [LABELS.md](./LABELS.md) for label taxonomy

4. **Add custom templates:**
   - Copy structure from existing templates
   - Add to `.github/ISSUE_TEMPLATE/`
   - Use YAML front matter format

### Template Front Matter

Each template starts with YAML front matter:

```yaml
---
name: Template Name                    # Displayed in template chooser
about: Short description               # Shown under template name
title: '[PREFIX] '                     # Default issue title prefix
labels: label1, label2, label3         # Auto-applied labels
assignees: ''                          # Auto-assign (optional)
---
```

## Best Practices

### For Issue Creators

1. **Choose the right template**: Use the decision tree above
2. **Fill in all sections**: Don't leave required sections blank
3. **Be specific**: Provide concrete examples, not vague descriptions
4. **Include evidence**: Screenshots, logs, error messages
5. **Check for duplicates**: Search existing issues first
6. **Use proper formatting**: Code blocks, lists, emphasis
7. **Add labels**: Apply appropriate labels from [LABELS.md](./LABELS.md)
8. **Link related issues**: Reference related issues with `#123`

### For Issue Reviewers/Maintainers

1. **Triage promptly**: Review new issues within 48 hours
2. **Add missing information**: Request clarification if needed
3. **Apply labels**: Ensure proper labeling (type, priority, effort)
4. **Set priority**: Assess urgency and importance
5. **Estimate effort**: Add effort labels for planning
6. **Update status**: Keep status labels current
7. **Close gracefully**: Explain why if closing without action

### Writing Effective Issue Titles

**Good titles:**
- ✅ "Login button throws 500 error when email is invalid"
- ✅ "Add dark mode toggle to user settings"
- ✅ "Optimize database queries in user dashboard (5s → <1s)"
- ✅ "Update Django from 3.2 to 4.2"

**Poor titles:**
- ❌ "Bug"
- ❌ "Feature request"
- ❌ "Problem"
- ❌ "Help needed"

**Title formula:**
```
[Action/Problem] [specific component/feature] [context/outcome]
```

## Template Sections Explained

### Problem/Description Section
**Purpose:** Clearly articulate what needs to be done and why

**Tips:**
- Start with a concise summary (1-2 sentences)
- Explain context and background
- Use bullet points for clarity
- Include concrete examples

### User Value Section
**Purpose:** Explain the impact and benefits

**Tips:**
- Answer "Why does this matter?"
- Quantify impact when possible ("saves 2 hours/week")
- Identify affected users
- Connect to business goals

### Acceptance Criteria Section
**Purpose:** Define "done" with measurable outcomes

**Tips:**
- Use checkboxes (`- [ ]`) for trackability
- Be specific and testable
- Include functional and non-functional requirements
- Cover edge cases and error handling

### Technical Context Section
**Purpose:** Provide implementation guidance

**Tips:**
- Suggest affected files/components
- Note dependencies or blockers
- Include code examples if helpful
- Link to relevant documentation

### Priority Section
**Purpose:** Communicate urgency and importance

**Options:** Critical | High | Medium | Low

**Guidelines:**
- **Critical:** Production down, data loss, security breach
- **High:** Major bug, important feature, significant impact
- **Medium:** Standard features, improvements
- **Low:** Nice to have, minor issues

See [LABELS.md](./LABELS.md) for detailed priority guidelines.

### Estimated Effort Section
**Purpose:** Help with planning and resource allocation

**T-shirt sizing:**
- **XS** (<2h): Trivial fixes, typos
- **S** (2-4h): Simple bugs, minor features
- **M** (4-8h): Standard features, moderate fixes
- **L** (8-16h): Complex features, significant work
- **XL** (16-32h): Major features, large refactors
- **XXL** (32h+): Epic-level work, consider breaking down

**Tips:**
- Include design, implementation, testing, and documentation
- When uncertain, estimate higher
- Consider dependencies and unknowns

## FAQ

### General

**Q: Do I have to use a template?**
A: Templates are strongly encouraged for consistency and completeness. If none fit, use a blank issue but include key information (problem, impact, proposed solution).

**Q: Can I modify a template for my specific issue?**
A: Yes! Templates are starting points. Add/remove sections as needed for your context.

**Q: What if my issue fits multiple templates?**
A: Choose the primary type. For example, a security vulnerability that also requires a dependency update should use the Security Issue template and mention the dependency update in the solution.

**Q: How do I suggest improvements to templates?**
A: Create an issue using the Enhancement template and describe the proposed template improvements.

### Technical

**Q: How do I add a new custom template?**
A: Create a new `.md` file in `.github/ISSUE_TEMPLATE/` with appropriate YAML front matter. See [GitHub's documentation](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository).

**Q: Can I have both templates and blank issues?**
A: Yes, control this with `blank_issues_enabled` in `config.yml`.

**Q: How do templates work with automation?**
A: Templates apply labels automatically. Combine with GitHub Actions for advanced automation (auto-assign, notifications, etc.).

### Workflow

**Q: When should I update the priority or effort labels?**
A: Update during triage, planning, or when circumstances change. Document changes in comments.

**Q: What if an issue is blocked?**
A: Add the `blocked` label and reference the blocking issue with `Blocked by #123`.

**Q: How do I handle duplicate issues?**
A: Comment with "Duplicate of #123", add `duplicate` label, and close. GitHub will link them automatically.

**Q: Should I close issues that won't be fixed?**
A: Yes, with explanation. Use `wontfix` label and explain reasoning (out of scope, design decision, etc.).

## Advanced Usage

### Issue Templates with GitHub Actions

Automate workflows based on templates:

```yaml
# .github/workflows/label-issues.yml
name: Label Issues
on:
  issues:
    types: [opened]

jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - name: Auto-assign based on labels
        if: contains(github.event.issue.labels.*.name, 'security')
        uses: actions-ecosystem/action-add-assignees@v1
        with:
          assignees: security-team
```

### Issue Forms (Alternative to Markdown Templates)

GitHub also supports [issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) (YAML-based) with dropdowns, checkboxes, and validation:

```yaml
# .github/ISSUE_TEMPLATE/bug-report.yml
name: Bug Report
description: File a bug report
body:
  - type: dropdown
    id: severity
    attributes:
      label: Severity
      options:
        - Critical
        - High
        - Medium
        - Low
    validations:
      required: true
```

### Template Variables

Use template variables for dynamic content:

- `{{ author }}` - Issue creator's username
- `{{ repo }}` - Repository name
- `{{ date }}` - Current date

(Note: Requires GitHub Actions or external tooling)

## Related Resources

- [LABELS.md](./LABELS.md) - Comprehensive label guide
- [GitHub Issue Templates Documentation](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)
- [GitHub Issue Forms Syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- [GitHub Actions for Issues](https://github.com/actions/labeler)

## Template Maintenance

### Regular Review

Review templates quarterly:
- Are all templates being used?
- Do templates reflect current processes?
- Are sections clear and helpful?
- Do labels align with template usage?

### Gathering Feedback

- Ask contributors what's working/not working
- Analyze which sections are often left blank
- Monitor issues created without templates

### Version Control

Track template changes in CHANGELOG:

```markdown
## 2024-01-15
- Added "Security Considerations" section to Configuration template
- Updated effort estimation guidelines
- Added "Migration Strategy" to Infrastructure template
```

---

**Questions or suggestions?** Open an issue using the Enhancement template!

**Happy issue tracking! 🎯**
