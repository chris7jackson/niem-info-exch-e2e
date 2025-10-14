---
name: Implement data encryption at rest
about: Enable encryption for all stored data (Neo4j, MinIO, volumes)
title: 'Implement data encryption at rest for all storage systems'
labels: security, p0, storage, production
assignees: ''
---

## Problem Statement

Currently, ALL data is stored unencrypted:
- **Neo4j database**: Graph data stored in plaintext
- **MinIO objects**: XSD schemas, instance documents, CMF files in plaintext
- **Docker volumes**: Persistent data unencrypted
- **SQLite metadata**: Unencrypted (if used)

If the host system is compromised or volumes are extracted, all data is readable.

## User Value

- **Compliance**: Required for FISMA, HIPAA, PCI DSS
- **Data protection**: Protect sensitive NIEM data at rest
- **Defense in depth**: Additional security layer beyond access controls
- **Audit requirements**: Demonstrate encryption coverage

## Scope

Encrypt all persistent data storage:
1. Neo4j database files
2. MinIO object storage
3. Docker volumes
4. Configuration files with secrets

## Acceptance Criteria

### Neo4j Encryption
- [ ] Neo4j enterprise encryption enabled OR filesystem encryption used
- [ ] Database files encrypted
- [ ] Transaction logs encrypted
- [ ] Backup encryption configured
- [ ] Key management documented

### MinIO Encryption
- [ ] Server-Side Encryption (SSE) enabled
- [ ] SSE-S3 or SSE-KMS configured
- [ ] Automatic encryption for new objects
- [ ] Existing objects migrated to encrypted buckets
- [ ] Key rotation policy defined

### Docker Volumes
- [ ] Encrypted volumes for persistent data
- [ ] LUKS or dm-crypt for Linux
- [ ] FileVault for macOS
- [ ] BitLocker for Windows
- [ ] Volume encryption documented

### Key Management
- [ ] Encryption keys not stored in code or environment variables
- [ ] Key rotation process defined
- [ ] Key backup strategy documented
- [ ] Access to keys restricted (principle of least privilege)
- [ ] Consider KMS integration (AWS KMS, Azure Key Vault, HashiCorp Vault)

### Verification
- [ ] Encryption status verifiable for all stores
- [ ] Encrypted backups tested
- [ ] Restore from encrypted backup tested
- [ ] Performance impact measured and acceptable

## Technical Context

### Neo4j Encryption at Rest

**Option 1: Neo4j Enterprise (Native Encryption)**
```yaml
# docker-compose.yml
neo4j:
  image: neo4j:5.20-enterprise
  environment:
    NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
    NEO4J_dbms_security_encrypted__encryption__enabled: "true"
    NEO4J_dbms_security_encrypted__encryption__key__provider: "file"
    NEO4J_dbms_security_encrypted__encryption__key__file: "/encryption/neo4j.key"
  volumes:
    - ./encryption/neo4j:/encryption:ro
```

**Cost**: Requires Neo4j Enterprise license ($$$)

**Option 2: Filesystem Encryption (Recommended for PoC)**
```bash
# Create encrypted volume using LUKS
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup luksOpen /dev/sdb1 neo4j_encrypted
sudo mkfs.ext4 /dev/mapper/neo4j_encrypted
sudo mount /dev/mapper/neo4j_encrypted /var/lib/neo4j/data
```

**Docker Volume Plugin:**
```yaml
volumes:
  neo4j-data:
    driver: local
    driver_opts:
      type: none
      device: /mnt/encrypted/neo4j
      o: bind
```

### MinIO Encryption at Rest

**Server-Side Encryption (SSE-S3):**
```python
# Enable encryption for all new objects
from minio import Minio
from minio.sse import SseCustomerKey

# Option 1: Server-managed keys (SSE-S3)
client = Minio(...)
# Auto-encrypts with server-managed keys

# Option 2: Customer-managed keys (SSE-C)
sse_key = SseCustomerKey(b"32-byte-encryption-key-here-xxx")
client.put_object(
    "bucket",
    "object",
    data,
    length,
    sse=sse_key
)
```

**MinIO Configuration:**
```yaml
minio:
  environment:
    MINIO_KMS_SECRET_KEY: "my-minio-key:CHANGE-ME-CHANGE-ME-CHANGE-ME-CHANGE-ME"
  command: server /data --console-address ":9001"
```

**Encrypt Existing Objects:**
```python
# Migration script
for obj in client.list_objects("bucket", recursive=True):
    # Re-upload with encryption
    data = client.get_object("bucket", obj.object_name)
    client.put_object("bucket", obj.object_name, data, sse=sse_config)
```

### Docker Volume Encryption

**Linux (LUKS):**
```bash
# Create encrypted volume
sudo cryptsetup luksFormat /dev/sdb
sudo cryptsetup luksOpen /dev/sdb encrypted_volume
sudo mkfs.ext4 /dev/mapper/encrypted_volume
```

**macOS (FileVault):**
```bash
# Enable FileVault for Docker volumes directory
sudo fdesetup enable
```

**Docker Compose Integration:**
```yaml
volumes:
  encrypted-neo4j:
    driver: local
    driver_opts:
      type: none
      device: /mnt/encrypted/neo4j
      o: bind
  encrypted-minio:
    driver: local
    driver_opts:
      type: none
      device: /mnt/encrypted/minio
      o: bind
```

### Key Management

**Development (Not Secure - For Testing Only):**
```bash
# Generate encryption key
openssl rand -hex 32 > .keys/encryption.key

# Mount as read-only volume
docker-compose.yml:
  volumes:
    - ./.keys:/keys:ro
```

**Production (Recommended):**
- **AWS KMS**: Managed key service
- **Azure Key Vault**: Managed keys for Azure
- **HashiCorp Vault**: Self-hosted KMS
- **Google Cloud KMS**: Managed keys for GCP

**Vault Integration Example:**
```python
import hvac

client = hvac.Client(url='https://vault:8200', token=vault_token)
encryption_key = client.secrets.kv.v2.read_secret_version(
    path='niem/encryption-keys'
)['data']['data']['neo4j_key']
```

## Implementation Notes

### Phase 1: MinIO Encryption (4 hours)
1. Enable SSE-S3 on MinIO
2. Test new object encryption
3. Migrate existing objects
4. Verify encryption status

### Phase 2: Neo4j Encryption (6-8 hours)
**Path A: Enterprise (if licensed):**
1. Upgrade to Enterprise edition
2. Generate encryption key
3. Enable encryption
4. Test database operations

**Path B: Filesystem (if Community):**
1. Set up encrypted filesystem
2. Migrate Neo4j data
3. Update docker-compose
4. Test mounting and access

### Phase 3: Docker Volume Encryption (4 hours)
1. Create encrypted filesystems
2. Configure Docker volumes
3. Migrate existing data
4. Update docker-compose

### Phase 4: Key Management (6-8 hours)
1. Choose KMS solution
2. Set up key storage
3. Integrate with services
4. Test key rotation
5. Document procedures

### Phase 5: Testing & Validation (4 hours)
1. Verify encryption active
2. Test performance impact
3. Test backup/restore
4. Validate key rotation
5. Test disaster recovery

## Testing & Verification

```bash
# Verify Neo4j encryption (Enterprise)
docker exec neo4j neo4j-admin dbms encryption-status

# Verify MinIO encryption
mc admin info play/bucket --json | jq '.encryption'

# Check filesystem encryption (Linux)
sudo cryptsetup status /dev/mapper/encrypted_volume

# Attempt to read raw data (should be encrypted)
sudo strings /var/lib/neo4j/data/databases/neo4j/neostore
# Should show encrypted gibberish, not plaintext

# Performance test
time docker exec neo4j cypher-shell "MATCH (n) RETURN count(n)"
```

## Implementation Alternatives

### Option 1: Filesystem-Level Encryption (Recommended for PoC)
**Pros:**
- Works with Community editions
- No license costs
- OS-level encryption (LUKS, FileVault)
- Transparent to applications

**Cons:**
- Requires host configuration
- Key management is manual
- Performance overhead on host

### Option 2: Application-Level Encryption
**Pros:**
- Fine-grained control
- Works anywhere
- No infrastructure changes

**Cons:**
- More complex to implement
- Application must handle encryption
- Queryability issues (can't query encrypted fields)

### Option 3: Enterprise Features
**Pros:**
- Native support
- Better integration
- Optimized performance

**Cons:**
- License costs
- Vendor lock-in
- May not be available for all services

## Related Issues

- Related to: #8 (SSL/TLS) - Encryption in transit
- Related to: #9 (Data encryption in transit)
- Part of: SECURITY.md P0 roadmap
- Enables: Compliance certifications
- Requires: Key management solution

## Priority

**P0 - Blocker for Production** - Critical for any production deployment with sensitive data

## Estimated Effort

**Large to Extra Large (L-XL)** - ~20-32 hours
- MinIO encryption: 4 hours
- Neo4j encryption: 6-8 hours (depends on edition)
- Volume encryption: 4 hours
- Key management: 6-8 hours
- Testing: 4 hours
- Documentation: 4 hours
- Troubleshooting buffer: 4-6 hours

**Note**: Effort assumes Community edition (filesystem encryption). Enterprise edition adds ~8 hours for licensing and setup.

## Additional Context

**Compliance Requirements:**
- **HIPAA §164.312(a)(2)(iv)**: Encryption of ePHI
- **PCI DSS 3.2**: Requirement 3.4 (render PAN unreadable)
- **GDPR Article 32**: Encryption of personal data
- **FedRAMP**: SC-28 (Protection of information at rest)
- **NIST 800-53**: SC-28, SC-13 (Cryptographic protection)

**Performance Impact:**
- Filesystem encryption: ~5-10% overhead
- AES-NI hardware acceleration reduces impact
- SSD performance more affected than HDD
- Test workload-specific impact

**Key Rotation Strategy:**
```
1. Generate new encryption key
2. Decrypt data with old key
3. Re-encrypt data with new key
4. Update key references
5. Securely delete old key
6. Repeat quarterly (or per policy)
```

**Backup Considerations:**
- Encrypted backups require key for restore
- Store keys separately from backups
- Document key recovery process
- Test restore from encrypted backups
- Consider backup encryption separately

**References:**
- https://neo4j.com/docs/operations-manual/current/security/encryption/
- https://min.io/docs/minio/linux/operations/server-side-encryption.html
- https://docs.docker.com/storage/storagedriver/device-mapper-driver/
- https://www.vaultproject.io/docs/secrets/kv

**Disaster Recovery:**
```
1. Document key locations
2. Secure key backups (offline, encrypted)
3. Test restore procedures
4. Maintain key version history
5. Plan for key compromise scenario
```
