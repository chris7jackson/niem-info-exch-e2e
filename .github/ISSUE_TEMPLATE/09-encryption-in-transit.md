---
name: Implement data encryption in transit
about: Enforce TLS 1.2+ for all inter-service communication with strong ciphers
title: 'Implement comprehensive data encryption in transit'
labels: security, p0, networking, production
assignees: ''
---

## Problem Statement

Beyond enabling TLS (#8), we need to ensure **all** data in transit is encrypted with strong protocols and cipher suites. This includes:
- Enforcing minimum TLS version (1.2+)
- Disabling weak cipher suites
- Securing internal Docker network
- Validating all certificate chains
- Preventing downgrade attacks

Currently: No enforcement, mixed HTTP/HTTPS possible, weak ciphers allowed

## User Value

- **Compliance**: Meet NIST 800-52r2, PCI DSS requirements
- **Protection**: Prevent MITM (man-in-the-middle) attacks
- **Audit**: Demonstrate security posture for certifications
- **Best practices**: Industry-standard encryption

## Scope

Comprehensive encryption in transit across all communication paths:
1. External client → UI
2. UI → API
3. API → Neo4j
4. API → MinIO
5. Docker inter-service networking

## Acceptance Criteria

### TLS Configuration
- [ ] TLS 1.2 minimum (TLS 1.3 preferred)
- [ ] SSLv3, TLS 1.0, TLS 1.1 explicitly disabled
- [ ] Strong cipher suites only (AES-GCM, ChaCha20-Poly1305)
- [ ] Weak ciphers disabled (RC4, 3DES, MD5, SHA1)
- [ ] Forward secrecy enabled (ECDHE, DHE key exchange)
- [ ] Certificate validation enforced (no self-signed bypass in production)

### Network Segmentation
- [ ] Docker network configured with encryption
- [ ] Internal communication uses TLS
- [ ] No plaintext fallback allowed
- [ ] Network policy enforces encryption

### Certificate Validation
- [ ] All clients validate server certificates
- [ ] Certificate pinning documented (optional)
- [ ] Revocation checking configured (OCSP/CRL)
- [ ] Hostname verification enabled

### Monitoring & Logging
- [ ] TLS connection failures logged
- [ ] Cipher suite usage monitored
- [ ] Certificate expiration alerts
- [ ] Downgrade attempt detection

### Documentation
- [ ] Cipher suite choices documented
- [ ] TLS version policy documented
- [ ] Certificate management procedures
- [ ] Troubleshooting guide

## Technical Context

**Recommended Cipher Suites (NIST compliant):**
```
TLS_AES_256_GCM_SHA384              # TLS 1.3
TLS_CHACHA20_POLY1305_SHA256        # TLS 1.3
TLS_AES_128_GCM_SHA256              # TLS 1.3
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384    # TLS 1.2
TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256    # TLS 1.2
```

**Explicitly Disabled Ciphers:**
```
TLS_RSA_*                           # No forward secrecy
*_CBC_*                             # Vulnerable to BEAST, Lucky13
*_RC4_*                             # Weak cipher
*_3DES_*                            # Weak cipher
*_MD5                               # Weak hash
```

**Files to Modify:**

**1. FastAPI SSL Configuration** (`api/Dockerfile` + `api/src/niem_api/main.py`)
```python
import ssl

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_SSLv3

# Set strong cipher suites
ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')

ssl_context.load_cert_chain(cert_path, key_path)
ssl_context.load_verify_locations(cafile=ca_cert_path)
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED
```

**2. Neo4j Client Configuration** (`api/src/niem_api/clients/neo4j_client.py`)
```python
from neo4j import GraphDatabase, TRUST_SYSTEM_CA_SIGNED_CERTIFICATES

driver = GraphDatabase.driver(
    "neo4j+s://neo4j:7687",
    auth=(user, password),
    encrypted=True,
    trust=TRUST_SYSTEM_CA_SIGNED_CERTIFICATES,
    max_connection_lifetime=3600,
    max_connection_pool_size=50,
    connection_timeout=30.0,
    # Enforce TLS validation
    trusted_certificates=TrustSystemCAs()
)
```

**3. MinIO Client Configuration** (`api/src/niem_api/core/dependencies.py`)
```python
import urllib3
from minio import Minio

# Configure HTTP client with strict TLS
http_client = urllib3.PoolManager(
    timeout=urllib3.Timeout(connect=10.0, read=30.0),
    cert_reqs='CERT_REQUIRED',
    ca_certs='/etc/ssl/certs/ca-certificates.crt',
    ssl_minimum_version=ssl.TLSVersion.TLSv1_2
)

client = Minio(
    "minio:9000",
    access_key=access_key,
    secret_key=secret_key,
    secure=True,
    http_client=http_client
)
```

**4. Docker Network Configuration** (`docker-compose.yml`)
```yaml
networks:
  secure-backend:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_ip_masquerade: "true"
      com.docker.network.driver.mtu: 1500
    # For production with overlay network:
    # driver: overlay
    # encrypted: true

services:
  api:
    networks:
      - secure-backend
  neo4j:
    networks:
      - secure-backend
  minio:
    networks:
      - secure-backend
```

**5. Nginx/Reverse Proxy Configuration** (if added)
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-CHACHA20-POLY1305';
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;

add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

## Implementation Notes

### Phase 1: Cipher Suite Hardening (4 hours)
1. Configure each service's cipher suites
2. Test compatibility
3. Verify weak ciphers disabled
4. Document choices

### Phase 2: Certificate Validation (4 hours)
1. Enable hostname verification
2. Configure CA certificate bundles
3. Test certificate validation failures
4. Add error handling

### Phase 3: Network Segmentation (2 hours)
1. Create secure Docker network
2. Migrate services
3. Test inter-service communication
4. Verify no plaintext fallback

### Phase 4: Monitoring & Logging (4 hours)
1. Add TLS connection logging
2. Log cipher suite usage
3. Alert on weak cipher attempts
4. Monitor for downgrade attacks

### Phase 5: Testing & Validation (4 hours)
1. Use SSL Labs or testssl.sh
2. Verify TLS version enforcement
3. Test cipher suite negotiation
4. Validate certificate chains
5. Test revocation checking

## Security Testing Commands

```bash
# Test TLS configuration
openssl s_client -connect localhost:8443 -tls1_2
openssl s_client -connect localhost:8443 -tls1_1  # Should fail

# Check cipher suites
nmap --script ssl-enum-ciphers -p 8443 localhost

# Comprehensive SSL test
docker run --rm -ti drwetter/testssl.sh https://localhost:8443

# Test certificate validation
curl --cacert ca.crt https://localhost:8443/healthz
curl -k https://localhost:8443/healthz  # Should NOT work in prod
```

## Related Issues

- Depends on: #8 (Enable SSL/TLS) - Must be completed first
- Related to: #10 (Encryption at rest)
- Part of: SECURITY.md P0 roadmap
- Enables: Certificate pinning (future)
- Enables: Mutual TLS (mTLS) authentication (future)

## Priority

**P0 - Blocker for Production** - Critical security requirement

## Estimated Effort

**Medium (M)** - ~8-12 hours
- Cipher configuration: 4 hours
- Certificate validation: 4 hours
- Network segmentation: 2 hours
- Monitoring setup: 4 hours
- Testing: 4 hours
- Documentation: 2 hours

## Additional Context

**NIST 800-52r2 Requirements:**
- TLS 1.2 minimum
- FIPS 140-2 approved algorithms
- Forward secrecy required
- Certificate validation mandatory

**Common Vulnerabilities:**
- BEAST (TLS 1.0 + CBC)
- POODLE (SSLv3)
- CRIME/BREACH (TLS compression)
- Lucky13 (CBC timing)
- Heartbleed (OpenSSL bug - patched)
- Logjam (weak DH parameters)

**Performance Considerations:**
- TLS 1.3 is faster than TLS 1.2 (fewer roundtrips)
- AES-GCM has hardware acceleration on modern CPUs
- Session resumption reduces handshake overhead
- OCSP stapling reduces latency

**Compliance Mappings:**
- **PCI DSS 4.0**: Requirement 4.2 (Encryption in transit)
- **HIPAA**: 164.312(e)(1) (Transmission security)
- **FedRAMP**: SC-8 (Transmission confidentiality)
- **NIST 800-53**: SC-8, SC-13 (Cryptographic protection)

**References:**
- https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-52r2.pdf
- https://wiki.mozilla.org/Security/Server_Side_TLS
- https://ssl-config.mozilla.org/
- https://ciphersuite.info/

**Certificate Revocation:**
```python
# OCSP stapling configuration
ssl_context.set_ocsp_client_callback(ocsp_callback)

# CRL checking
ssl_context.verify_flags = ssl.VERIFY_CRL_CHECK_CHAIN
```
