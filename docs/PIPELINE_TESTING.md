# Pipeline Testing & Validation Guide

## Overview

This guide covers how to test and validate the CI/CD pipeline to ensure it works as designed before merging changes.

## Testing Strategies

### 1. Workflow Syntax Validation ✅ (Fastest)

Validate GitHub Actions YAML syntax locally before pushing.

#### Install actionlint

```bash
# macOS
brew install actionlint

# Linux
curl -sL https://github.com/rhysd/actionlint/releases/latest/download/actionlint_linux_amd64.tar.gz | tar xz
sudo mv actionlint /usr/local/bin/

# Windows (with scoop)
scoop install actionlint
```

#### Validate Workflows

```bash
# Validate all workflows
actionlint .github/workflows/*.yml

# Validate specific workflow
actionlint .github/workflows/pr-checks.yml

# With detailed output
actionlint -verbose .github/workflows/*.yml
```

#### Common Errors Caught

- Invalid YAML syntax
- Typos in action names
- Missing required parameters
- Invalid shell commands
- Incorrect workflow triggers

---

### 2. Local Check Execution ✅ (Fast)

Run the same commands that CI will execute, before pushing.

#### Backend Checks

```bash
cd api

# Install dependencies (once)
pip install -r requirements.txt
pip install -r requirements-test.txt

# Run all quality checks (same as CI)
echo "Running ruff..."
ruff check src/

echo "Running black..."
black src/ --check

echo "Running mypy..."
mypy src/

echo "Running bandit..."
bandit -r src/ -ll

echo "Running unit tests..."
pytest tests/unit/ --cov=src --cov-fail-under=80

echo "✅ All backend checks passed!"
```

#### Frontend Checks

```bash
cd ui

# Install dependencies (once)
npm ci

# Run all quality checks (same as CI)
echo "Running eslint..."
npm run lint

echo "Running TypeScript check..."
npm run type-check

echo "Running npm audit..."
npm audit --audit-level=critical

echo "Running unit tests..."
npm run test:coverage

echo "Running build..."
npm run build

echo "✅ All frontend checks passed!"
```

#### Integration Tests

```bash
# Start dependencies
docker compose up -d neo4j minio

# Wait for services to be ready
echo "Waiting for services..."
sleep 15

# Set environment variables
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password
export MINIO_ENDPOINT=localhost:9001
export MINIO_ACCESS_KEY=minio
export MINIO_SECRET_KEY=minio123
export MINIO_SECURE=false

# Run integration tests
cd api
pytest tests/integration/ --verbose

# Cleanup
cd ..
docker compose down
```

---

### 3. Act - Run GitHub Actions Locally ⚡ (Recommended)

[Act](https://github.com/nektos/act) runs GitHub Actions workflows locally using Docker.

#### Install Act

```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows (with scoop)
scoop install act
```

#### Run Workflows Locally

```bash
# Test PR checks workflow (simulates pull request)
act pull_request -W .github/workflows/pr-checks.yml

# Test main pipeline workflow (simulates push to main)
act push -W .github/workflows/main-pipeline.yml

# Test specific job
act -j backend-quality

# Dry run (see what would run without executing)
act -n

# With verbose output
act -v
```

#### Act Configuration

Create `.actrc` for defaults:

```
# .actrc
-P ubuntu-latest=catthehacker/ubuntu:act-latest
--container-architecture linux/amd64
```

#### Limitations

- ~95% accurate (some differences from real GitHub Actions)
- Services (Neo4j, MinIO) may need manual setup
- GitHub-specific features (GITHUB_TOKEN, cache) behave differently
- Large workflows can be slow

**When to use:**
- Quick validation before pushing
- Testing workflow logic changes
- Debugging specific jobs

**When NOT to use:**
- Final validation (use feature branch instead)
- Testing service dependencies
- Validating security scans

---

### 4. Feature Branch Testing ✅ (Most Reliable)

Test on GitHub with a real workflow run.

#### Create Test Branch

```bash
# Create test branch
git checkout -b test/ci-pipeline-validation

# Make your workflow changes
# Edit .github/workflows/pr-checks.yml, etc.

# Commit changes
git add .github/workflows/
git commit -m "test: validate CI pipeline changes"

# Push to GitHub
git push origin test/ci-pipeline-validation
```

#### Open Draft PR

```bash
# Using GitHub CLI
gh pr create \
  --draft \
  --title "TEST: CI Pipeline Validation" \
  --body "Testing pipeline changes. DO NOT MERGE."

# Or manually on GitHub web UI
```

#### Monitor Workflow

```bash
# Watch workflow run in real-time
gh run watch

# List recent runs
gh run list --workflow=pr-checks.yml

# View specific run
gh run view <run-id>

# Download logs
gh run download <run-id>
```

#### What to Validate

- ✅ Workflows trigger on correct events
- ✅ Path filters work (change only `api/` triggers only backend)
- ✅ Jobs run in parallel where expected
- ✅ Caching works (second run is faster)
- ✅ Failing tests block merge
- ✅ Non-blocking jobs don't block (Trivy, CodeQL)
- ✅ Artifacts upload correctly
- ✅ Logs are readable and helpful

#### Cleanup

```bash
# Delete test branch (after validation)
git checkout main
git branch -D test/ci-pipeline-validation
git push origin --delete test/ci-pipeline-validation

# Or close PR without merging
gh pr close <pr-number>
```

---

### 5. Manual Workflow Dispatch 🎯 (For Testing)

Trigger workflows manually without creating a PR.

#### Via GitHub CLI

```bash
# Trigger PR checks manually
gh workflow run pr-checks.yml

# Trigger on specific branch
gh workflow run pr-checks.yml --ref test-branch

# Watch the run
gh run watch
```

#### Via GitHub Web UI

1. Go to **Actions** tab
2. Select workflow (e.g., "PR Quality Checks")
3. Click **Run workflow** button
4. Select branch
5. Click **Run workflow**

---

## Validation Checklist

Use this checklist when testing pipeline changes:

### Syntax & Configuration
- [ ] `actionlint` passes with no errors
- [ ] YAML syntax is valid
- [ ] All required parameters are present
- [ ] Environment variables are defined

### Path-Based Triggers
- [ ] Backend changes only trigger backend jobs
- [ ] Frontend changes only trigger frontend jobs
- [ ] Workflow changes trigger everything

### Quality Gates
- [ ] Lint failures block pipeline
- [ ] Type errors block pipeline
- [ ] Test failures block pipeline
- [ ] Coverage below 80% blocks pipeline
- [ ] Security critical issues block pipeline

### Non-Blocking Gates
- [ ] Trivy failures don't block
- [ ] CodeQL failures don't block
- [ ] Artifacts still upload on failure

### Performance
- [ ] PR checks complete in < 5 minutes
- [ ] Main pipeline completes in < 15 minutes
- [ ] Caching reduces dependency install time
- [ ] Jobs run in parallel where possible

### Integration Tests
- [ ] Neo4j service starts successfully
- [ ] MinIO service starts successfully
- [ ] Tests can connect to services
- [ ] Healthchecks work correctly

### Docker & Smoke Tests
- [ ] All images build successfully
- [ ] docker-compose stack starts
- [ ] `/healthz` endpoint returns 200
- [ ] `/readyz` endpoint returns 200
- [ ] UI is accessible on port 3000

### Artifacts & Reports
- [ ] Coverage reports upload correctly
- [ ] Security scan results upload
- [ ] Test results are viewable
- [ ] Logs are clear and helpful

---

## Debugging Failed Workflows

### View Detailed Logs

```bash
# View run logs
gh run view <run-id> --log

# Download all logs
gh run download <run-id>

# View specific job logs
gh run view <run-id> --job=<job-id> --log
```

### Common Issues

#### "Resource not accessible by integration"
**Cause:** Missing permissions
**Fix:** Add to workflow:
```yaml
permissions:
  contents: read
  security-events: write  # For CodeQL/Trivy
```

#### "Cache not found"
**Cause:** Cache key changed or expired
**Fix:** Normal on first run or after 7 days

#### "Service unhealthy"
**Cause:** Service failed to start in time
**Fix:** Increase health check retries:
```yaml
options: >-
  --health-retries 10
  --health-interval 5s
```

#### "Path filter didn't work"
**Cause:** Filter syntax error
**Fix:** Check path glob patterns:
```yaml
paths:
  - 'api/**'      # Matches api/anything
  - '!api/docs/'  # Exclude api/docs/
```

#### "Workflow didn't trigger"
**Cause:** Multiple possibilities
**Fix:** Check:
- Branch name matches trigger
- Path filters don't exclude all changes
- Workflow file is in `.github/workflows/`
- YAML syntax is valid

---

## Testing Workflow Changes

### Safe Testing Process

1. **Validate syntax locally**
   ```bash
   actionlint .github/workflows/pr-checks.yml
   ```

2. **Test with act (if applicable)**
   ```bash
   act pull_request -j backend-quality
   ```

3. **Create test branch**
   ```bash
   git checkout -b test/workflow-changes
   git push origin test/workflow-changes
   ```

4. **Open draft PR**
   ```bash
   gh pr create --draft
   ```

5. **Monitor results**
   ```bash
   gh run watch
   ```

6. **Iterate on failures**
   - Fix issues
   - Push updates
   - Workflow re-runs automatically

7. **Merge when green**
   ```bash
   gh pr ready  # Mark PR as ready
   gh pr merge --squash
   ```

---

## Performance Testing

### Measure Workflow Runtime

```bash
# Get runtime for recent runs
gh run list --workflow=pr-checks.yml --json conclusion,startedAt,updatedAt

# View timing for specific run
gh run view <run-id> --json jobs | jq '.jobs[] | {name: .name, duration: .completed_at - .started_at}'
```

### Optimization Targets

| Workflow | Target | Acceptable | Too Slow |
|----------|--------|------------|----------|
| PR Checks | < 3 min | < 5 min | > 10 min |
| Main Pipeline | < 10 min | < 15 min | > 20 min |

### Slow Workflow Troubleshooting

1. **Check caching**
   - pip cache hit rate
   - npm cache hit rate

2. **Identify slow jobs**
   ```bash
   gh run view <run-id> --json jobs
   ```

3. **Parallelize where possible**
   - Remove unnecessary `needs:` dependencies

4. **Optimize Docker builds**
   - Check `.dockerignore` is present
   - Use multi-stage builds
   - Layer caching enabled

---

## Continuous Validation

### Weekly Checks

- [ ] Run full pipeline on main branch
- [ ] Review non-blocking failures (Trivy, CodeQL)
- [ ] Check workflow performance metrics
- [ ] Update dependencies if needed

### After Dependency Updates

- [ ] Verify all workflows still pass
- [ ] Check for new security vulnerabilities
- [ ] Update version pins if needed

### Before Major Changes

- [ ] Test on feature branch first
- [ ] Validate with act if possible
- [ ] Document changes in this file

---

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [actionlint Repository](https://github.com/rhysd/actionlint)
- [act Repository](https://github.com/nektos/act)
- [GitHub CLI](https://cli.github.com/)

## Related Documentation

- [CI_CD_PIPELINE.md](./CI_CD_PIPELINE.md) - Pipeline architecture and details
- [PIPELINE_MAINTENANCE.md](./PIPELINE_MAINTENANCE.md) - Maintenance procedures
- [TODO_FUTURE_ENHANCEMENTS.md](./TODO_FUTURE_ENHANCEMENTS.md) - Future improvements
