# GitHub Issues: Version Control & Release Management

Create these issues on GitHub to implement version control mapped to NIEM versions.

---

## Issue 1: Add semantic versioning scheme mapped to NIEM versions

**Labels:** `enhancement`

**Description:**

### Context
Currently the repo has static version 1.0.0 in both `api/pyproject.toml` and `ui/package.json`. The codebase supports NIEM 6.0 but there's no formal mapping between application releases and NIEM model versions.

### Goal
Establish a semantic versioning scheme that clearly maps application versions to supported NIEM model versions.

### Proposed Approach
- Use semantic versioning: `MAJOR.MINOR.PATCH` (e.g., 6.0.0, 6.1.0)
- Major version tracks NIEM model version (currently 6.x for NIEM 6.0)
- Minor version for feature additions within same NIEM version
- Patch version for bug fixes

### Acceptance Criteria
- [ ] Document versioning scheme in README or VERSIONING.md
- [ ] Define version compatibility matrix (app version ↔ NIEM version)
- [ ] Specify upgrade/migration strategy when NIEM version changes
- [ ] Include version in API responses (`/health` or `/version` endpoint)

### Related
Part of version control initiative to enable proper release management.

---

## Issue 2: Create automated version management and release workflow

**Labels:** `enhancement`

**Description:**

### Context
Need automated tooling to manage version bumps, changelogs, and GitHub releases.

### Goal
Implement CI/CD workflow for version management and release creation.

### Proposed Approach
1. **Version Source of Truth**: Single VERSION file at repo root
2. **Automation Tools**:
   - Python: `bump2version` or `tbump` to sync version across files
   - GitHub Actions workflow for releases
3. **Changelog**: Automated changelog generation from conventional commits

### Implementation Tasks
- [ ] Add VERSION file at repo root
- [ ] Configure version bumping tool (update pyproject.toml, package.json, VERSION)
- [ ] Create `.github/workflows/release.yml` for automated releases
- [ ] Add `CHANGELOG.md` with Keep a Changelog format
- [ ] Script to generate changelog from git commits
- [ ] Release checklist template

### Acceptance Criteria
- [ ] Single command to bump version across all files
- [ ] GitHub release created with changelog when version tag pushed
- [ ] Release includes artifacts (Docker images, tagged commit)
- [ ] Documentation on release process

### Related
Depends on Issue #1 (versioning scheme).

---

## Issue 3: Add version metadata to API and UI

**Labels:** `enhancement`

**Description:**

### Context
Applications should expose their version for debugging, compatibility checks, and operational visibility.

### Goal
Expose version information through API endpoints and UI.

### Implementation Tasks

#### API (`api/`)
- [ ] Add `GET /api/version` endpoint returning:
```json
{
  "app_version": "6.0.0",
  "niem_version": "6.0",
  "cmf_version": "1.0",
  "build_timestamp": "2025-01-15T10:30:00Z",
  "git_commit": "abc1234"
}
```
- [ ] Add version to existing `/health` endpoint
- [ ] Include version in response headers (`X-App-Version`)
- [ ] Load version from pyproject.toml at runtime

#### UI (`ui/`)
- [ ] Display version in footer or settings page
- [ ] Add version to browser console on load
- [ ] Include version in API client headers
- [ ] Load version from package.json at build time

### Acceptance Criteria
- [ ] Version endpoints return accurate information
- [ ] Version visible in UI
- [ ] Integration test validates version endpoint
- [ ] Version automatically updated on release

### Related
Part of version control initiative.

---

## Issue 4: Document NIEM version compatibility and migration

**Labels:** `documentation`

**Description:**

### Context
As the application evolves to support different NIEM model versions (currently 6.0, future 6.1, 7.0), users need clear documentation on compatibility and migration.

### Goal
Create comprehensive documentation for version compatibility, upgrade paths, and breaking changes.

### Implementation Tasks
- [ ] Create `docs/VERSIONING.md` with:
  - Version numbering scheme explanation
  - NIEM version compatibility matrix
  - Breaking change policy
- [ ] Create `docs/MIGRATION.md` with:
  - Upgrade guides between versions
  - Data migration scripts/procedures
  - Backward compatibility notes
- [ ] Update main README with version info section
- [ ] Add deprecation policy

### Acceptance Criteria
- [ ] Clear matrix showing app version → NIEM version support
- [ ] Migration guide for upgrading NIEM versions
- [ ] Examples of handling multi-version support (if applicable)
- [ ] Documented process for deprecating features

### Example Compatibility Matrix
| App Version | NIEM Version | CMF Version | Support Status |
|-------------|--------------|-------------|----------------|
| 6.0.x       | 6.0          | 1.0         | Active         |
| 6.1.x       | 6.0          | 1.0         | Planned        |
| 7.0.x       | 7.0          | 1.0         | Future         |

### Related
Part of version control initiative.

---

## Issue 5: Add Docker image versioning and tagging strategy

**Labels:** `enhancement`

**Description:**

### Context
Docker images need consistent tagging aligned with semantic versioning and NIEM versions.

### Goal
Implement Docker image tagging strategy for releases and development builds.

### Proposed Tagging Strategy
- `latest` - latest stable release
- `vMAJOR.MINOR.PATCH` - specific release (e.g., `v6.0.0`)
- `vMAJOR.MINOR` - latest patch for minor version (e.g., `v6.0`)
- `vMAJOR` - latest minor for major version (e.g., `v6`)
- `niem-X.Y` - specific NIEM version support (e.g., `niem-6.0`)
- `edge` or `dev` - development builds from main branch
- `sha-<commit>` - specific commit builds

### Implementation Tasks
- [ ] Update Docker Compose files with version tags
- [ ] Create GitHub Actions workflow for building and pushing images
- [ ] Tag images in container registry (Docker Hub, GitHub Container Registry)
- [ ] Document image tagging in README
- [ ] Add image version label in Dockerfile

### Example Dockerfile Labels
```dockerfile
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.niem-version="6.0"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
```

### Acceptance Criteria
- [ ] Automated image builds on version tags
- [ ] Images properly tagged in registry
- [ ] Version labels in Docker images
- [ ] Documentation on pulling specific versions

### Related
Part of version control initiative, relates to Issue #2 (release workflow).

---

## Quick Start Guide

To create these issues on GitHub:

1. Go to: https://github.com/YOUR_USERNAME/niem-info-exch-e2e/issues/new
2. Copy each issue section above
3. Paste title and description
4. Add the specified labels
5. Submit

Or install GitHub CLI and run:
```bash
brew install gh  # or appropriate package manager
gh auth login
# Then create issues from this file programmatically
```
