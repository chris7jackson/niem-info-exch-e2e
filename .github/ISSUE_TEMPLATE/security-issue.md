---
name: Security Issue
about: Report a security vulnerability or propose security hardening
title: '[SECURITY] '
labels: security, needs-triage
assignees: ''
---

<!--
⚠️ IMPORTANT: For security vulnerabilities, consider using private security advisories
instead of public issues. See: https://docs.github.com/en/code-security/security-advisories

For critical vulnerabilities:
1. DO NOT post details publicly
2. Contact maintainers privately
3. Allow time for fix before disclosure
-->

## Security Issue Type

- [ ] Vulnerability (exploitable security flaw)
- [ ] Security hardening (improvement to security posture)
- [ ] Security configuration (improve security settings)
- [ ] Dependency security (vulnerable dependency)
- [ ] Compliance (regulatory or standards requirement)

## Severity Assessment

**Severity Level:**
<!-- Use CVSS or similar framework for vulnerabilities -->
- [ ] Critical - Immediate exploitation possible, high impact (RCE, data breach)
- [ ] High - Exploitation likely, significant impact (privilege escalation, auth bypass)
- [ ] Medium - Exploitation possible with conditions, moderate impact
- [ ] Low - Limited exploitability or impact

**CVSS Score:** <!-- If applicable, e.g., 9.8 Critical -->

## Vulnerability Description

**Summary:**
<!-- High-level description of the security issue -->

**Affected Components:**
<!-- Which parts of the system are affected? -->
-

**Affected Versions:**
<!-- Which versions are vulnerable? -->
- Vulnerable: v1.x.x - v2.x.x
- Fixed in: vX.X.X (if known)

## Impact Assessment

**Potential Impact:**
<!-- What could an attacker achieve? -->
- [ ] Data breach / Information disclosure
- [ ] Unauthorized access
- [ ] Privilege escalation
- [ ] Remote code execution (RCE)
- [ ] Denial of service (DoS)
- [ ] Data tampering / Integrity loss
- [ ] Account takeover
- [ ] Cross-site scripting (XSS)
- [ ] SQL injection
- [ ] Other: ___________

**Attack Complexity:**
- [ ] Low - Easy to exploit, no special conditions
- [ ] Medium - Requires some conditions or knowledge
- [ ] High - Difficult to exploit, requires significant conditions

**User Interaction Required:**
- [ ] None - Automatic exploitation
- [ ] Limited - Minimal interaction (click link)
- [ ] Significant - Requires deliberate user action

## Reproduction / Proof of Concept

<!-- ⚠️ For public issues, provide minimal info. Full PoC should be private -->

**Environment:**
<!-- Where was this discovered? -->

**Steps to Reproduce:**
<!-- High-level steps (detailed PoC should be shared privately) -->
1.
2.
3.

**Expected Secure Behavior:**
<!-- What should happen in a secure system? -->

**Actual Behavior:**
<!-- What actually happens? -->

## Proposed Solution

**Recommended Fix:**
<!-- High-level description of the fix -->

**Mitigation Steps:**
<!-- Temporary workarounds or mitigation before fix is available -->

**Security Best Practices:**
<!-- Relevant security principles or standards -->
- OWASP Top 10
- CWE (Common Weakness Enumeration)
- NIST guidelines
- Zero Trust principles

## Compliance Considerations

**Regulatory Requirements:**
<!-- If applicable -->
- [ ] GDPR (EU data protection)
- [ ] HIPAA (healthcare data)
- [ ] PCI DSS (payment card data)
- [ ] SOC 2 (security controls)
- [ ] FedRAMP (US federal)
- [ ] Other: ___________

## Acceptance Criteria

- [ ] Vulnerability patched or security improvement implemented
- [ ] Security testing performed (penetration test, vulnerability scan)
- [ ] Code review completed with security focus
- [ ] Regression tests added to prevent reintroduction
- [ ] Security documentation updated
- [ ] Dependency updates applied (if applicable)
- [ ] Security advisory published (for vulnerabilities)
- [ ] CVE assigned (if applicable)
- [ ] Users notified through proper channels

## Technical Context

**Affected Code:**
<!-- File paths, functions, or components (can be general for public issues) -->

**Attack Vector:**
<!-- How is the vulnerability exploited? -->
- [ ] Network - Remotely exploitable
- [ ] Adjacent - Requires local network access
- [ ] Local - Requires local access
- [ ] Physical - Requires physical access

**Authentication Required:**
<!-- Does exploitation require authentication? -->
- [ ] None - No authentication needed
- [ ] Single - Requires one level of auth
- [ ] Multiple - Requires multiple auth factors

## Related Security Issues

**Dependencies:**
<!-- Related to other security issues? -->
-

**References:**
<!-- Links to CVEs, security advisories, research papers -->
-

**Similar Vulnerabilities:**
<!-- Have similar issues been found before? -->

## Priority

**Priority:** <!-- Critical | High | Medium | Low -->

**Justification:**
<!-- Why this priority? Consider: exploitability, impact, exposure -->

## Estimated Effort

**Effort:** <!-- XS (<2h) | S (2-4h) | M (4-8h) | L (8-16h) | XL (16-32h) | XXL (>32h) -->

**Complexity:**
- [ ] Simple fix (config change, version bump)
- [ ] Moderate fix (code changes, refactoring)
- [ ] Complex fix (architecture changes, significant refactoring)

**Timeline:**
<!-- For vulnerabilities, when should this be fixed? -->
- [ ] Immediate (within 24-48 hours)
- [ ] Urgent (within 1 week)
- [ ] High priority (within 2-4 weeks)
- [ ] Standard timeline

---

**Disclosure Timeline:**
<!-- For vulnerabilities -->
- Discovery date:
- Vendor notification:
- Fix target date:
- Public disclosure date:

**Reporter Notes:**
<!-- Any additional context or information -->
