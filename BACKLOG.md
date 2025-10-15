# Production Readiness Backlog

**Repository:** NIEM Information Exchange - End-to-End PoC
**Goal:** Transform proof-of-concept into production-grade open source project
**Target Audience:** Government agencies, enterprises handling NIEM data exchanges

## Priority Definitions

| Priority | Definition | Timeline | Impact |
|----------|-----------|----------|--------|
| **P0** | **Blocker** - Cannot deploy to production without this | Week 1-2 | Legal/Security risk |
| **P1** | **Critical** - Required for production deployment | Week 3-4 | Security/Compliance |
| **P2** | **Important** - Production hardening and operations | Week 5-6 | Operations/Reliability |
| **P3** | **Nice-to-have** - Quality of life improvements | Week 7+ | Developer experience |

---

## P0: Blockers (Legal & Critical Security)

### P0.1 - Add LICENSE File
**Story:** As an open source contributor, I need to know the licensing terms before using or contributing to this codebase.

**Rationale:**
- **Legal blocker**: No LICENSE = no legal permission to use/modify/distribute
- GitHub shows "All rights reserved" without explicit license
- NIEM community typically uses Apache 2.0 (government-friendly)

**Acceptance Criteria:**
- [ ] LICENSE file in repository root
- [ ] Apache License 2.0 (recommended for government use)
- [ ] Copyright notice with year and organization
- [ ] NOTICE file if using third-party code (niem-cmf, niem-ndr)

**Effort:** 1 hour
**Dependencies:** None
**Files:** `LICENSE`, `NOTICE`

---

### P0.2 - Add SECURITY.md
**Story:** As a security researcher, I need a clear process for reporting vulnerabilities responsibly.

**Rationale:**
- **Security best practice**: CVE disclosure requires clear process
- GitHub Security tab requires this file
- Government agencies require vulnerability management policy

**Acceptance Criteria:**
- [ ] SECURITY.md with vulnerability disclosure policy
- [ ] Security contact email/form
- [ ] Response time SLA (e.g., 90 days for public disclosure)
- [ ] Supported versions table
- [ ] Link to security advisories page

**Effort:** 2 hours
**Dependencies:** None
**Files:** `SECURITY.md`

**Template:** GitHub security policy template

---

### P0.3 - Add CODE_OF_CONDUCT.md
**Story:** As a contributor, I need to understand community standards and expected behavior.

**Rationale:**
- **Community governance**: Required for healthy open source projects
- Reduces legal liability for maintainers
- Creates inclusive environment

**Acceptance Criteria:**
- [ ] CODE_OF_CONDUCT.md with enforcement policy
- [ ] Contributor Covenant 2.1 (industry standard)
- [ ] Contact method for violations
- [ ] Enforcement guidelines

**Effort:** 1 hour
**Dependencies:** None
**Files:** `CODE_OF_CONDUCT.md`

**Template:** https://www.contributor-covenant.org/

---

### P0.4 - Enable TLS/SSL for All Services
**Story:** As a security officer, I need all data in transit to be encrypted to meet compliance requirements.

**Rationale:**
- **Critical security gap**: Currently all traffic is plaintext
- NIEM exchanges often contain PII/sensitive data
- Compliance requirement (FedRAMP, FISMA, etc.)

**Current State:**
```yaml
# docker-compose.yml:49
MINIO_SECURE: "false"  # ❌ Plaintext HTTP

# docker-compose.yml:30
NEO4J_URI: bolt://neo4j:7687  # ❌ Unencrypted Bolt
```

**Acceptance Criteria:**
- [ ] Generate self-signed certs for dev (script in `scripts/generate-certs.sh`)
- [ ] Document production cert requirements (Let's Encrypt, corporate CA)
- [ ] Configure Neo4j with TLS (bolt+s:// protocol)
- [ ] Configure MinIO with TLS (MINIO_SECURE=true)
- [ ] Configure FastAPI with TLS (Uvicorn with certfile/keyfile)
- [ ] Update docker-compose.yml with TLS config
- [ ] Update .env.example with TLS variables
- [ ] Update README with certificate setup instructions

**Effort:** 8 hours
**Dependencies:** None (can use self-signed certs initially)
**Files:**
- `docker-compose.yml`
- `scripts/generate-certs.sh`
- `README.md` (certificate section)
- `.env.example`

**Risks:**
- Certificate management complexity in development
- Need to document cert rotation for production

---

### P0.5 - Add Secrets Management
**Story:** As a DevOps engineer, I need secrets stored securely, not in plaintext .env files.

**Rationale:**
- **Critical security gap**: Plaintext passwords in `.env.example`
- Secrets in source control risk (even if gitignored)
- Production requires external secrets management

**Current State:**
```bash
# .env.example - ❌ Plaintext secrets
NEO4J_PASSWORD=password
MINIO_ROOT_PASSWORD=minio123
DEV_TOKEN=devtoken
```

**Acceptance Criteria:**
- [ ] Support HashiCorp Vault integration (recommended)
- [ ] Support AWS Secrets Manager (cloud alternative)
- [ ] Support Kubernetes Secrets (K8s deployment)
- [ ] Document local dev mode (still uses .env but with warnings)
- [ ] Add secrets rotation documentation
- [ ] Update docker-compose.yml with secrets provider config
- [ ] Add example Vault policy HCL file
- [ ] Add startup script to fetch secrets on boot

**Effort:** 16 hours
**Dependencies:** None (provide multiple options)
**Files:**
- `api/src/niem_api/core/secrets.py` (new)
- `docker-compose.yml`
- `docs/SECRETS_MANAGEMENT.md` (new)
- `examples/vault-policy.hcl` (new)

**Implementation Notes:**
```python
# api/src/niem_api/core/secrets.py
class SecretsProvider:
    @staticmethod
    def get_provider():
        """Factory for secrets provider"""
        provider_type = os.getenv("SECRETS_PROVIDER", "env")
        if provider_type == "vault":
            return VaultSecretsProvider()
        elif provider_type == "aws":
            return AWSSecretsProvider()
        else:
            return EnvSecretsProvider()  # Fallback
```

---

## P1: Critical (Production Deployment Requirements)

### P1.1 - Replace Dev Token Auth with OAuth2/JWT
**Story:** As a system administrator, I need production-grade authentication with user management capabilities.

**Rationale:**
- **Security requirement**: Current "devtoken" is not production-safe
- Need user identity for audit logs
- Need token expiration and refresh
- Need integration with enterprise SSO

**Current State:**
```python
# api/src/niem_api/core/auth.py:10-19
def verify_token(credentials):
    expected_token = os.getenv("DEV_TOKEN", "devtoken")  # ❌ Static token
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401)
```

**Acceptance Criteria:**
- [ ] Support Auth0 (SaaS option)
- [ ] Support Keycloak (self-hosted option)
- [ ] Support custom OIDC provider
- [ ] JWT token validation with RS256 signing
- [ ] Token expiration and refresh flow
- [ ] Extract user claims (sub, email, name) for audit logs
- [ ] Update all endpoints to use new auth
- [ ] Backward-compatible dev mode with simple token
- [ ] Document auth provider setup in README

**Effort:** 24 hours
**Dependencies:** P0.5 (secrets management for client secrets)
**Files:**
- `api/src/niem_api/core/auth.py` (rewrite)
- `api/src/niem_api/core/oauth.py` (new)
- `api/src/niem_api/models/user.py` (new)
- `docs/AUTHENTICATION.md` (new)

**API Changes:**
```python
# Before
@app.post("/api/ingest/xml")
async def ingest_xml(token: str = Depends(verify_token)):
    ...

# After
@app.post("/api/ingest/xml")
async def ingest_xml(user: User = Depends(get_current_user)):
    # user.id, user.email, user.roles available
    ...
```

---

### P1.2 - Implement RBAC (Role-Based Access Control)
**Story:** As an administrator, I need to control who can upload schemas, ingest data, or view graphs.

**Rationale:**
- **Security requirement**: Not all users should have admin access
- Multi-tenant deployments need isolation
- Compliance requires access controls (NIST 800-53 AC-2)

**Role Definitions:**
| Role | Permissions |
|------|-------------|
| **admin** | All operations, user management, system reset |
| **schema_manager** | Upload/manage schemas, no data access |
| **data_ingestor** | Ingest data, query own data |
| **viewer** | Read-only graph queries |
| **auditor** | Read audit logs only |

**Acceptance Criteria:**
- [ ] Role definitions in database/config
- [ ] Permission decorators for endpoints
- [ ] Role assignment via JWT claims or database
- [ ] Tenant isolation (optional, for multi-tenant)
- [ ] Admin API for role management
- [ ] Document permission matrix

**Effort:** 32 hours
**Dependencies:** P1.1 (OAuth2/JWT auth)
**Files:**
- `api/src/niem_api/core/rbac.py` (new)
- `api/src/niem_api/models/role.py` (new)
- `api/src/niem_api/handlers/user_management.py` (new)
- `docs/RBAC.md` (new)

**Implementation:**
```python
# api/src/niem_api/core/rbac.py
def require_roles(*roles):
    """Decorator to enforce role-based access"""
    def decorator(func):
        @wraps(func)
        async def wrapper(user: User = Depends(get_current_user), *args, **kwargs):
            if not any(role in user.roles for role in roles):
                raise HTTPException(403, "Insufficient permissions")
            return await func(user=user, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@app.post("/api/schema/upload")
@require_roles("admin", "schema_manager")
async def upload_schema(user: User):
    ...
```

---

### P1.3 - Add Comprehensive Audit Logging
**Story:** As a compliance officer, I need complete audit trails of who accessed what data and when.

**Rationale:**
- **Compliance requirement**: NIST 800-53 AU-2, GDPR Article 30
- Government agencies require audit logs
- Security incident investigation
- User behavior analytics

**Acceptance Criteria:**
- [ ] Structured audit log format (JSON)
- [ ] Log to dedicated audit stream (separate from app logs)
- [ ] Capture: timestamp, user_id, action, resource, result, IP, user_agent
- [ ] Log retention policy (7 years for government)
- [ ] Immutable audit log storage
- [ ] Audit log query API
- [ ] Document audit events in AUDIT_EVENTS.md

**Audit Events:**
- `schema.uploaded`, `schema.activated`, `schema.deleted`
- `data.ingested`, `data.queried`, `data.exported`
- `user.login`, `user.logout`, `user.role_changed`
- `system.reset`, `system.backup`

**Effort:** 16 hours
**Dependencies:** P1.1 (user identity from auth)
**Files:**
- `api/src/niem_api/core/audit.py` (new)
- `api/src/niem_api/handlers/audit_log.py` (new)
- `docs/AUDIT_EVENTS.md` (new)

**Implementation:**
```python
# api/src/niem_api/core/audit.py
import structlog

audit_logger = structlog.get_logger("audit")

def audit_event(action: str, resource: str, result: str):
    """Decorator to audit API operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(user: User, *args, **kwargs):
            try:
                response = await func(user=user, *args, **kwargs)
                audit_logger.info(
                    action,
                    user_id=user.id,
                    resource=resource,
                    result="success",
                    timestamp=datetime.utcnow().isoformat()
                )
                return response
            except Exception as e:
                audit_logger.error(
                    action,
                    user_id=user.id,
                    resource=resource,
                    result="failure",
                    error=str(e)
                )
                raise
        return wrapper
    return decorator
```

---

### P1.4 - Implement Rate Limiting
**Story:** As a platform operator, I need to prevent DoS attacks and ensure fair resource usage.

**Rationale:**
- **Security requirement**: Prevent abuse and resource exhaustion
- Cost control (Neo4j queries can be expensive)
- Fair usage in multi-tenant environments

**Rate Limit Strategy:**
| Endpoint | Limit | Window | Rationale |
|----------|-------|--------|-----------|
| `/api/schema/upload` | 10 | 1 hour | Schema uploads are heavy |
| `/api/ingest/xml` | 100 | 1 hour | Data ingestion is expensive |
| `/api/graph/query` | 1000 | 1 hour | Query rate for normal use |
| `/api/admin/reset` | 5 | 1 day | Dangerous operation |

**Acceptance Criteria:**
- [ ] Per-user rate limiting (by user_id from JWT)
- [ ] Per-IP rate limiting (fallback for unauthenticated)
- [ ] Per-endpoint configurable limits
- [ ] Redis-backed rate limit storage
- [ ] Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining)
- [ ] 429 error response with retry-after header
- [ ] Admin override capability
- [ ] Rate limit metrics

**Effort:** 12 hours
**Dependencies:** P1.1 (user identity)
**Files:**
- `api/src/niem_api/core/rate_limit.py` (new)
- `docker-compose.yml` (add Redis service)
- `docs/RATE_LIMITING.md` (new)

**Implementation:**
```python
# Use slowapi (FastAPI rate limiting library)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/schema/upload")
@limiter.limit("10/hour")
async def upload_schema(...):
    ...
```

---

### P1.5 - Security Audit: Input Sanitization
**Story:** As a security engineer, I need confidence that all user inputs are properly sanitized.

**Rationale:**
- **Security requirement**: Prevent injection attacks
- High-risk areas: Cypher query generation, file upload processing
- CLAUDE.md mentions parameterization but needs verification

**Audit Scope:**
1. **Cypher Injection:**
   - `api/src/niem_api/services/domain/xml_to_graph/converter.py`
   - `api/src/niem_api/services/domain/json_to_graph/converter.py`
   - All uses of Neo4j query builder

2. **Path Traversal:**
   - File upload handlers (schema upload, data ingestion)
   - MinIO object path construction

3. **XSS:**
   - API error messages returned to client
   - Graph visualization data

**Acceptance Criteria:**
- [ ] Audit report documenting all input points
- [ ] Verify all Cypher queries use parameterization (no string interpolation)
- [ ] Add schema validation for all API inputs (Pydantic models)
- [ ] Add filename sanitization for uploads
- [ ] Add content-type validation for uploads
- [ ] Add max file size limits
- [ ] Document security assumptions in SECURITY_DESIGN.md

**Effort:** 16 hours
**Dependencies:** None
**Files:**
- `docs/SECURITY_AUDIT_REPORT.md` (new)
- `docs/SECURITY_DESIGN.md` (new)
- Various files (fixes as needed)

**High-Risk Code to Audit:**
```python
# api/src/niem_api/services/domain/xml_to_graph/converter.py
# Line 800+ - Cypher generation
# VERIFY: All values in f-strings are properly escaped

# api/src/niem_api/handlers/ingest.py
# File path handling - check for path traversal
```

---

## P2: Important (Production Hardening)

### P2.1 - Implement PII Detection and Classification
**Story:** As a privacy officer, I need automatic detection of PII in ingested data.

**Rationale:**
- **Compliance requirement**: GDPR, CCPA require PII tracking
- NIEM exchanges commonly contain PII (names, SSN, addresses)
- Need to identify data for retention/deletion policies

**Acceptance Criteria:**
- [ ] Detect PII patterns in property values (regex, NLP)
- [ ] Tag Neo4j nodes with PII classification
- [ ] Log PII access in audit trail
- [ ] Support custom PII detection rules per schema
- [ ] Generate PII inventory report

**Effort:** 40 hours
**Dependencies:** P1.3 (audit logging)
**Files:**
- `api/src/niem_api/services/pii_detector.py` (new)
- `docs/PII_DETECTION.md` (new)

---

### P2.2 - Add Prometheus Metrics
**Story:** As a DevOps engineer, I need operational metrics for monitoring and alerting.

**Rationale:**
- **Operational requirement**: Can't manage what you can't measure
- Need to detect issues before users report them
- Capacity planning and performance optimization

**Metrics to Expose:**
- Request counts (by endpoint, status code)
- Request latency (p50, p95, p99)
- Neo4j query latency
- MinIO operation latency
- Schema upload success/failure rate
- Data ingestion throughput (docs/sec)
- Graph size (node count, relationship count)
- Cache hit rates

**Acceptance Criteria:**
- [ ] `/metrics` endpoint with Prometheus format
- [ ] FastAPI instrumentation (requests, latency)
- [ ] Custom business metrics (schemas, ingestions)
- [ ] Neo4j metrics (query time, connection pool)
- [ ] MinIO metrics (upload size, duration)
- [ ] Example Grafana dashboard JSON
- [ ] Example Prometheus alerting rules

**Effort:** 16 hours
**Dependencies:** None
**Files:**
- `api/src/niem_api/core/metrics.py` (new)
- `examples/grafana-dashboard.json` (new)
- `examples/prometheus-alerts.yml` (new)

---

### P2.3 - Implement Correlation IDs
**Story:** As a support engineer, I need to trace requests across API, Neo4j, and MinIO.

**Rationale:**
- **Operational requirement**: Troubleshooting distributed systems
- Already mentioned in CLAUDE.md but not implemented
- Link logs across services for single request

**Acceptance Criteria:**
- [ ] Generate correlation_id for each request (UUID)
- [ ] Pass correlation_id to Neo4j (as query comment)
- [ ] Pass correlation_id to MinIO (as metadata)
- [ ] Include correlation_id in all log entries
- [ ] Return correlation_id in error responses (X-Correlation-ID header)
- [ ] Document correlation_id usage in TROUBLESHOOTING.md

**Effort:** 8 hours
**Dependencies:** None
**Files:**
- `api/src/niem_api/core/correlation.py` (new)
- `api/src/niem_api/core/logging.py` (update)
- `docs/TROUBLESHOOTING.md` (new)

---

### P2.4 - Make Security Scanning Blocking
**Story:** As a security engineer, I need to prevent vulnerable code from being merged.

**Rationale:**
- **Security best practice**: Shift-left security
- Currently Trivy is non-blocking (line 158: `continue-on-error: true`)
- Should fail builds on HIGH/CRITICAL vulnerabilities

**Acceptance Criteria:**
- [ ] Change Trivy to blocking in `.github/workflows/main-pipeline.yml`
- [ ] Set severity threshold to HIGH and above
- [ ] Add exception process for false positives (security waiver file)
- [ ] Document security scanning in CONTRIBUTING.md

**Effort:** 4 hours
**Dependencies:** None
**Files:**
- `.github/workflows/main-pipeline.yml`
- `.trivyignore` (new, for waivers)
- `CONTRIBUTING.md`

---

### P2.5 - Enable Dependabot
**Story:** As a maintainer, I need automated PR creation for dependency updates.

**Rationale:**
- **Security best practice**: Stay up-to-date on security patches
- Reduces manual effort for dependency updates
- GitHub native, zero infrastructure

**Acceptance Criteria:**
- [ ] Create `.github/dependabot.yml`
- [ ] Enable for Python (pip)
- [ ] Enable for Node.js (npm)
- [ ] Enable for Docker (base images)
- [ ] Enable for GitHub Actions
- [ ] Set weekly update schedule
- [ ] Group non-security updates

**Effort:** 2 hours
**Dependencies:** None
**Files:**
- `.github/dependabot.yml` (new)

---

### P2.6 - Enhanced Health Checks
**Story:** As a load balancer, I need to know when the API is ready to serve traffic.

**Rationale:**
- **Operational requirement**: Kubernetes readiness/liveness probes
- Current `/healthz` is basic
- Need dependency status (Neo4j, MinIO)

**Acceptance Criteria:**
- [ ] `/healthz` - Overall health (200 OK or 503 Service Unavailable)
- [ ] `/livez` - Liveness probe (is process alive?)
- [ ] `/readyz` - Readiness probe (can accept traffic?)
- [ ] Check Neo4j connectivity
- [ ] Check MinIO connectivity
- [ ] Return JSON with dependency status
- [ ] Cache checks (don't check on every request)

**Effort:** 8 hours
**Dependencies:** None
**Files:**
- `api/src/niem_api/handlers/health.py` (new)
- `api/src/niem_api/main.py` (add endpoints)

---

### P2.7 - Neo4j Backup Strategy
**Story:** As a database administrator, I need automated backups with point-in-time recovery.

**Rationale:**
- **Critical operational requirement**: Data loss prevention
- Currently no backup documented
- Graph data is difficult to reconstruct

**Acceptance Criteria:**
- [ ] Automated daily Neo4j dumps
- [ ] Export to S3/MinIO
- [ ] Retention policy (30 daily, 12 monthly)
- [ ] Document restore procedure
- [ ] Test restore process
- [ ] Backup monitoring (alert on failure)

**Effort:** 16 hours
**Dependencies:** None
**Files:**
- `scripts/backup-neo4j.sh` (new)
- `scripts/restore-neo4j.sh` (new)
- `docs/BACKUP_RESTORE.md` (new)

---

### P2.8 - MinIO Backup Strategy
**Story:** As a storage administrator, I need schema and data files backed up securely.

**Rationale:**
- **Critical operational requirement**: Schema loss = system unusable
- MinIO data is source of truth for schemas
- Need disaster recovery plan

**Acceptance Criteria:**
- [ ] MinIO replication to secondary instance (or S3)
- [ ] Versioning enabled on buckets
- [ ] Retention policy documented
- [ ] Document restore procedure
- [ ] Test restore process

**Effort:** 12 hours
**Dependencies:** None
**Files:**
- `docker-compose.yml` (MinIO replication config)
- `docs/BACKUP_RESTORE.md` (update)

---

## P3: Nice-to-Have (Quality of Life)

### P3.1 - API Versioning Strategy
**Story:** As an API consumer, I need versioning so updates don't break my integration.

**Effort:** 12 hours
**Files:** `api/src/niem_api/main.py`, `docs/API_VERSIONING.md`

---

### P3.2 - Circuit Breakers
**Story:** As a resilience engineer, I need circuit breakers to prevent cascading failures.

**Effort:** 16 hours
**Files:** `api/src/niem_api/clients/` (update all clients)

---

### P3.3 - Data Retention Policies
**Story:** As a compliance officer, I need automated data deletion after retention period.

**Effort:** 24 hours
**Files:** `api/src/niem_api/services/retention.py`, cron jobs

---

### P3.4 - CHANGELOG.md
**Story:** As a user, I need to know what changed in each release.

**Effort:** 4 hours
**Files:** `CHANGELOG.md`, CI automation

---

### P3.5 - CORS Audit
**Story:** As a security engineer, I need production CORS configuration audited.

**Effort:** 4 hours
**Files:** `api/src/niem_api/main.py`, `docs/CORS_CONFIG.md`

---

### P3.6 - OpenTelemetry Tracing
**Story:** As a performance engineer, I need distributed tracing for request optimization.

**Effort:** 24 hours
**Files:** `api/src/niem_api/core/tracing.py`, Jaeger setup

---

### P3.7 - Production Deployment Guide
**Story:** As a DevOps engineer, I need Kubernetes deployment manifests.

**Effort:** 40 hours
**Files:** `k8s/`, `helm/`, `docs/DEPLOYMENT.md`

---

### P3.8 - Performance Testing
**Story:** As a performance engineer, I need load testing for capacity planning.

**Effort:** 32 hours
**Files:** `tests/performance/`, CI integration

---

### P3.9 - UI Error Boundaries
**Story:** As a user, I need graceful error handling in the UI.

**Effort:** 8 hours
**Files:** `ui/src/components/ErrorBoundary.tsx`

---

## Summary Statistics

| Priority | Items | Estimated Effort | Critical Path |
|----------|-------|------------------|---------------|
| P0 | 5 | 48 hours (~1.5 weeks) | Week 1-2 |
| P1 | 5 | 100 hours (~3 weeks) | Week 3-5 |
| P2 | 8 | 106 hours (~3 weeks) | Week 6-8 |
| P3 | 9 | 164 hours (~4 weeks) | Week 9-12 |
| **Total** | **27** | **418 hours (~10 weeks)** | **Q1 2024** |

## Implementation Roadmap

### Sprint 1-2 (Weeks 1-2): Legal & Critical Security
- P0.1 - LICENSE
- P0.2 - SECURITY.md
- P0.3 - CODE_OF_CONDUCT.md
- P0.4 - TLS/SSL
- P0.5 - Secrets Management

**Outcome:** Repository legally safe and basic security hardened

---

### Sprint 3-4 (Weeks 3-4): Authentication & Authorization
- P1.1 - OAuth2/JWT
- P1.2 - RBAC
- P1.3 - Audit Logging

**Outcome:** Production-grade auth and compliance logging

---

### Sprint 5-6 (Weeks 5-6): Security & Observability
- P1.4 - Rate Limiting
- P1.5 - Security Audit
- P2.2 - Prometheus Metrics
- P2.3 - Correlation IDs

**Outcome:** Secure and observable system

---

### Sprint 7-8 (Weeks 7-8): Operations & Reliability
- P2.1 - PII Detection
- P2.4 - Blocking Security Scans
- P2.5 - Dependabot
- P2.6 - Enhanced Health Checks
- P2.7 - Neo4j Backups
- P2.8 - MinIO Backups

**Outcome:** Production-ready operations

---

### Sprint 9+ (Weeks 9+): Quality of Life
- P3.1 through P3.9 as time permits

**Outcome:** Developer experience improvements

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| OAuth2 integration complexity | High | High | Start with Auth0 (simpler), document Keycloak alternative |
| TLS certificate management | Medium | Medium | Use self-signed for dev, document prod requirements |
| Performance regression from auth/RBAC | Medium | Medium | Benchmark and cache auth decisions |
| Backup restore never tested | High | Critical | Schedule quarterly DR drills |
| PII detection false positives | Medium | Medium | Allow custom rules, manual override |

---

## Dependencies Between Items

```
P0.5 (Secrets) → P1.1 (OAuth2)
P1.1 (OAuth2) → P1.2 (RBAC)
P1.2 (RBAC) → P1.3 (Audit)
P1.3 (Audit) → P2.1 (PII Detection)

All items → Documentation updates in README.md
```

---

## Success Metrics

After completing this backlog:
- [ ] Pass OpenSSF Best Practices badge (https://bestpractices.coreinfrastructure.org/)
- [ ] Zero HIGH/CRITICAL Trivy vulnerabilities
- [ ] <1% API error rate in production
- [ ] <500ms p95 latency for ingestion
- [ ] 99.5% uptime SLA
- [ ] Zero data loss incidents
- [ ] Successful disaster recovery drill
