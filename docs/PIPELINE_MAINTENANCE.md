# Pipeline Maintenance Guide

## Overview

This guide covers routine maintenance tasks for the CI/CD pipeline, including updates, troubleshooting, and modifications.

## Regular Maintenance Tasks

### Weekly Tasks

#### 1. Review Non-Blocking Failures

Check GitHub Security tab for Trivy and CodeQL findings:

```bash
# View security alerts
gh api /repos/:owner/:repo/security-advisories

# Or visit: https://github.com/[owner]/[repo]/security
```

**Action items:**
- Review new vulnerabilities
- Document accepted risks
- Update dependencies if fixes available
- Add suppressions if false positives

#### 2. Monitor Pipeline Performance

```bash
# Check recent workflow runtimes
gh run list --workflow=pr-checks.yml --limit 10 --json conclusion,startedAt,updatedAt

# Look for trends:
# - Increasing runtimes
# - Cache miss rates
# - Frequent failures
```

**Target metrics:**
- PR checks: < 5 minutes
- Main pipeline: < 15 minutes
- Success rate: > 95%

### Monthly Tasks

#### 1. Update Dependencies

**Python (api/):**
```bash
cd api

# Check outdated packages
pip list --outdated

# Update requirements (carefully)
pip install --upgrade pip
pip install --upgrade <package>

# Test changes
pytest tests/unit/

# Update requirements.txt
pip freeze > requirements.txt
```

**Node.js (ui/):**
```bash
cd ui

# Check outdated packages
npm outdated

# Update (carefully)
npm update <package>

# Test changes
npm run test:run
npm run build

# Commit updated package-lock.json
```

**GitHub Actions:**
```yaml
# Check for action updates
# Example: actions/checkout@v4 -> @v5

# Update in workflows:
uses: actions/checkout@v5  # Updated
uses: actions/setup-python@v5  # Updated
uses: actions/setup-node@v4  # Check for v5
```

#### 2. Review and Update Security Scans

```bash
# Update Trivy
# (Automatically uses latest in workflow)

# Update bandit/ruff if needed
cd api
pip install --upgrade bandit ruff

# Test
bandit -r src/ -ll
ruff check src/
```

### Quarterly Tasks

#### 1. Dependency Audit

Run comprehensive security checks:

```bash
# Python
cd api
safety check --json > safety-report.json
cat safety-report.json | jq '.vulnerabilities'

# Node.js
cd ui
npm audit --json > npm-audit.json
cat npm-audit.json | jq '.vulnerabilities'
```

#### 2. Pipeline Review

- Review workflow efficiency
- Check for unused jobs/steps
- Validate path filters still make sense
- Review artifact retention (GitHub default: 90 days)

#### 3. Documentation Updates

- Update this file with any new procedures
- Review CI_CD_PIPELINE.md for accuracy
- Update version numbers in examples

---

## Updating Tool Versions

### Updating Python Version

**1. Update `pyproject.toml`:**
```toml
[tool.mypy]
python_version = "3.13"  # Updated

[project]
requires-python = ">=3.13"  # Updated
```

**2. Update workflows:**
```yaml
env:
  PYTHON_VERSION: '3.13'  # Updated
```

**3. Update Dockerfile:**
```dockerfile
FROM python:3.13-slim  # Updated
```

**4. Test locally:**
```bash
pyenv install 3.13
pyenv local 3.13
cd api
pip install -r requirements.txt
pytest tests/
```

**5. Update README and documentation**

### Updating Node.js Version

**1. Update workflows:**
```yaml
env:
  NODE_VERSION: '20'  # Updated from 18
```

**2. Update Dockerfile:**
```dockerfile
FROM node:20-alpine  # Updated from 20
```

**3. Test locally:**
```bash
nvm install 20
nvm use 20
cd ui
npm ci
npm run test:run
npm run build
```

**4. Update package.json engines (optional):**
```json
"engines": {
  "node": ">=20.0.0"
}
```

---

## Modifying Quality Gates

### Adding a New Check

**Example: Add pytest-benchmark for performance testing**

**1. Update requirements-test.txt:**
```
pytest-benchmark==4.0.0
```

**2. Add workflow step:**
```yaml
- name: Run performance benchmarks
  run: |
    cd api
    pytest tests/ --benchmark-only --benchmark-json=benchmark.json
  continue-on-error: true  # Non-blocking

- name: Upload benchmark results
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: performance-benchmarks
    path: api/benchmark.json
```

**3. Update documentation:**
- Add to CI_CD_PIPELINE.md
- Document in this file

### Changing Coverage Threshold

**1. Update `pyproject.toml`:**
```toml
[tool.coverage.report]
fail_under = 85.0  # Increased from 80
```

**2. Update workflow:**
```yaml
pytest tests/unit/ --cov-fail-under=85  # Increased
```

**3. Communicate to team:**
- Document reason for change
- Give time to increase coverage
- Consider gradual increase (80 -> 82 -> 85)

### Removing a Check

**1. Comment out workflow step:**
```yaml
# Temporarily disabled - reason: [explain]
# - name: Run flake8
#   run: flake8 src/
```

**2. Document in commit:**
```
chore: disable flake8 check

Reason: Migrated to ruff which covers same checks
```

**3. Update documentation**

---

## Troubleshooting Common Issues

### Cache Issues

**Problem:** Cache not restoring correctly

**Solution:**
```yaml
# Update cache key to force rebuild
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-v2-${{ hashFiles('api/requirements*.txt') }}
    #                         ^^^ Increment version
```

### Service Health Check Failures

**Problem:** Neo4j/MinIO not ready in time

**Solution 1: Increase retries**
```yaml
options: >-
  --health-retries 10  # Increased from 5
  --health-interval 5s
```

**Solution 2: Add explicit wait**
```yaml
- name: Wait for services
  run: |
    timeout 120 bash -c 'until curl -f http://localhost:9000/minio/health/live; do sleep 5; done'
```

### Path Filters Not Working

**Problem:** Jobs running when they shouldn't

**Debug:**
```yaml
# Add debug output
- name: Debug changed files
  run: |
    echo "Changed files:"
    git diff --name-only ${{ github.event.before }} ${{ github.sha }}
```

**Fix:** Verify path glob patterns:
```yaml
paths:
  - 'api/**'          # Matches everything under api/
  - '!api/docs/**'    # Except docs/
  - '.github/workflows/pr-checks.yml'  # This specific file
```

### Permission Errors

**Problem:** "Resource not accessible by integration"

**Solution:** Add permissions to workflow:
```yaml
permissions:
  contents: read
  security-events: write  # For CodeQL/Trivy
  pull-requests: write    # For PR comments
  statuses: write         # For status checks
```

### Timeout Issues

**Problem:** Workflow times out

**Solution 1: Increase timeout**
```yaml
jobs:
  integration-tests:
    timeout-minutes: 30  # Increased from default 360
```

**Solution 2: Add step timeout**
```yaml
- name: Run tests
  timeout-minutes: 10
  run: pytest tests/
```

### Artifact Upload Failures

**Problem:** Artifacts not uploading

**Check:**
1. Path exists
2. Size < 10GB (GitHub limit)
3. Retention policy not exceeded

**Fix:**
```yaml
- name: Upload artifacts
  uses: actions/upload-artifact@v4
  if: always()  # Upload even on failure
  with:
    name: test-results
    path: |
      api/coverage.xml
      api/htmlcov/
    retention-days: 30  # Explicit retention
```

---

## Managing Workflow Secrets

### Adding a New Secret

**Via GitHub CLI:**
```bash
gh secret set SECRET_NAME --body "secret-value"

# Or from file
gh secret set SECRET_NAME < secret.txt

# List secrets
gh secret list
```

**Via GitHub Web UI:**
1. Go to Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Enter name and value
4. Click "Add secret"

### Using Secrets in Workflows

```yaml
steps:
  - name: Deploy
    env:
      DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
    run: |
      echo "Deploying with key..."
      # Use $DEPLOY_KEY here
```

**Security notes:**
- Secrets are redacted in logs
- Never echo secrets directly
- Use temporary credentials when possible
- Rotate secrets regularly

---

## Branch Protection Rules

### Recommended Settings

```yaml
# Configure via GitHub Settings > Branches > Add rule

Branch name pattern: main

Protections:
  ✅ Require a pull request before merging
     ✅ Require approvals: 1
     ✅ Dismiss stale reviews
  ✅ Require status checks to pass before merging
     ✅ Require branches to be up to date
     Required checks:
        - Backend Quality
        - Frontend Quality
        - PR Quality Status
  ✅ Require conversation resolution before merging
  ✅ Do not allow bypassing the above settings
```

### Via GitHub CLI

```bash
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Backend Quality","Frontend Quality"]}' \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field enforce_admins=true
```

---

## Monitoring and Alerts

### GitHub Actions Status

Monitor workflow health:

```bash
# Recent failures
gh run list --status failure --limit 10

# Specific workflow failures
gh run list --workflow=pr-checks.yml --status failure

# Get failure details
gh run view <run-id> --log-failed
```

### Setting Up Notifications

**1. Email notifications:**
- GitHub > Settings > Notifications
- Enable "Actions" notifications

**2. Slack integration:**
```yaml
# Add to workflow
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "❌ Pipeline failed: ${{ github.workflow }}"
      }
```

**3. GitHub CLI watch:**
```bash
# Watch in terminal
gh run watch

# With notifications
gh run watch && terminal-notifier -message "Workflow complete"
```

---

## Cost Optimization

### GitHub Actions Minutes

**Free tier:** 2,000 minutes/month (private repos)

**Current usage:**
- PR check: ~5 min
- Main pipeline: ~15 min
- ~20 min per merged PR

**Optimization strategies:**

1. **Path-based triggers** (already implemented)
2. **Cache dependencies** (already implemented)
3. **Fail fast:**
   ```yaml
   strategy:
     fail-fast: true  # Stop other jobs on first failure
   ```
4. **Conditional jobs:**
   ```yaml
   if: github.event_name == 'push' && github.ref == 'refs/heads/main'
   ```
5. **Self-hosted runners** (for high-volume projects)

### Artifact Storage

**Free tier:** 500MB storage

**Cleanup old artifacts:**
```bash
# List artifacts
gh api repos/:owner/:repo/actions/artifacts

# Delete old artifacts (via script)
gh api repos/:owner/:repo/actions/artifacts \
  | jq '.artifacts[] | select(.expired == false) | .id' \
  | xargs -I {} gh api repos/:owner/:repo/actions/artifacts/{} --method DELETE
```

**Set retention in workflow:**
```yaml
- uses: actions/upload-artifact@v4
  with:
    retention-days: 7  # Delete after 7 days
```

---

## Rollback Procedures

### Reverting Workflow Changes

**1. Identify problematic commit:**
```bash
git log --oneline .github/workflows/
```

**2. Revert commit:**
```bash
git revert <commit-hash>
git push origin main
```

**3. Or restore from previous version:**
```bash
git checkout <previous-commit> -- .github/workflows/pr-checks.yml
git commit -m "Rollback workflow to previous version"
git push origin main
```

### Emergency Workflow Disable

**Disable via GitHub UI:**
1. Actions > Select workflow
2. Click "..." menu
3. Select "Disable workflow"

**Or rename file:**
```bash
mv .github/workflows/pr-checks.yml .github/workflows/pr-checks.yml.disabled
git commit -m "Temporarily disable PR checks"
git push origin main
```

---

## Best Practices

### Do's ✅

- Test workflow changes on feature branches
- Use semantic commit messages for pipeline changes
- Document reasons for configuration changes
- Keep workflows DRY with reusable workflows
- Version pin dependencies when stability is critical
- Monitor pipeline performance regularly

### Don'ts ❌

- Don't commit secrets or credentials
- Don't bypass required status checks
- Don't disable security scans without documentation
- Don't increase timeouts without investigating root cause
- Don't make breaking changes without team notification
- Don't test on main branch

---

## Emergency Contacts

**Pipeline issues:**
- Check [PIPELINE_TESTING.md](./PIPELINE_TESTING.md) for debugging
- Review workflow logs: `gh run view <run-id> --log`
- Search GitHub Actions community: https://github.com/orgs/community/discussions

**GitHub Actions status:**
- https://www.githubstatus.com/

---

## Related Documentation

- [CI_CD_PIPELINE.md](./CI_CD_PIPELINE.md) - Pipeline architecture
- [PIPELINE_TESTING.md](./PIPELINE_TESTING.md) - Testing guide
- [TODO_FUTURE_ENHANCEMENTS.md](./TODO_FUTURE_ENHANCEMENTS.md) - Planned improvements
- [CLAUDE.md](../CLAUDE.md) - Development guidelines
