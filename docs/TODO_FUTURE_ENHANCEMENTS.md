# Future Pipeline Enhancements

## Overview

This document tracks planned improvements and future enhancements for the CI/CD pipeline. These items are **not currently implemented** but represent valuable additions for future development.

## Priority: High

### 1. End-to-End Testing with Playwright

**Status:** Not implemented
**Effort:** Medium (2-3 days)
**Value:** High

**Description:**
Add browser-based E2E tests for critical user workflows.

**Implementation:**
```bash
# Install Playwright
cd ui
npm install -D @playwright/test
npx playwright install

# Create tests
mkdir -p tests/e2e
```

**Workflow integration:**
```yaml
- name: Run Playwright E2E tests
  run: |
    cd ui
    npx playwright test
  continue-on-error: true  # Initially non-blocking

- name: Upload test results
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report
    path: ui/playwright-report/
```

**Key scenarios to test:**
- Upload NIEM schema
- Validate schema
- Ingest XML/JSON data
- View graph visualization
- Error handling flows

**Files to create:**
- `ui/playwright.config.ts`
- `ui/tests/e2e/schema-upload.spec.ts`
- `ui/tests/e2e/data-ingest.spec.ts`
- `ui/tests/e2e/graph-view.spec.ts`

---

### 2. Performance Testing with k6

**Status:** Not implemented
**Effort:** Medium (2-3 days)
**Value:** Medium

**Description:**
Load testing for API endpoints to establish performance baselines.

**Implementation:**
```bash
# Install k6 locally
brew install k6  # macOS
```

**Test scenarios:**
```javascript
// tests/performance/api-load-test.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up
    { duration: '1m', target: 10 },   // Steady
    { duration: '30s', target: 0 },   // Ramp down
  ],
};

export default function () {
  let res = http.get('http://localhost:8000/healthz');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 200ms': (r) => r.timings.duration < 200,
  });
}
```

**Workflow integration:**
```yaml
performance-tests:
  name: Performance Tests
  runs-on: ubuntu-latest
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  continue-on-error: true  # Non-blocking

  steps:
    - uses: actions/checkout@v4

    - name: Start services
      run: docker compose up -d

    - name: Install k6
      run: |
        sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
        echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update
        sudo apt-get install k6

    - name: Run load tests
      run: k6 run tests/performance/api-load-test.js --out json=results.json

    - name: Upload results
      uses: actions/upload-artifact@v4
      with:
        name: performance-results
        path: results.json
```

**Performance targets to establish:**
- `/healthz`: < 50ms @ 100 RPS
- `/api/schema`: < 500ms @ 10 RPS
- `/api/ingest/xml`: < 2s @ 5 RPS (with 1MB file)

---

## Priority: Medium

### 3. Container Image Publishing

**Status:** Not implemented
**Effort:** Low (1 day)
**Value:** Medium (when sharing externally)

**Description:**
Publish Docker images to GitHub Container Registry (GHCR) or Docker Hub for easier distribution.

**When needed:**
- Sharing with collaborators
- Government distribution
- Enterprise deployment
- Public release

**Implementation:**
```yaml
# New workflow: .github/workflows/release.yml
name: Release

on:
  release:
    types: [published]

jobs:
  publish-images:
    name: Build and Publish Images
    runs-on: ubuntu-latest

    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: ./api
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/api:latest
            ghcr.io/${{ github.repository }}/api:${{ github.ref_name }}

      - name: Build and push UI image
        uses: docker/build-push-action@v5
        with:
          context: ./ui
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/ui:latest
            ghcr.io/${{ github.repository }}/ui:${{ github.ref_name }}
```

**Documentation needs:**
- Update README with pull instructions
- Document versioning strategy
- Add security scanning for published images

---

### 4. SBOM Generation

**Status:** Not implemented
**Effort:** Low (1 day)
**Value:** High (for gov/enterprise distribution)

**Description:**
Generate Software Bill of Materials for supply chain security and compliance.

**When needed:**
- Government distribution (NIEM context!)
- Enterprise customers
- Compliance requirements
- Vulnerability tracking

**Implementation:**
```yaml
sbom-generation:
  name: Generate SBOM
  runs-on: ubuntu-latest
  if: github.event_name == 'release'

  steps:
    - uses: actions/checkout@v4

    - name: Generate SBOM with syft
      uses: anchore/sbom-action@v0
      with:
        image: ghcr.io/${{ github.repository }}/api:latest
        format: cyclonedx-json
        output-file: sbom-api.json

    - name: Upload SBOM
      uses: actions/upload-artifact@v4
      with:
        name: sbom
        path: sbom-*.json

    - name: Attach to release
      uses: softprops/action-gh-release@v1
      with:
        files: sbom-*.json
```

**Tools to consider:**
- **syft** (recommended) - Fast, accurate, multi-format
- **cyclonedx-cli** - Standard SBOM format
- **trivy sbom** - Integrated with Trivy scanning

---

### 5. Deployment Automation

**Status:** Not implemented
**Effort:** High (5-7 days)
**Value:** Medium (only if hosting remotely)

**Description:**
Automated deployment to remote environments (only needed if moving beyond local PoC).

**Current state:** Local-only via `docker-compose up`

**Future scenarios:**
- Deploy to dev/staging servers
- Cloud hosting (AWS, Azure, GCP)
- Kubernetes deployment

**Example workflow:**
```yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        type: choice
        options:
          - dev
          - staging
          - production

jobs:
  deploy:
    name: Deploy to ${{ inputs.environment }}
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to environment
        run: |
          # SSH to server
          # Pull latest images
          # Run docker compose
          # Smoke tests
          # Rollback on failure
```

**Considerations:**
- Secrets management (API keys, credentials)
- Blue-green deployment
- Health check validation
- Rollback procedures
- Monitoring integration

---

## Priority: Low

### 6. Advanced Observability

**Status:** Not implemented
**Effort:** High (5-7 days)
**Value:** Low (for PoC), High (for production)

**Description:**
Comprehensive monitoring, logging, and alerting.

**Components:**
1. **Prometheus metrics**
   - Request rates
   - Error rates
   - Response times
   - Resource usage

2. **Grafana dashboards**
   - System health overview
   - API performance
   - Database metrics
   - Storage usage

3. **Distributed tracing**
   - OpenTelemetry instrumentation
   - Request flow visualization

4. **Centralized logging**
   - Elasticsearch/Loki
   - Log aggregation
   - Search and analysis

**When to implement:**
- Moving to production
- Need performance insights
- Debugging complex issues
- SLA requirements

---

### 7. Dependency Update Automation

**Status:** Not implemented
**Effort:** Medium (2-3 days)
**Value:** Medium

**Description:**
Automated dependency updates with Dependabot or Renovate.

**Dependabot configuration:**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/api"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "npm"
    directory: "/ui"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

**Benefits:**
- Automatic security updates
- Keeps dependencies current
- Reduces maintenance burden

**Considerations:**
- Can create many PRs
- May introduce breaking changes
- Requires good test coverage

---

### 8. Multi-environment Testing

**Status:** Not implemented
**Effort:** Medium (3-4 days)
**Value:** Low (for single-environment PoC)

**Description:**
Test across multiple Python/Node versions and operating systems.

**Example matrix:**
```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12', '3.13']
    node-version: ['18', '20', '22']
    os: [ubuntu-latest, macos-latest, windows-latest]
```

**When needed:**
- Library/framework development
- Multi-platform distribution
- Supporting older versions

---

### 9. Code Coverage Trending

**Status:** Not implemented
**Effort:** Low (1 day)
**Value:** Low

**Description:**
Track code coverage over time and visualize trends.

**Options:**
- **Codecov** (SaaS)
- **Coveralls** (SaaS)
- **GitHub Pages** with coverage-badge-py

**Implementation:**
```yaml
- name: Generate coverage badge
  uses: tj-actions/coverage-badge-py@v2
  with:
    output: coverage.svg

- name: Commit badge
  run: |
    git add coverage.svg
    git commit -m "Update coverage badge"
    git push
```

---

### 10. Pre-commit Hooks

**Status:** Not implemented
**Effort:** Low (1 day)
**Value:** Medium

**Description:**
Run quality checks before commits to catch issues earlier.

**Setup:**
```bash
pip install pre-commit

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff

  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy

# Install hooks
pre-commit install
```

**Benefits:**
- Faster feedback than CI
- Prevents pushing broken code
- Enforces consistency

**Considerations:**
- Can slow down commits
- May frustrate developers
- Optional vs required

---

## Implementation Checklist

When implementing any of these enhancements:

- [ ] Create feature branch
- [ ] Update relevant workflows
- [ ] Add configuration files
- [ ] Update documentation (CI_CD_PIPELINE.md, etc.)
- [ ] Test thoroughly
- [ ] Create PR with detailed description
- [ ] Get team review
- [ ] Merge and monitor

---

## Revisit Schedule

Review this document:
- **Quarterly:** Reassess priorities based on project needs
- **Before major milestones:** Check if any items become high priority
- **On request:** When stakeholders ask for specific features

---

## Related Documentation

- [CI_CD_PIPELINE.md](./CI_CD_PIPELINE.md) - Current pipeline architecture
- [PIPELINE_TESTING.md](./PIPELINE_TESTING.md) - Testing procedures
- [PIPELINE_MAINTENANCE.md](./PIPELINE_MAINTENANCE.md) - Maintenance guide
- [CLAUDE.md](../CLAUDE.md) - Development guidelines
