# Versioning Strategy

## Overview

This project uses **separate semantic versioning** for API and UI components, with automated version bumping in the CI/CD pipeline.

## Version Format

Both API and UI follow [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

### Prerelease Phase (0.x.y)

- **Current Status**: Prerelease (not production-ready)
- **API Version**: `0.1.0` (from `api/VERSION`)
- **UI Version**: `0.1.0` (from `ui/VERSION`)
- **Breaking changes allowed** in 0.x.y versions
- **No migration tooling active** during prerelease

### Version Increment Rules

**MAJOR** (0 → 1, or breaking changes in 1.0.0+):
- NIEM model version changes (e.g., 6.0 → 7.0)
- Breaking API changes
- Incompatible schema changes
- Triggered by: `BREAKING CHANGE:` in commit or `feat!:`, `fix!:` syntax

**MINOR** (0.1.0 → 0.2.0):
- New features (backward-compatible)
- Significant enhancements
- Triggered by: `feat:` commit prefix

**PATCH** (0.1.0 → 0.1.1):
- Bug fixes
- Minor improvements
- Documentation updates
- Triggered by: `fix:` commit prefix or other conventional commits

## Separate Versioning

API and UI versions are **independent** and auto-bump only when their respective code changes:

### API Version (`api/VERSION`)
- Bumps when changes are made to `api/**` files
- Exposed via:
  - `/healthz` endpoint: `{"api_version": "0.1.0", ...}`
  - `X-API-Version` response header
  - FastAPI docs version
  - Docker image labels

### UI Version (`ui/VERSION`)
- Bumps when changes are made to `ui/**` files
- Exposed via:
  - Footer: "UI: v0.1.0"
  - Environment variable: `NEXT_PUBLIC_APP_VERSION`
  - Docker image labels

### Example Scenarios

**Scenario 1**: Fix API bug
```bash
# Commit: "fix: resolve Neo4j connection timeout"
# Files: api/src/niem_api/clients/neo4j_client.py
# Result: api/VERSION bumps 0.1.0 → 0.1.1, ui/VERSION unchanged
```

**Scenario 2**: Add UI feature
```bash
# Commit: "feat: add schema set naming to upload form"
# Files: ui/src/components/SchemaUpload.tsx
# Result: ui/VERSION bumps 0.1.0 → 0.2.0, api/VERSION unchanged
```

**Scenario 3**: Update both
```bash
# Commit: "feat: add new graph query endpoint and UI visualizer"
# Files: api/src/niem_api/handlers/graph.py, ui/src/components/GraphView.tsx
# Result: Both versions bump minor (0.1.0 → 0.2.0)
```

## Automated Version Bumping

### How It Works

1. **Developer workflow**:
   - Make changes on feature branch
   - Use conventional commits (`feat:`, `fix:`, etc.)
   - Merge to `main`

2. **CI automatically**:
   - Detects which files changed (`api/**` or `ui/**`)
   - Reads commit message for bump type
   - Updates appropriate `VERSION` file(s)
   - Commits back: `chore: bump API to 0.2.0 [skip ci]`
   - Re-triggers pipeline with new version

3. **Build pipeline**:
   - Reads `api/VERSION` and `ui/VERSION`
   - Injects into Docker builds as build args
   - Tags images: `api:v0.2.0`, `ui:v0.1.0`
   - Version available at runtime

### Workflow Files

- **`.github/workflows/auto-version-bump.yml`** - Auto-increment versions on merge to main
- **`.github/workflows/main-pipeline.yml`** - Build with version metadata

## Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types
- `feat:` - New feature (bumps MINOR)
- `fix:` - Bug fix (bumps PATCH)
- `docs:` - Documentation only (bumps PATCH)
- `chore:` - Build/tooling (bumps PATCH)
- `refactor:` - Code refactoring (bumps PATCH)
- `test:` - Add/update tests (bumps PATCH)
- `perf:` - Performance improvement (bumps PATCH)

### Breaking Changes
```
feat!: restructure API response format

BREAKING CHANGE: All endpoints now return data in { data, meta } wrapper
```

## NIEM Version Compatibility

| App Versions   | NIEM Version | CMF Version | Status      | Notes                          |
|----------------|--------------|-------------|-------------|--------------------------------|
| API 0.1.x      | 6.0          | 1.0         | Active      | Initial prerelease             |
| UI 0.1.x       | 6.0          | 1.0         | Active      | Initial prerelease             |
| API/UI 1.0.0+  | 6.0          | 1.0         | Future      | Production-ready (requires P0s)|
| API/UI 2.0.0+  | 7.0          | TBD         | Future      | NIEM 7.0 support               |

## Path to Production (1.0.0)

### Blockers for 1.0.0 Release

Must complete before either component can release 1.0.0:

**P0 Security** (GitHub Issues #19-21):
- [ ] Enable SSL/TLS for all services
- [ ] Implement comprehensive encryption in transit
- [ ] Add data encryption at rest
- [ ] Replace dev token with OAuth2/JWT
- [ ] Implement RBAC and authorization
- [ ] Add secrets management

**Critical Bugs**:
- [ ] Fix API test failures (#10)
- [ ] Fix UI test failures (#11)
- [ ] Ensure root node inclusion (#13)

**Production Readiness**:
- [ ] Test coverage ≥ 80%
- [ ] Security audit completed
- [ ] Performance testing completed
- [ ] Documentation complete

### When 1.0.0 Releases

**Migration System Activates**:
- `api/migrations/` - Neo4j schema migrations
- `ui/migrations/` - LocalStorage/state migrations
- Automated migration runner on startup

**Versioning Changes**:
- Breaking changes require MAJOR version bump
- Deprecation policy enforced
- Migration guides required for MAJOR bumps

## Version Metadata

### API Response Example
```json
{
  "status": "healthy",
  "api_version": "0.1.0",
  "git_commit": "abc1234567",
  "build_date": "2025-10-14T12:00:00Z",
  "niem_version": "6.0"
}
```

### Docker Image Labels
```
org.opencontainers.image.version=0.1.0
org.opencontainers.image.revision=abc1234567
org.opencontainers.image.created=2025-10-14T12:00:00Z
```

## Manual Version Override

To manually change version (not recommended during prerelease):

```bash
# Update version file
echo "0.2.0" > api/VERSION

# Commit
git add api/VERSION
git commit -m "chore: bump API to 0.2.0 [skip ci]"
git push
```

**Note**: Automated bumping will continue from the new version.

## References

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- GitHub Issues #1-5 (versioning discussion)
