# CI/CD Pipeline Documentation

## Overview

This project uses a streamlined, two-workflow CI/CD pipeline optimized for a local development PoC. The pipeline focuses on fast feedback, high code quality, and practical security checks without bureaucratic overhead.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Pull Request                             │
├─────────────────────────────────────────────────────────────────┤
│  pr-checks.yml                                                   │
│  ├── Backend Quality (parallel)                                 │
│  │   ├── Lint (ruff)                                           │
│  │   ├── Format (black)                                        │
│  │   ├── Type check (mypy)                                     │
│  │   ├── Security (bandit high+)                               │
│  │   └── Unit tests (80% coverage)                             │
│  └── Frontend Quality (parallel)                                │
│      ├── Lint (eslint)                                          │
│      ├── Type check (tsc)                                       │
│      ├── Security (npm audit critical)                          │
│      ├── Unit tests (80% coverage)                              │
│      └── Build validation                                       │
│                                                                  │
│  Runtime: ~3-5 minutes                                          │
│  All checks: BLOCKING                                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Main Branch                              │
├─────────────────────────────────────────────────────────────────┤
│  main-pipeline.yml                                               │
│  ├── Integration Tests (BLOCKING)                               │
│  │   ├── Neo4j service                                          │
│  │   ├── MinIO service                                          │
│  │   └── Full integration suite                                 │
│  ├── Docker Build & Smoke Tests (BLOCKING)                      │
│  │   ├── Build all services                                     │
│  │   ├── Start docker compose                                   │
│  │   ├── Test /healthz endpoint                                 │
│  │   ├── Test /readyz endpoint                                  │
│  │   └── Test UI accessibility                                  │
│  ├── Security Scan (NON-BLOCKING)                               │
│  │   └── Trivy container/dependency scan                        │
│  └── CodeQL Analysis (NON-BLOCKING)                             │
│      ├── Python SAST                                             │
│      └── JavaScript SAST                                         │
│                                                                  │
│  Runtime: ~10-15 minutes                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Workflow Details

### PR Checks (`pr-checks.yml`)

**Purpose:** Fast quality feedback on pull requests

**Triggers:**
- Pull requests to `main` or `develop`
- Manual dispatch for testing

**Path-based Optimization:**
- Only runs backend checks if `api/**` files changed
- Only runs frontend checks if `ui/**` files changed
- Always runs if `.github/workflows/**` changed

**Quality Gates (All Blocking):**

| Check | Tool | Threshold | Rationale |
|-------|------|-----------|-----------|
| Lint | ruff, eslint | Zero errors | Code style consistency |
| Format | black | Exact match | Automated formatting |
| Type Check | mypy, tsc | Zero errors | Type safety |
| Security | bandit (high+), npm audit (critical) | Zero critical | Security baseline |
| Unit Tests | pytest, vitest | 80% coverage | Code correctness |
| Build | npm build | Successful | Production viability |

**Artifacts:**
- Backend coverage report (HTML + XML)
- Frontend coverage report
- Security scan results (bandit, npm audit)

---

### Main Pipeline (`main-pipeline.yml`)

**Purpose:** Comprehensive validation after merge to main

**Triggers:**
- Push to `main` branch
- Manual dispatch for testing

**Stages:**

#### 1. Integration Tests (Blocking)
- Runs full integration test suite
- Uses GitHub Actions services for Neo4j and MinIO
- Tests actual database/storage interactions
- **Failure blocks pipeline**

#### 2. Docker Build & Smoke Tests (Blocking)
- Builds all Docker images from scratch
- Starts full docker-compose stack
- Validates health endpoints:
  - `GET /healthz` - Application liveness
  - `GET /readyz` - Dependencies ready (Neo4j, MinIO)
  - `GET http://localhost:3000` - UI accessibility
- **Failure blocks pipeline**

#### 3. Security Scanning (Non-blocking)
- Trivy scans for:
  - Container vulnerabilities
  - Dependency vulnerabilities
  - Misconfigurations
- Results uploaded to GitHub Security tab
- **Failures are informational only**

#### 4. CodeQL Analysis (Non-blocking)
- Static analysis for Python and JavaScript
- Detects security issues, bugs, code smells
- Results uploaded to GitHub Security tab
- **Failures are informational only**

**Why Some Gates Are Non-blocking:**
- Container scanning can have false positives
- Some vulnerabilities may not be fixable immediately
- Focus on awareness, not blocking development

---

## Running Checks Locally

### Backend Quality Checks

```bash
cd api

# Lint
ruff check src/

# Format check
black src/ --check

# Type check
mypy src/

# Security scan
bandit -r src/ -ll

# Unit tests with coverage
pytest tests/unit/ --cov=src --cov-fail-under=80
```

### Frontend Quality Checks

```bash
cd ui

# Lint
npm run lint

# Type check
npm run type-check

# Security audit
npm audit --audit-level=critical

# Unit tests with coverage
npm run test:coverage

# Build
npm run build
```

### Integration Tests

```bash
# Start services
docker compose up -d neo4j minio

# Wait for services
sleep 10

# Run tests
cd api
pytest tests/integration/

# Cleanup
docker compose down
```

### Full Stack Smoke Tests

```bash
# Build and start everything
docker compose up -d --build

# Wait for services (or use the wait script)
sleep 30

# Test endpoints
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
curl http://localhost:3000

# Cleanup
docker compose down
```

---

## Configuration Files

### Python Tooling (`api/pyproject.toml`)

Centralizes configuration for:
- **ruff:** Linting rules, line length (120), ignore patterns
- **black:** Formatting settings
- **mypy:** Type checking strictness
- **pytest:** Test discovery, markers, coverage thresholds
- **coverage:** Branch coverage, exclusions, 80% threshold

### Docker Build Optimization

- **`api/.dockerignore`:** Excludes tests, caches, .env files
- **`ui/.dockerignore`:** Excludes node_modules, .next, test files

**Impact:** 10-50x faster builds by reducing context size from ~850MB to ~15MB

---

## Troubleshooting

### PR Checks Failing

**Lint errors:**
```bash
# Auto-fix most issues
cd api && ruff check src/ --fix
cd ui && npm run lint -- --fix

# Format code
cd api && black src/
```

**Type errors:**
- Review mypy/tsc output
- Add type annotations
- Use `# type: ignore` sparingly for third-party issues

**Coverage below 80%:**
- Add unit tests for new code
- Check `htmlcov/index.html` for coverage gaps

**Security issues:**
- Bandit: Review flagged code, add `# nosec` with justification if false positive
- npm audit: Update dependencies or document risk

### Integration Tests Failing

**Services not ready:**
- Increase health check retries
- Check service logs: `docker compose logs neo4j minio`

**Connection errors:**
- Verify environment variables match docker-compose.yml
- Check network connectivity

### Docker Build Failing

**Context too large:**
- Ensure `.dockerignore` files are present
- Check for large files in build context

**Build hangs:**
- Clear Docker cache: `docker system prune -a`
- Check for infinite loops in Dockerfile

### Pipeline Timing Out

- Default timeout is 2 hours
- Integration tests have 5-minute timeout per test
- Smoke tests wait up to 2 minutes for services

---

## Modifying the Pipeline

### Adding a New Quality Check

1. Add step to appropriate workflow
2. Use `continue-on-error: true` if non-blocking
3. Upload artifacts for visibility
4. Update this documentation

**Example: Add pytest-benchmark**

```yaml
- name: Run performance benchmarks
  run: |
    cd api
    pytest tests/ --benchmark-only
  continue-on-error: true  # Non-blocking
```

### Changing Coverage Threshold

Update in two places:

1. **`api/pyproject.toml`:**
```toml
[tool.coverage.report]
fail_under = 85.0  # Changed from 80
```

2. **`.github/workflows/pr-checks.yml`:**
```yaml
--cov-fail-under=85  # Changed from 80
```

### Adding Path-based Triggers

```yaml
on:
  pull_request:
    paths:
      - 'api/**'
      - 'ui/**'
      - 'docs/**'  # New path
```

---

## Security Scanning Details

### Bandit (Python Security)
- Scans for common security issues
- Severity levels: low, medium, high
- **Blocking:** High+ severity only
- Common issues: hardcoded secrets, SQL injection, shell injection

### npm audit (Node Security)
- Checks dependencies for known vulnerabilities
- **Blocking:** Critical severity only
- Fix: `npm audit fix` or update dependencies

### Trivy (Container Security)
- Scans base images and dependencies
- Checks for CVEs and misconfigurations
- **Non-blocking** - informational only

### CodeQL (SAST)
- Deep static analysis
- Detects: SQL injection, XSS, path traversal, etc.
- **Non-blocking** - informational only

---

## Best Practices

### For Developers

1. **Run checks locally before pushing**
   - Saves CI time and GitHub Actions minutes
   - Faster feedback loop

2. **Keep PRs small**
   - Easier to review
   - Faster CI execution
   - Less likely to conflict

3. **Fix failing tests immediately**
   - Don't let main branch stay red
   - Blocks other developers

4. **Review security warnings**
   - Even non-blocking ones
   - Document why warnings are acceptable if not fixed

### For Maintainers

1. **Monitor pipeline performance**
   - PR checks should stay under 5 minutes
   - Main pipeline under 15 minutes

2. **Update dependencies regularly**
   - Security patches
   - Tool updates (ruff, pytest, etc.)

3. **Review non-blocking failures**
   - Trivy and CodeQL findings
   - Address or document accepted risks

4. **Keep documentation current**
   - Update when adding/changing gates
   - Document rationale for decisions

---

## GitHub Actions Limits

**Free tier limits:**
- 2,000 minutes/month for private repos
- Unlimited for public repos

**Current usage estimate:**
- PR check: ~5 minutes
- Main pipeline: ~15 minutes
- ~20 minutes per merged PR

**Optimization tips:**
- Path-based triggers reduce unnecessary runs
- Caching reduces dependency install time
- Parallel jobs reduce total runtime

---

## Related Documentation

- [PIPELINE_TESTING.md](./PIPELINE_TESTING.md) - Testing and validation guide
- [PIPELINE_MAINTENANCE.md](./PIPELINE_MAINTENANCE.md) - Maintenance procedures
- [TODO_FUTURE_ENHANCEMENTS.md](./TODO_FUTURE_ENHANCEMENTS.md) - Future improvements
- [CLAUDE.md](../CLAUDE.md) - Development guidelines
