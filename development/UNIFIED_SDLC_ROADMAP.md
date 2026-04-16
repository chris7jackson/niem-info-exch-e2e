# Unified SDLC Expansion and Production Roadmap

**Created:** 2026-03-04
**Status:** Active
**Source:** Merges [EXPANSION_PLAN.md](EXPANSION_PLAN.md) (architecture/features) with [../BACKLOG.md](../BACKLOG.md) (production readiness)

---

## How this plan works

- **Features** are discrete deliverables. Each feature is delivered in isolation using the same SDLC: **Plan -> Design -> Build -> Test -> Deploy**.
- **Validation** at each step is explicit: no phase is considered complete until its validation is done.
- You execute **one feature at a time**; after Deploy you move to the next feature. Dependencies determine order.

### SDLC phase definitions and validation

| Phase | Purpose | Validation (gate to next phase) |
|-------|---------|----------------------------------|
| **Plan** | Scope, acceptance criteria, dependencies, risks, success criteria | Written scope doc or checklist agreed; dependencies and order clear |
| **Design** | Technical approach: interfaces, APIs, file changes, ADR if needed | Design doc or ADR reviewed; implementation path clear |
| **Build** | Implement code and config changes | Code complete; linters/static checks pass; no known regressions |
| **Test** | Unit, integration, and manual checks against acceptance criteria | All tests pass; acceptance criteria verified; rollback approach known |
| **Deploy** | Integrate into mainline and run in target environment | Feature works in target env; docs updated; change visible to users/ops as intended |

"Deploy" here means: merge to main (or release branch), and optionally deploy to a dev/staging environment. For some features (e.g. CODE_OF_CONDUCT) it is just "file merged and visible in repo."

### Feature file convention

Each feature gets its own file under `development/features/` named `FNN-short-name.md` (e.g. `F01-code-of-conduct.md`). That file is created from `development/templates/FEATURE_TEMPLATE.md` and tracks the feature through all five SDLC phases with checklists.

---

## Already done (no work in this roadmap)

- P0.1 LICENSE (Apache 2.0 at repo root)
- P0.2 SECURITY.md (present at repo root)
- NOTICE file (third-party attribution)
- Basic `/healthz` and `/readyz` in `api/src/niem_api/main.py`

---

## Feature list and suggested order

### Tier 1 -- Foundation and first SDLC run

**F1 -- CODE_OF_CONDUCT (P0.3)**

- **Scope:** Add Contributor Covenant 2.1, enforcement and contact.
- **Dependencies:** None.
- **SDLC:** Plan (accept BACKLOG acceptance criteria) -> Design (template choice, contact method) -> Build (add `CODE_OF_CONDUCT.md`) -> Test (reviewer check) -> Deploy (merge).
- **Validation:** File present; linked from README or CONTRIBUTING; BACKLOG P0.3 criteria met.

**F2 -- Graph client abstraction (Expansion)**

- **Scope:** Define `GraphClient` protocol; Neo4j implements it; DI in `api/src/niem_api/core/dependencies.py`; refactor ingest, graph, entity_resolution, admin, schema_manager, settings_service to use injected client; add `run_transaction(statements)` so ingest no longer touches `neo4j_client.driver`.
- **Dependencies:** None.
- **SDLC:** Plan (scope from `development/EXPANSION_PLAN.md` sections 3 and 3.4) -> Design (ADR + protocol and method list; list of call sites to change) -> Build (protocol, Neo4j impl, DI, refactors) -> Test (unit with fake client; existing integration tests still pass) -> Deploy (merge; default backend remains Neo4j).
- **Validation:** No direct `Neo4jClient` or `driver` in handlers/services; one place to swap backend (config + factory).

---

### Tier 2 -- Capability (expansion)

**F3 -- Batch upload (ADR-001 to ingest)**

- **Scope:** Apply `docs/adr/001-batch-processing-architecture.md` to XML/JSON ingest: shared semaphore, `BatchConfig` limits, optional `asyncio.gather` for limited concurrency; per-file errors; timeouts.
- **Dependencies:** None (optional: F2 so ingest uses abstract client).
- **SDLC:** Plan (confirm ADR limits and semaphore value) -> Design (where semaphore lives; how gather is used; env vars) -> Build (ingest + config) -> Test (multi-file ingest; failure of one file; timeout) -> Deploy (merge; document env vars).
- **Validation:** Ingest respects batch limits and concurrency; no resource exhaustion under load.

**F4 -- Performance: caching and concurrency**

- **Scope:** Cache mapping.yaml (and optionally CMF/element-tree) per schema_id in memory with invalidation on schema update; reuse existing batch concurrency where applicable; optional bulk Cypher (e.g. UNWIND) for ingest.
- **Dependencies:** F2 recommended (so cache and bulk run through abstract client).
- **SDLC:** Plan (which artifacts to cache; TTL/invalidation; bulk strategy) -> Design (cache key/scope; where cache lives; API for invalidation) -> Build (cache layer; optional bulk path) -> Test (cache hit/miss; invalidation; correctness) -> Deploy (merge; monitor latency).
- **Validation:** Fewer MinIO round-trips for repeated schema use; optional bulk improves ingest throughput.

**F5 -- Schema tinkering**

- **Scope:** Multi-schema UX (compare, switch context); configurable `BATCH_MAX_SCHEMA_FILES`; optional "copy schema" (clone schema_id + designs).
- **Dependencies:** None.
- **SDLC:** Plan (BACKLOG/EXPANSION scope; copy semantics) -> Design (API for copy; UI flows; config) -> Build (API + UI + config) -> Test (upload/copy/activate; limits) -> Deploy (merge).
- **Validation:** Users can copy a schema and experiment without losing original; limits configurable.

**F6 -- Graph modeling extensions**

- **Scope:** Extend mapping spec (e.g. optional indexes, relationship properties); schema designer: multiple named designs per schema; align `api/src/niem_api/services/domain/graph/schema_manager.py` with mapping.
- **Dependencies:** F2 (schema_manager uses abstract client).
- **SDLC:** Plan (list of mapping extensions; design naming) -> Design (mapping schema; storage of multiple designs) -> Build (mapping + converters + designer + schema_manager) -> Test (round-trip; multiple designs) -> Deploy (merge).
- **Validation:** Multiple designs per schema; mapping-driven indexes where supported.

---

### Tier 3 -- Production readiness (infra and security baseline)

**F7 -- TLS for all services (P0.4)**

- **Scope:** Self-signed certs for dev; Neo4j bolt+s, MinIO TLS, FastAPI TLS; docs and `.env.example`.
- **Dependencies:** None.
- **SDLC:** Plan (BACKLOG P0.4 criteria; dev vs prod) -> Design (cert layout; compose changes) -> Build (scripts, compose, app config) -> Test (curl/UI over HTTPS; Neo4j/MinIO TLS) -> Deploy (merge; document cert rotation).
- **Validation:** All client-server traffic in scope uses TLS in configured env.

**F8 -- Secrets management (P0.5)**

- **Scope:** Support Vault and/or AWS Secrets Manager and K8s Secrets; keep .env for dev with warnings; docs and example policy.
- **Dependencies:** None.
- **SDLC:** Plan (BACKLOG P0.5; which providers first) -> Design (SecretsProvider interface; env vars; startup flow) -> Build (e.g. `api/src/niem_api/core/secrets.py`, compose, docs) -> Test (dev .env; optional Vault or mock) -> Deploy (merge; document).
- **Validation:** Production can use external secrets; dev still works with .env.

**F9 -- Blocking security scans and Dependabot (P2.4, P2.5)**

- **Scope:** Trivy blocking in `.github/workflows/main-pipeline.yml`; severity threshold; `.trivyignore`; `.github/dependabot.yml` for pip, npm, Docker, Actions.
- **Dependencies:** None.
- **SDLC:** Plan (BACKLOG P2.4/P2.5) -> Design (threshold; dependabot groups) -> Build (workflow, .trivyignore, dependabot.yml, CONTRIBUTING) -> Test (trigger pipeline; verify block on critical) -> Deploy (merge).
- **Validation:** HIGH/CRITICAL unwaived fail build; Dependabot PRs created.

**F10 -- Health checks formalization (P2.6)**

- **Scope:** Add `/livez`; ensure `/healthz` and `/readyz` return JSON with dependency status; optional caching; optional `api/src/niem_api/handlers/health.py`.
- **Dependencies:** None.
- **SDLC:** Plan (BACKLOG P2.6; K8s probe semantics) -> Design (response shape; cache TTL) -> Build (endpoints; cache if needed) -> Test (probes; failure behavior) -> Deploy (merge).
- **Validation:** Orchestrators can use livez/readyz; dependency status accurate.

---

### Tier 4 -- Auth and compliance

**F11 -- OAuth2/JWT (P1.1)**

- **Scope:** Replace dev token with JWT validation; support Auth0 or Keycloak or custom OIDC; user claims for audit; dev-mode fallback.
- **Dependencies:** F8 (secrets for client secrets).
- **SDLC:** Plan (BACKLOG P1.1; provider choice) -> Design (auth flow; token validation; user model) -> Build (auth layer; endpoints) -> Test (unit + integration with mock OIDC) -> Deploy (merge; document).
- **Validation:** Production can use OIDC; dev mode still works; user identity available.

**F12 -- RBAC (P1.2)**

- **Scope:** Roles (admin, schema_manager, data_ingestor, viewer, auditor); permission decorators; role from JWT or DB.
- **Dependencies:** F11.
- **SDLC:** Plan (BACKLOG P1.2; role matrix) -> Design (rbac module; decorators; storage) -> Build (rbac, role checks on routes) -> Test (each role; forbidden cases) -> Deploy (merge).
- **Validation:** Endpoints enforce roles; permission matrix documented.

**F13 -- Audit logging (P1.3)**

- **Scope:** Structured audit log; events (schema, data, user, system); dedicated stream; retention note.
- **Dependencies:** F11 (user identity).
- **SDLC:** Plan (BACKLOG P1.3; event list) -> Design (format; transport; storage) -> Build (audit module; instrumentation) -> Test (events emitted; no PII leak) -> Deploy (merge).
- **Validation:** Key actions produce audit records; query API if required.

**F14 -- Rate limiting (P1.4)**

- **Scope:** Per-user and per-IP limits; configurable per endpoint; Redis or in-memory; 429 and headers.
- **Dependencies:** F11 (user identity for per-user).
- **SDLC:** Plan (BACKLOG P1.4; limits table) -> Design (middleware; storage; config) -> Build (rate_limit module; apply to routes) -> Test (throttling; headers) -> Deploy (merge).
- **Validation:** Limits enforced; 429 and headers correct.

**F15 -- Security audit and input sanitization (P1.5)**

- **Scope:** Audit Cypher, path traversal, XSS; parameterization and validation; max file size; SECURITY_DESIGN.md and audit report.
- **Dependencies:** None.
- **SDLC:** Plan (BACKLOG P1.5; scope of audit) -> Design (fixes; validation points) -> Build (fixes; docs) -> Test (regression tests for injection) -> Deploy (merge).
- **Validation:** Audit report exists; high-risk areas mitigated.

---

### Tier 5 -- Operations and observability

**F16 -- Observability (P2.2, P2.3)**

- **Scope:** Prometheus `/metrics`; correlation_id per request; pass-through to graph DB and MinIO; TROUBLESHOOTING.md.
- **Dependencies:** F2 (correlation in graph client).
- **SDLC:** Plan (BACKLOG P2.2/P2.3; metric list) -> Design (metric names; correlation propagation) -> Build (metrics; correlation middleware) -> Test (metrics exposed; correlation in logs) -> Deploy (merge).
- **Validation:** Metrics scrapeable; requests traceable by correlation_id.

**F17 -- Graph DB backup strategy (P2.7)**

- **Scope:** Automated backups of graph DB (Neo4j or abstract backend); export to S3/MinIO; retention; restore doc and test.
- **Dependencies:** F2 (so backup is backend-aware or generic).
- **SDLC:** Plan (BACKLOG P2.7; retention) -> Design (script; schedule; storage path) -> Build (scripts, docs) -> Test (backup + restore) -> Deploy (merge; enable in target env).
- **Validation:** Restore tested; retention and alerts documented.

**F18 -- MinIO backup strategy (P2.8)**

- **Scope:** Versioning and/or replication; retention; restore procedure and doc.
- **Dependencies:** None.
- **SDLC:** Plan (BACKLOG P2.8) -> Design (versioning vs replication) -> Build (config, docs) -> Test (restore test) -> Deploy (merge).
- **Validation:** Restore procedure works; retention documented.

---

### Tier 6 -- Optional / later

**F19 -- New DB provider adapter (Expansion)**

- **Scope:** Implement GraphClient for one of TuringDB or LadybugDB; config switch; compose profile; docs (including Cypher compatibility).
- **Dependencies:** F2.
- **SDLC:** Plan (which provider; compatibility matrix) -> Design (adapter API; config) -> Build (adapter; compose; docs) -> Test (integration tests with that backend) -> Deploy (merge; optional profile).
- **Validation:** Can run app against alternate backend with config change.

**F20 -- PII detection (P2.1)**

- **Scope:** Detect and tag PII; optional audit integration; PII report.
- **Dependencies:** F13 (audit).
- **SDLC:** Plan -> Design -> Build -> Test -> Deploy.
- **Validation:** PII tagged; report and audit hook if required.

Additional BACKLOG P3 items (API versioning, circuit breakers, retention, CHANGELOG, CORS audit, OpenTelemetry, K8s guide, performance tests, UI error boundaries) can be added as F21+ using the same SDLC and dependency order from BACKLOG.

---

## Dependency graph

```
F1 (CODE_OF_CONDUCT) -----> no dependencies
F2 (Graph abstraction) ---> no dependencies

F3 (Batch upload) --------> optional F2
F4 (Performance) ---------> recommended F2
F5 (Schema tinkering) ----> no dependencies
F6 (Graph modeling) ------> F2

F7 (TLS) -----------------> no dependencies
F8 (Secrets) --------------> no dependencies
F9 (Security scans) ------> no dependencies
F10 (Health checks) ------> no dependencies

F11 (OAuth2/JWT) ---------> F8
F12 (RBAC) ---------------> F11
F13 (Audit logging) ------> F11
F14 (Rate limiting) ------> F11
F15 (Security audit) -----> no dependencies

F16 (Observability) ------> F2
F17 (Graph DB backup) ----> F2
F18 (MinIO backup) -------> no dependencies

F19 (New DB adapter) -----> F2
F20 (PII detection) ------> F13
```

---

## Execution model

- **One feature at a time:** Complete Plan -> Design -> Build -> Test -> Deploy for feature N (including validation at each step) before starting feature N+1.
- **Track state per feature:** Each feature has its own file under `development/features/` (created from `development/templates/FEATURE_TEMPLATE.md`) with phase checklists and validation notes.
- **Track overall state:** `development/ROADMAP_STATUS.md` shows all 20 features at a glance with current phase and date.
- **Reordering:** You can do Tier 1-2 (F1-F6) in any order that respects noted dependencies. F7-F10 can follow or run in parallel with F3-F6 if you want the production baseline earlier. F11+ follow BACKLOG dependency chain (F8 -> F11 -> F12, F13, F14; F13 -> F20).

---

## Related documents

- **Expansion scope and rationale:** [EXPANSION_PLAN.md](EXPANSION_PLAN.md) (especially sections 3 and 3.4 for graph abstraction)
- **Production criteria per item:** [../BACKLOG.md](../BACKLOG.md) (P0-P3)
- **Feature tracking:** [ROADMAP_STATUS.md](ROADMAP_STATUS.md)
- **Feature template:** [templates/FEATURE_TEMPLATE.md](templates/FEATURE_TEMPLATE.md)
- **Individual features:** `features/F01-code-of-conduct.md`, `features/F02-graph-client-abstraction.md`, etc.
