---
name: Dependency Update
about: Update libraries, packages, frameworks, or runtime versions
title: '[DEPENDENCY] '
labels: dependencies, needs-triage
assignees: ''
---

## Dependency Update

**Which dependency needs to be updated?**
<!-- Package/library name and ecosystem -->
- Package: <!-- e.g., react, django, lodash -->
- Ecosystem: <!-- e.g., npm, pip, Maven, Go modules -->
- Current version: <!-- e.g., 17.0.2 -->
- Target version: <!-- e.g., 18.2.0 -->

**Type of update:**
- [ ] Major version (breaking changes expected)
- [ ] Minor version (new features, backward compatible)
- [ ] Patch version (bug fixes only)
- [ ] Security update (CVE fix)
- [ ] Runtime/language version (e.g., Node.js, Python, Java)
- [ ] Transitive dependency (dependency of a dependency)
- [ ] Development dependency (not in production)
- [ ] Multiple dependencies (batch update)

## Reason for Update

**Why update this dependency?**
- [ ] Security vulnerability (CVE)
- [ ] Bug fix we need
- [ ] New feature we want to use
- [ ] Dependency of another package we need
- [ ] End of life / No longer maintained
- [ ] Performance improvements
- [ ] Compatibility with other dependencies
- [ ] Stay current / Reduce technical debt
- [ ] Required by platform/hosting provider

**Urgency:**
- [ ] Critical - Security vulnerability actively exploited
- [ ] High - Security vulnerability, known exploits
- [ ] Medium - Bug fix, feature needed, or approaching EOL
- [ ] Low - Maintenance, nice to have

## Security Considerations

<!-- If security-related -->

**CVE Information:**
<!-- If applicable -->
- CVE ID: <!-- e.g., CVE-2024-12345 -->
- CVSS Score: <!-- e.g., 9.8 Critical -->
- Description: <!-- Brief description of vulnerability -->
- Exploit availability: <!-- Known/Public/None -->

**Security Advisory:**
<!-- Link to GitHub Security Advisory, npm advisory, or vendor security bulletin -->
-

**Affected Code:**
<!-- Does our code use the vulnerable functionality? -->
- [ ] Yes - We use the affected feature
- [ ] Maybe - Need to investigate usage
- [ ] No - Transitive dependency or unused feature
- [ ] Unknown - Needs analysis

## Breaking Changes

<!-- For major version updates -->

**Known Breaking Changes:**
<!-- List breaking changes from changelog/migration guide -->
1.
2.
3.

**Migration Guide:**
<!-- Link to official migration guide -->
-

**Impact Assessment:**
<!-- How will breaking changes affect our code? -->
- Affected files: <!-- estimate, e.g., ~25 files -->
- Code changes required: <!-- describe scope -->
- API changes: <!-- If dependency is part of public API -->

## Compatibility

**Dependency Compatibility:**
<!-- Will this update require updating other dependencies? -->
- Compatible with current dependencies: [ ] Yes [ ] No [ ] Unknown
- Requires updating: <!-- List other packages that need updates -->
  -
  -

**Runtime Compatibility:**
<!-- Will this work with our current runtime? -->
- Node.js version: <!-- e.g., requires Node 18+, we're on 16 -->
- Python version: <!-- e.g., requires Python 3.10+, we're on 3.9 -->
- Browser support: <!-- Does this drop support for browsers we target? -->

**Platform Compatibility:**
<!-- Any OS or platform-specific considerations? -->
- [ ] Cross-platform (no issues)
- [ ] Platform-specific concerns: <!-- describe -->

## Testing Strategy

**Test Plan:**
<!-- How will you verify the update is safe? -->
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Manual testing of affected features
- [ ] Performance regression testing
- [ ] Security scanning (npm audit, Snyk, etc.)

**Risk Areas:**
<!-- Which parts of the application are most at risk? -->
-

**Rollback Plan:**
<!-- How to revert if update causes issues? -->
- [ ] Simple: Revert version in package.json and redeploy
- [ ] Moderate: May require database migration rollback
- [ ] Complex: Significant changes, difficult rollback

## Acceptance Criteria

- [ ] Dependency updated to target version
- [ ] All tests passing (unit, integration, e2e)
- [ ] No new security vulnerabilities introduced
- [ ] Breaking changes addressed (if any)
- [ ] Code changes reviewed
- [ ] Documentation updated (if API changed)
- [ ] Changelog updated
- [ ] Deployed to staging and validated
- [ ] Production deployment successful

## Implementation Notes

**Update Command:**
```bash
# Commands to update dependency
# e.g., npm install package@version
# e.g., pip install package==version
```

**Files to Modify:**
<!-- List files that will change -->
- `package.json` / `requirements.txt` / `pom.xml` / `go.mod`
- <!-- Any code files needing changes -->

**Code Changes Required:**
<!-- If breaking changes, describe necessary code updates -->

**Deprecated Features:**
<!-- Are we using any deprecated features? -->
- [ ] No deprecated features in use
- [ ] Using deprecated features: <!-- list and plan to update -->

## Changelog Review

**Relevant Changes:**
<!-- Summarize important changes from dependency's changelog -->
- **New features:**
  -
- **Bug fixes:**
  -
- **Breaking changes:**
  -
- **Performance improvements:**
  -
- **Deprecations:**
  -

**Changelog Link:**
<!-- Link to dependency's changelog/release notes -->
-

## Dependencies

**Blockers:**
<!-- What must be done before this update? -->
-

**Enables:**
<!-- What will this update enable? -->
-

**Related Updates:**
<!-- Other dependencies to update at the same time? -->
-

## Additional Context

**Lock File Changes:**
<!-- Will this significantly change package-lock.json, yarn.lock, etc.? -->
- [ ] Minor changes
- [ ] Major changes (many transitive dependencies updated)

**Bundle Size Impact:**
<!-- For frontend dependencies -->
- Current bundle size: <!-- e.g., 450 KB -->
- Expected bundle size: <!-- e.g., 460 KB (+10 KB) -->

**Performance Impact:**
<!-- Expected performance changes -->
- [ ] Improvement expected
- [ ] No change expected
- [ ] Regression possible (needs benchmarking)

**Documentation:**
<!-- Documentation that needs updating -->
- [ ] README
- [ ] Installation guide
- [ ] API documentation
- [ ] Troubleshooting guide
- [ ] No documentation changes needed

## Priority

**Priority:** <!-- Critical | High | Medium | Low -->

**Justification:**
<!-- Why this priority? Consider: security, features needed, technical debt -->

## Estimated Effort

**Effort:** <!-- XS (<2h) | S (2-4h) | M (4-8h) | L (8-16h) | XL (16-32h) | XXL (>32h) -->

**Breakdown:**
- Update dependency: <!-- estimate -->
- Address breaking changes: <!-- estimate -->
- Testing: <!-- estimate -->
- Documentation: <!-- estimate -->

**Complexity:**
- [ ] Simple - Patch/minor update, no breaking changes
- [ ] Moderate - Minor breaking changes or several code updates
- [ ] Complex - Major version with significant breaking changes

---

**Automated Dependency Updates:**
<!-- If using Dependabot, Renovate, etc. -->
- [ ] This update was flagged by automated tool
- [ ] Tool: <!-- Dependabot, Renovate, Snyk -->
- [ ] PR link: <!-- If automated PR exists -->

**Additional Notes:**
<!-- Any other context or considerations -->
