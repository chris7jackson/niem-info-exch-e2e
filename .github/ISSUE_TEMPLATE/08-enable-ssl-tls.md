---
name: Enable SSL/TLS for all services
about: Configure HTTPS/TLS for API, Neo4j, and MinIO
title: 'Enable SSL/TLS for all services (HTTPS, Bolt+S, MinIO TLS)'
labels: security, p0, infrastructure, production
assignees: ''
---

## Problem Statement

Currently, ALL services communicate over unencrypted protocols:
- **API**: HTTP (port 8000)
- **Neo4j**: Bolt (port 7687) - no TLS
- **MinIO**: HTTP (ports 9000, 9001) - no TLS
- **UI**: HTTP (port 3000)

This is documented in `SECURITY.md` as a known limitation but is **critical for any production deployment**.

## User Value

- **Security**: Protect data in transit from eavesdropping
- **Compliance**: Required for FISMA, FedRAMP, HIPAA
- **Trust**: Industry standard for web services
- **Authentication**: Prerequisite for client certificates

## Scope

Enable TLS 1.2+ for all inter-service and external communication:
1. **FastAPI** (ui/src/lib/api.ts) → HTTPS
2. **Neo4j** → Bolt+S with TLS
3. **MinIO** → HTTPS with TLS
4. **UI** → Served over HTTPS

## Acceptance Criteria

### API (FastAPI)
- [ ] API runs with TLS enabled (HTTPS on port 8443 or 443)
- [ ] Certificate configured (self-signed for dev, real cert for prod)
- [ ] HTTP→HTTPS redirect enabled
- [ ] TLS 1.2+ only (no SSLv3, TLS 1.0, TLS 1.1)
- [ ] Strong cipher suites configured
- [ ] HSTS headers enabled

### Neo4j
- [ ] Bolt+S enabled (Neo4j TLS/SSL)
- [ ] Certificate configured for Neo4j
- [ ] Connection string updated: `bolt+s://` or `neo4j+s://`
- [ ] Python driver configured with SSL context
- [ ] Verify certificate validation works

### MinIO
- [ ] MinIO runs with TLS enabled (HTTPS)
- [ ] Certificate configured for MinIO
- [ ] Python client configured with `secure=True`
- [ ] S3 client validates certificates
- [ ] Console accessible via HTTPS

### UI (Next.js)
- [ ] Next.js served over HTTPS
- [ ] All API calls use HTTPS
- [ ] Mixed content warnings resolved
- [ ] Secure cookies configured

### Certificate Management
- [ ] Document cert generation process (self-signed for dev)
- [ ] Document cert installation for production
- [ ] Certificate rotation strategy documented
- [ ] Expiration monitoring recommended

## Technical Context

**Files to Modify:**

**1. Docker Compose** (`docker-compose.yml`)
```yaml
services:
  api:
    ports:
      - "8443:8443"  # HTTPS
    environment:
      SSL_ENABLED: "true"
      SSL_CERT_PATH: "/certs/api.crt"
      SSL_KEY_PATH: "/certs/api.key"
    volumes:
      - ./certs:/certs:ro

  neo4j:
    environment:
      NEO4J_dbms_connector_bolt_tls__level: REQUIRED
      NEO4J_dbms_ssl_policy_bolt_enabled: "true"
      NEO4J_dbms_ssl_policy_bolt_base__directory: /ssl
    volumes:
      - ./certs/neo4j:/ssl:ro

  minio:
    environment:
      MINIO_OPTS: "--certs-dir /certs"
    volumes:
      - ./certs/minio:/certs:ro
```

**2. FastAPI Configuration** (`api/src/niem_api/main.py`)
```python
import ssl
import uvicorn

if os.getenv("SSL_ENABLED") == "true":
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(
        os.getenv("SSL_CERT_PATH"),
        os.getenv("SSL_KEY_PATH")
    )
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    uvicorn.run(app, host="0.0.0.0", port=8443, ssl=ssl_context)
```

**3. Neo4j Client** (`api/src/niem_api/clients/neo4j_client.py`)
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "neo4j+s://neo4j:7687",  # +s for TLS
    auth=(user, password),
    encrypted=True,
    trust=TRUST_SYSTEM_CA_SIGNED_CERTIFICATES
)
```

**4. MinIO Client** (`api/src/niem_api/core/dependencies.py`)
```python
from minio import Minio

client = Minio(
    endpoint="minio:9000",
    access_key=...,
    secret_key=...,
    secure=True  # Enable HTTPS
)
```

**5. UI Configuration** (`ui/src/lib/api.ts`)
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://localhost:8443';
```

## Implementation Notes

### Phase 1: Certificate Generation (2 hours)
```bash
# Development: Self-signed certificates
mkdir -p certs/{api,neo4j,minio}

# Generate API cert
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout certs/api/api.key \
  -out certs/api/api.crt \
  -days 365 \
  -subj "/CN=localhost"

# Generate Neo4j cert
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout certs/neo4j/private.key \
  -out certs/neo4j/public.crt \
  -days 365 \
  -subj "/CN=neo4j"

# Generate MinIO cert
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout certs/minio/private.key \
  -out certs/minio/public.crt \
  -days 365 \
  -subj "/CN=minio"
```

### Phase 2: Service Configuration (6-8 hours)
1. **API**: Configure Uvicorn with SSL context
2. **Neo4j**: Enable bolt.tls_level and configure SSL policy
3. **MinIO**: Point to certs directory
4. **UI**: Update all HTTP → HTTPS

### Phase 3: Client Updates (4 hours)
1. Update all clients to use TLS
2. Configure certificate validation
3. Handle self-signed certs in development
4. Update connection strings

### Phase 4: Testing (4 hours)
1. Test each service individually
2. Test inter-service communication
3. Test UI → API → Neo4j → MinIO flow
4. Verify certificate validation
5. Test certificate mismatch handling

### Phase 5: Documentation (2 hours)
1. Document certificate generation
2. Update SECURITY.md
3. Add production cert installation guide
4. Document troubleshooting

## Production Considerations

**Certificate Authority (CA):**
- Development: Self-signed certs (generated above)
- Production: Use Let's Encrypt, DigiCert, or internal CA
- Consider cert-manager for Kubernetes deployments

**Certificate Rotation:**
- Automate rotation before expiration
- Use short-lived certs (90 days recommended)
- Monitor expiration dates
- Test rotation process

**Performance:**
- TLS adds ~10-20ms latency per connection
- Use connection pooling to amortize handshake cost
- Enable TLS session resumption
- Consider HTTP/2 for multiplexing

**Troubleshooting:**
- Certificate validation failures
- Hostname mismatches
- Mixed content warnings
- Self-signed cert trust issues

## Related Issues

- Blocks: #9 (data encryption in transit) - prerequisite
- Related to: #10 (data encryption at rest)
- Part of: SECURITY.md P0 items
- Enables: Client certificate authentication (future)

## Priority

**P0 - Blocker for Production** - Must have for any production deployment

## Estimated Effort

**Large (L)** - ~16-24 hours
- Certificate generation: 2 hours
- Service configuration: 6-8 hours
- Client updates: 4 hours
- Testing: 4 hours
- Documentation: 2 hours
- Troubleshooting buffer: 2-4 hours

## Additional Context

**NIST 800-52r2 Guidelines:**
- Require TLS 1.2 or later
- Disable weak cipher suites
- Use strong key lengths (2048+ bits)
- Implement certificate validation

**Docker TLS Resources:**
- https://docs.docker.com/engine/security/certificates/
- https://neo4j.com/docs/operations-manual/current/security/ssl-framework/
- https://min.io/docs/minio/linux/operations/network-encryption.html

**Testing Tools:**
- `openssl s_client` - Test TLS connections
- `nmap --script ssl-enum-ciphers` - Check cipher suites
- Qualys SSL Labs - Comprehensive SSL testing

**Security Headers:**
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src https:
```
