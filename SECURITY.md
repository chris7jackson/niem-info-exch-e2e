# Security Policy

This is a **proof-of-concept** project intended for local demonstration and educational purposes. It is **not production-ready** and should only be run in isolated, air-gapped environments with sample data.

This security policy provides guidance for local demo deployments and how to report security issues found during development.

## Intended Use

✅ **Safe for:**
- Local laptop demos with Docker
- Educational workshops
- Development and testing environments
- Air-gapped demo systems with sample NIEM data

❌ **NOT safe for:**
- Production deployments
- Internet-accessible systems
- Real PII or sensitive government data
- Multi-user environments
- Systems connected to external networks

## Known Limitations

This proof-of-concept has the following security limitations **by design** for demo simplicity:

### Authentication
- Uses static dev token (`DEV_TOKEN=devtoken` in `.env`)
- No user management or session handling
- No multi-user support
- No role-based access control (RBAC)

### Data Protection
- **No encryption in transit** - All services use HTTP/unencrypted protocols
- **No encryption at rest** - Database and file storage are unencrypted
- **Default credentials:**
  - Neo4j: `neo4j/password`
  - MinIO: `minio/minio123`
  - API: `devtoken`

### Network Security
- All services exposed on localhost only
- No firewall rules configured
- No network segmentation
- Not hardened for external access
- CORS allows `localhost:3000` only

### Dependencies
- Uses vendored third-party tools (see [NOTICE](NOTICE))
- No automatic security update mechanism
- Dependencies frozen at tested versions

⚠️ **Important:** These limitations are intentional for demo simplicity. See [BACKLOG.md](BACKLOG.md) for the production hardening roadmap.

## Demo Environment Best Practices

For safe local demonstrations:

1. **Run only on localhost**
   - Don't expose ports to external networks
   - Don't bind services to `0.0.0.0`
   - Keep Docker containers on default bridge network

2. **Use sample data only**
   - Never use real PII or classified information
   - Use the provided `samples/CrashDriver-cmf/` test data
   - Fictional data only (e.g., "Peter Death Bredon Wimsey")

3. **Shut down after demos**
   ```bash
   docker compose down
   ```
   Stops all services and removes containers

4. **Keep Docker updated**
   - Update Docker Desktop regularly
   - Pull latest base images when rebuilding

5. **Reset between demos**
   ```bash
   # Clear all data (Neo4j + MinIO)
   docker compose down -v
   ```
   Removes all volumes and stored data

6. **Monitor resource usage**
   - Neo4j can consume significant memory
   - Close other applications during demos if needed
   - Check `docker compose ps` for service health

## Reporting Security Issues

Found a security concern during development?

### For Security-Related Bugs

1. **Check if it's a known limitation** - See "Known Limitations" above
2. **Open a GitHub Issue** - https://github.com/[username]/niem-info-exch-e2e/issues
3. **Tag with `security` label**
4. **Describe:**
   - The security concern
   - Steps to reproduce
   - Potential impact (if deployed to production)
   - Suggested fix (if you have one)

### For Significant Vulnerabilities

If you discover a vulnerability that could seriously impact users if this were deployed to production (e.g., remote code execution, authentication bypass beyond the known dev token issue):

**Email directly:** chris7jackson@gmail.com

Include:
- Type of vulnerability
- Location (file/endpoint)
- Proof of concept
- Potential impact

**Response time:** Best effort (this is a PoC project maintained part-time)

### Not Security Issues

The following are **known by design** and not security issues:
- Static `devtoken` authentication
- Plaintext HTTP/Bolt/S3 connections
- Default Neo4j/MinIO credentials
- Localhost-only CORS
- No rate limiting
- No audit logging

These are tracked in [BACKLOG.md](BACKLOG.md) for production hardening.

## Production Deployment

⚠️ **This project is NOT production-ready.**

If you plan to deploy this in a production or multi-user environment, review:

### Critical Security Gaps

**P0 - Blockers:**
- No TLS/SSL encryption (P0.4)
- No secrets management (P0.5)
- Credentials in plaintext `.env` files

**P1 - Required for Production:**
- Static dev token authentication (P1.1)
- No role-based access control (P1.2)
- No audit logging (P1.3)
- No rate limiting (P1.4)
- No input sanitization audit (P1.5)

**P2 - Operations:**
- No PII detection/classification (P2.1)
- No metrics/observability (P2.2)
- No backup/disaster recovery (P2.7, P2.8)

### Production Readiness Roadmap

See [BACKLOG.md](BACKLOG.md) for the complete production hardening plan:
- **27 backlog items** organized by priority
- **P0-P3 priority levels** (blockers → nice-to-have)
- **~418 hours estimated effort** (~10 weeks, 1 FTE)
- **Detailed acceptance criteria** for each item

**Key items needed before production:**
- OAuth2/JWT authentication (P1.1)
- RBAC and authorization (P1.2)
- TLS/SSL encryption (P0.4)
- Secrets management (P0.5)
- Comprehensive security audit (P1.5)
- Audit logging for compliance (P1.3)
- Rate limiting and throttling (P1.4)
- Backup and disaster recovery (P2.7, P2.8)

### Recommended Security Review

Before production deployment, conduct:
- **Threat modeling** - Identify attack vectors
- **Penetration testing** - External security assessment
- **Code review** - Focus on input validation and Cypher query generation
- **Dependency audit** - Check for known vulnerabilities
- **Compliance review** - FISMA, FedRAMP, or applicable standards

## Third-Party Security

This project uses the following third-party components:

### Vendored Tools
- **niemopen/cmftool** - CMF validation tool (Apache 2.0)
  - Source: https://github.com/niemopen/cmftool
- **NIEM/NIEM-NDR** - NDR validation rules (CC BY 4.0)
  - Source: https://github.com/NIEM/NIEM-NDR

### Runtime Dependencies
- **Neo4j 5.20** - Graph database
  - Security: https://neo4j.com/security/
- **MinIO** - S3-compatible storage
  - Security: https://min.io/docs/minio/linux/operations/security.html
- **FastAPI** - Python web framework
  - Security: https://fastapi.tiangolo.com/deployment/security/
- **Next.js 14** - React framework
  - Security: https://nextjs.org/docs/app/building-your-application/configuring/security

See [NOTICE](NOTICE) for complete third-party attribution.

**Reporting third-party vulnerabilities:**
Security issues in third-party components should be reported to their respective maintainers, not to this project.

## Security Configuration Checklist

If you choose to deploy this despite the warnings, at minimum:

- [ ] Change all default credentials
  - [ ] Neo4j password (not `password`)
  - [ ] MinIO credentials (not `minio/minio123`)
  - [ ] API DEV_TOKEN (not `devtoken`)
- [ ] Enable TLS/SSL for all services
  - [ ] Neo4j Bolt+S
  - [ ] MinIO HTTPS
  - [ ] API HTTPS
- [ ] Implement proper authentication
  - [ ] OAuth2 or JWT tokens
  - [ ] User management
  - [ ] Session handling
- [ ] Add authorization and RBAC
- [ ] Enable audit logging
- [ ] Set up rate limiting
- [ ] Configure firewall rules
- [ ] Implement backup strategy
- [ ] Set up monitoring and alerting
- [ ] Conduct security assessment

**Better yet:** Wait for production readiness items in BACKLOG.md to be implemented.

## Compliance and Standards

### Current State
This PoC project does **NOT** comply with:
- FISMA (Federal Information Security Management Act)
- FedRAMP (Federal Risk and Authorization Management Program)
- NIST 800-53 security controls
- GDPR data protection requirements
- CCPA privacy requirements
- SOC 2 compliance standards

### Target State
The production roadmap (BACKLOG.md) includes items to address:
- Authentication and authorization (AC family)
- Audit and accountability (AU family)
- System and communications protection (SC family)
- Security assessment and authorization (CA family)

For government production use, a full ATO (Authority to Operate) assessment would be required.

## Resources

- **Project Documentation:** [README.md](README.md)
- **Production Roadmap:** [BACKLOG.md](BACKLOG.md)
- **License:** [LICENSE](LICENSE) (Apache 2.0)
- **Third-Party Attribution:** [NOTICE](NOTICE)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Architecture:** [docs/API_ARCHITECTURE.md](docs/API_ARCHITECTURE.md)

## Contact

**Project Maintainer:** Christopher Jackson
- **Email:** chris7jackson@gmail.com
- **GitHub:** https://github.com/[username]/niem-info-exch-e2e

For non-security issues, please use GitHub Issues.

---

**Last Updated:** October 2025
**Version:** Proof of Concept (Pre-1.0)
