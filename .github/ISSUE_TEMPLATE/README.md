# GitHub Issue Templates

This directory contains detailed issue templates for major features and enhancements to the NIEM Information Exchange E2E PoC project.

## Available Templates

### Graph Improvements (Issues 1-4)

**#1: Flatten augmentation properties to parent nodes** [`01-flatten-augmentation-properties.md`]
- Remove augmentation wrapper nodes
- Move properties directly to parent nodes
- Effort: Large (L) - 8-16 hours
- Priority: Medium

**#2: Ensure root node inclusion and prevent orphaned nodes** [`02-root-node-orphan-prevention.md`]
- Always include document root in graph
- Detect and prevent orphaned nodes
- Effort: Medium (M) - 4-8 hours
- Priority: High

**#3: Convert associations to enriched relationship edges** [`03-associations-as-enriched-edges.md`]
- Transform association nodes into rich edges
- Store association properties on relationships
- Effort: Extra Large (XL) - 16-24 hours
- Priority: Medium

**#4: Add XML-to-JSON instance data transformation** [`04-xml-to-json-transformation.md`]
- Use CMF tool for format conversion
- Enable bidirectional XML ↔ JSON transformation
- Effort: Medium to Large (M-L) - 8-16 hours
- Priority: Low-Medium

### Validation Enhancement (Issue 5)

**#5: Display exact line numbers and source snippets for NDR violations** [`05-ndr-line-numbers-ui.md`]
- Show validation errors with line numbers
- Display code context in UI
- Effort: Small to Medium (S-M) - 4-8 hours
- Priority: Low-Medium
- **Note**: Backend already implemented! Mainly UI work needed.

### File Management (Issues 6-7)

**#6: Add schema set naming for IEPD identification** [`06-schema-set-naming.md`]
- User-defined names for schema sets
- Description fields for documentation
- Effort: Small (S) - 2-4 hours
- Priority: Low

**#7: Build interactive data import wizard** [`07-data-import-wizard.md`]
- Visual mapping tool for XML/JSON → Graph
- Interactive graph schema preview
- Effort: Extra Extra Large (XXL) - 32-48 hours
- Priority: Low / Future Enhancement
- **Note**: High complexity, consider milestone approach

### Security Hardening (Issues 8-10)

**#8: Enable SSL/TLS for all services** [`08-enable-ssl-tls.md`]
- HTTPS for API, UI
- Bolt+S for Neo4j
- TLS for MinIO
- Effort: Large (L) - 16-24 hours
- Priority: **P0 - Blocker for Production**

**#9: Implement comprehensive data encryption in transit** [`09-encryption-in-transit.md`]
- Enforce TLS 1.2+ with strong ciphers
- Disable weak protocols and ciphers
- Certificate validation
- Effort: Medium (M) - 8-12 hours
- Priority: **P0 - Blocker for Production**
- **Depends on**: Issue #8

**#10: Implement data encryption at rest** [`10-encryption-at-rest.md`]
- Encrypt Neo4j database
- Enable MinIO SSE
- Encrypted Docker volumes
- Key management
- Effort: Large to Extra Large (L-XL) - 20-32 hours
- Priority: **P0 - Blocker for Production**

## How to Use These Templates

### Method 1: Create Issues from Templates (Recommended)
1. Go to GitHub Issues page
2. Click "New Issue"
3. Select template from list
4. Fill in any additional details
5. Create issue

### Method 2: Copy Template Content
1. Open template file (e.g., `01-flatten-augmentation-properties.md`)
2. Copy entire content
3. Create new GitHub issue
4. Paste content
5. Remove YAML front matter (---...---) if needed
6. Create issue

### Method 3: Bulk Issue Creation Script
```bash
# Create all issues at once using GitHub CLI
for file in .github/ISSUE_TEMPLATE/*.md; do
  gh issue create --title "$(grep '^title:' $file | cut -d"'" -f2)" --body-file "$file"
done
```

## Issue Dependencies

### Critical Path for Production
```
#8 (SSL/TLS) → #9 (Encryption in Transit) + #10 (Encryption at Rest)
```
All three security issues must be completed before production deployment.

### Graph Improvements Sequence
```
#1 (Augmentations) → #3 (Associations as Edges)
#2 (Root Nodes) → Independent
#4 (XML-JSON Transform) → Independent
```

### UI/UX Enhancements
```
#5 (NDR Line Numbers) → Independent
#6 (Schema Naming) → Enhances #7
#7 (Import Wizard) → Depends on #1, #3
```

## Priority Matrix

| Priority | Issues | Total Effort |
|----------|--------|--------------|
| **P0 (Production Blockers)** | #8, #9, #10 | 44-68 hours |
| **High** | #2 | 4-8 hours |
| **Medium** | #1, #3 | 24-40 hours |
| **Low-Medium** | #4, #5 | 12-24 hours |
| **Low / Future** | #6, #7 | 34-52 hours |

**Total Estimated Effort: 118-192 hours** (~3-5 weeks full-time)

## Recommended Implementation Order

### Phase 1: Security Hardening (Required for Production)
1. **#8**: Enable SSL/TLS (16-24 hours)
2. **#9**: Encryption in transit (8-12 hours)
3. **#10**: Encryption at rest (20-32 hours)

**Phase 1 Total**: 44-68 hours (~1-2 weeks)

### Phase 2: Core Graph Improvements
1. **#2**: Root nodes and orphan prevention (4-8 hours)
2. **#1**: Flatten augmentations (8-16 hours)
3. **#3**: Associations as edges (16-24 hours)

**Phase 2 Total**: 28-48 hours (~1 week)

### Phase 3: User Experience
1. **#6**: Schema naming (2-4 hours)
2. **#5**: NDR line numbers in UI (4-8 hours)
3. **#4**: XML-JSON transformation (8-16 hours)

**Phase 3 Total**: 14-28 hours (~3-5 days)

### Phase 4: Advanced Features (Future)
1. **#7**: Data import wizard (32-48 hours)

**Phase 4 Total**: 32-48 hours (~1-1.5 weeks)

## Labels Used

- `enhancement` - New feature or improvement
- `security` - Security-related
- `p0` - Priority 0 (blocking)
- `graph` - Graph generation/structure
- `ui` - User interface
- `ux` - User experience
- `validation` - Validation-related
- `niem` - NIEM-specific
- `infrastructure` - Infrastructure/deployment
- `production` - Production readiness
- `complex` - High complexity
- `future` - Future enhancement
- `cmf-tool` - CMF tool integration
- `transformation` - Data transformation
- `wizard` - Wizard/multi-step UI

## Contributing

When implementing these issues:
1. Follow CLAUDE.md conventions
2. Write tests for new functionality
3. Update documentation
4. Create PR with reference to issue number
5. Include "Fixes #N" in commit message

## Questions?

- Check CLAUDE.md for project conventions
- Review SECURITY.md for security requirements
- See BACKLOG.md for additional context
- Contact: chris7jackson@gmail.com
