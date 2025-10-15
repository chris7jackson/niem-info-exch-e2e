# API Migrations

This directory will contain database and schema migrations for the NIEM API.

## Status

**Not Active During Prerelease (0.x.y)**

Migration tooling is stubbed but not active during the prerelease phase. Breaking changes are allowed in 0.x.y versions.

## Future Implementation (1.0.0+)

When the API reaches version 1.0.0, this directory will contain:

### Neo4j Migrations
- Cypher scripts for graph schema changes
- Format: `001_description.cypher`, `002_description.cypher`
- Applied sequentially on startup

### MinIO/Storage Migrations
- Scripts for bucket structure changes
- Data format migrations
- Object reorganization

### Migration Strategy

**Versioned Migrations:**
- Each migration has a version number
- Migrations run in order
- Track applied migrations in Neo4j
- Idempotent where possible

**Example Migration:**
```cypher
// 001_add_version_tracking.cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (m:Migration) REQUIRE m.version IS UNIQUE;
CREATE (m:Migration {version: 1, name: 'add_version_tracking', applied_at: datetime()});
```

**NIEM Version Upgrades:**
- Migrations for NIEM 6.0 → 7.0 transitions
- Schema namespace updates
- Property mapping changes

## Related Documentation
- `docs/VERSIONING.md` - Semantic versioning strategy
- `docs/MIGRATION.md` - Migration guides (future)
