<!--
Sync Impact Report
==================
Version change: 1.1.0 → 1.2.0
Reason: Added Performance Architecture principle (VII)

Modified sections:
- Core Principles: Added VII. Performance Architecture

Added sections:
- VII. Performance Architecture (new principle)

Removed sections: None

Templates requiring updates:
✅ plan-template.md - Constitution Check section already supports principle validation
✅ spec-template.md - Requirements section aligns with FR/NFR structure
✅ tasks-template.md - Phase structure supports test-first and user story organization

Follow-up TODOs: None
-->

# NIEM Information Exchange Constitution

## Core Principles

### I. Layered Architecture

All API code MUST follow the three-layer architecture pattern:

1. **main.py (HTTP/Routing Layer)**: Routes, middleware, authentication, dependency injection. Routes MUST be thin controllers that delegate immediately to handlers.
2. **handlers/ (Orchestration Layer)**: Multi-step workflow coordination, error handling, response formatting. Handlers MUST NOT make direct database queries.
3. **services/ (Business Logic Layer)**: Pure business logic, algorithms, external integrations. Services MUST be stateless, testable in isolation, and receive dependencies as parameters.

**Rationale**: Separation of concerns enables independent testing, clear responsibility boundaries, and maintainable code. This pattern is documented in `docs/API_ARCHITECTURE.md`.

### II. Standards Conformance

All NIEM-related functionality MUST conform to established standards:

- **NIEM 6.0**: Current supported version for schema validation and data exchange
- **CMF (Common Model Format)**: MUST use CMF tools for XSD-to-JSON conversion and validation
- **NDR (Naming and Design Rules)**: Schema uploads SHOULD pass NDR validation; skip option available for non-conformant third-party schemas

**Rationale**: Interoperability with government and partner systems requires strict adherence to NIEM standards. Non-conformance creates integration failures.

### III. Test-First Development

Testing MUST follow these requirements:

- **API (Python)**: Minimum 80% code coverage enforced by pytest
- **UI (TypeScript)**: Minimum 70% coverage enforced by vitest
- **AAA Pattern**: All tests MUST follow Arrange-Act-Assert structure
- **Isolation**: Unit tests MUST mock external dependencies (databases, APIs, file systems)
- **Descriptive Names**: Test names MUST describe what is tested and expected behavior

**Rationale**: Tests enable safe refactoring, catch regressions early, and serve as living documentation. Coverage requirements are documented in `docs/UNIT_TESTING.md`.

### IV. Semantic Versioning

Version management MUST follow these rules:

- **Format**: MAJOR.MINOR.PATCH per Semantic Versioning 2.0.0
- **Separate Versions**: API (`api/VERSION`) and UI (`ui/VERSION`) version independently
- **Conventional Commits**: All commits MUST use conventional commit format (`feat:`, `fix:`, `docs:`, etc.)
- **Breaking Changes**: MUST use `feat!:` or `BREAKING CHANGE:` footer for backward-incompatible changes
- **Auto-bump**: CI automatically increments versions based on commit prefixes

**Rationale**: Predictable versioning enables dependency management and communicates change impact. Details in `docs/VERSIONING.md`.

### V. Simplicity & YAGNI

All implementations MUST favor simplicity:

- **Minimum Viable**: Implement only what is directly requested or clearly necessary
- **No Speculative Features**: Do not add features, abstractions, or configurability for hypothetical future needs
- **Three Lines Over Abstraction**: Prefer three similar lines of code over premature abstraction
- **Delete Unused Code**: Remove unused code completely; no backward-compatibility shims for internal changes
- **Validate at Boundaries**: Only validate at system boundaries (user input, external APIs); trust internal code

**Rationale**: Complexity has compounding costs. Simple solutions are easier to understand, test, modify, and debug.

### VI. Security Architecture

All code MUST follow defense-in-depth security practices:

**Secrets Management**:
- Credentials MUST be externalized to environment variables (`.env` files)
- `.env` files MUST NEVER be committed to version control (enforced via `.gitignore`)
- Production deployments MUST use Docker Secrets or Kubernetes Secrets
- Default development credentials MUST be changed before production deployment
- License files and secrets directories MUST be gitignored

**Input Validation & Injection Prevention**:
- All XML parsing MUST use `defusedxml` library (NOT standard `xml.etree.ElementTree`) to prevent XXE attacks, billion laughs, and quadratic blowup vulnerabilities (see `docs/tdr/001-defusedxml-for-secure-xml-parsing.md`)
- User input MUST be validated at API boundaries
- Database queries MUST use parameterized queries (Neo4j parameters, SQLAlchemy bound parameters)
- NEVER construct queries via string concatenation with user input

**Network Security**:
- Production MUST use HTTPS/TLS via reverse proxy (nginx or traefik)
- Internal service ports (Neo4j 7687, MinIO 9000, PostgreSQL 5432) MUST NOT be exposed publicly
- Docker networks MUST isolate services; only expose ports 80/443 through reverse proxy
- MinIO MUST use `MINIO_SECURE=true` in production

**Authentication & Authorization**:
- API authentication via bearer token (development: `DEV_TOKEN`, production: OAuth2/JWT)
- All API endpoints except health checks MUST require authentication
- P0 blockers for v1.0.0: implement RBAC and proper authorization

**Audit & Monitoring**:
- Security events (auth failures, 401/403 responses) MUST be logged
- Structured logging MUST be enabled for all services
- Credential rotation policy SHOULD be implemented (quarterly recommended)

**Static Analysis**:
- Bandit MUST be run for Python security scanning in CI
- Security warnings (e.g., B314 for unsafe XML) MUST be resolved, not suppressed with `# nosec`

**Rationale**: Defense-in-depth protects against multiple attack vectors. NIEM data often contains sensitive government information requiring strong security posture. Security vulnerabilities in XML processing are documented OWASP risks.

### VII. Performance Architecture

All code MUST follow performance-conscious design patterns:

**Async-First Design**:
- All API handlers MUST be async (`async def`) to maximize concurrent request handling
- I/O-bound operations (database queries, file operations, external APIs) MUST use async patterns
- Use `asyncio.gather()` for parallel independent operations
- Blocking operations MUST be offloaded to thread pools via `asyncio.to_thread()`

**Batch Processing with Controlled Concurrency** (see `docs/adr/001-batch-processing-architecture.md`):
- All batch operations MUST use `asyncio.Semaphore` for concurrency control
- System-wide concurrency limit via `BATCH_MAX_CONCURRENT_OPERATIONS` (default: 3)
- Operation-specific batch size limits:
  - Schema upload: `BATCH_MAX_SCHEMA_FILES` (default: 50)
  - XML/JSON conversion: `BATCH_MAX_CONVERSION_FILES` (default: 20)
  - XML/JSON ingestion: `BATCH_MAX_INGEST_FILES` (default: 20)
- Per-file timeout via `BATCH_OPERATION_TIMEOUT` (default: 60s)
- Error isolation: one file failure MUST NOT stop batch processing

**Graph Query Optimization**:
- Graph schema flattening SHOULD be used for analytics workloads to reduce relationship hops (see `docs/adr/002-graph-schema-design-flattening-strategy.md`)
- Neo4j queries MUST use indexes for frequently queried properties
- Avoid unbounded `MATCH (n) RETURN n` queries; always use `LIMIT` clause
- Use query parameters instead of string interpolation for query plan caching

**Resource Management**:
- Database connections MUST be pooled and reused
- Temporary files MUST be cleaned up after processing (use context managers)
- Large file uploads MUST stream to storage, not buffer in memory
- Docker containers MUST have resource limits in production

**CI/CD Performance Targets**:
- PR checks MUST complete in < 10 minutes for fast developer feedback
- Conditional job execution via path filtering to skip irrelevant tests
- Unit/integration tests run on PR; E2E tests run on main branch only

**Configuration Flexibility**:
- All performance-related limits MUST be configurable via environment variables
- Defaults MUST be safe for local development (conservative limits)
- Production deployments can increase limits based on available resources

**Rationale**: Predictable performance enables capacity planning and prevents resource exhaustion. Async patterns maximize throughput on I/O-bound workloads. Controlled concurrency protects local development environments while allowing production scaling.

## Technology Stack

**API**:
- Language: Python 3.11+
- Framework: FastAPI (async-native)
- Database: Neo4j (graph), PostgreSQL (Senzing entity resolution)
- Storage: MinIO (S3-compatible object storage)
- Testing: pytest, pytest-asyncio, pytest-cov
- Security: defusedxml, Bandit

**UI**:
- Framework: Next.js (React)
- Language: TypeScript
- Testing: vitest, @testing-library/react, MSW
- Styling: Tailwind CSS

**Infrastructure**:
- Container: Docker, Docker Compose
- CI/CD: GitHub Actions
- Reverse Proxy: nginx or traefik (production)

## Development Workflow

All feature development MUST follow this workflow:

1. **Branch**: Create feature branch from `main` using conventional naming (`feature/`, `fix/`, `docs/`)
2. **Develop**: Write tests first (when adding new functionality), implement, ensure tests pass
3. **Commit**: Use conventional commit messages; CI auto-bumps versions
4. **Review**: All changes require pull request review before merge
5. **Merge**: Squash merge to `main`; CI builds and tags Docker images

**Hot Reloading**: Development uses `docker-compose.override.yml` for automatic reload on code changes.

## Governance

This constitution supersedes all other development practices for this project.

**Amendment Process**:
1. Propose changes via pull request to `.specify/memory/constitution.md`
2. Document rationale for each change
3. Require team review and approval
4. Update version using semantic versioning (MAJOR for principle changes, MINOR for additions, PATCH for clarifications)

**Compliance**:
- All pull requests MUST verify compliance with these principles
- The `/speckit.plan` command includes a Constitution Check gate
- Violations MUST be documented in the Complexity Tracking section with justification

**Version**: 1.2.0 | **Ratified**: 2025-12-17 | **Last Amended**: 2025-12-17
