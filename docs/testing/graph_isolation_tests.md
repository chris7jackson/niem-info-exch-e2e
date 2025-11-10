# Graph Isolation Testing Strategy

## Overview

This document describes the comprehensive test suite for validating graph isolation functionality. The isolation feature ensures that data from different file uploads remains separate in Neo4j until explicitly linked via entity resolution.

## Test Coverage

### 1. Unit Tests (`api/tests/unit/services/test_graph_isolation.py`)

#### Test Classes:

**TestUploadIdGeneration**
- Tests that converters properly add `_upload_id`, `_schema_id`, and `_source_file` properties to nodes
- Verifies backward compatibility when upload_id is not provided
- Tests both JSON and XML converters

**TestGraphIsolation**
- Tests that MATCH clauses use composite keys (id + upload_id + source_file)
- Verifies different upload_ids create isolated graphs for same data
- Tests containment relationships use composite key matching
- Validates no accidental merging occurs

**TestEdgeCasesAndCompatibility**
- Tests empty/None upload_id handling
- Tests special characters in filenames
- Tests very long upload_ids

#### Key Test Cases:

1. **`test_json_converter_includes_upload_id_in_node_properties`**
   - Verifies `_upload_id`, `_schema_id`, and `_source_file` are added to generated Cypher
   - Tests JSON converter with upload tracking

2. **`test_xml_converter_includes_upload_id_in_node_properties`**
   - Verifies XML converter adds isolation properties
   - Tests with sourceDoc property for XML

3. **`test_json_match_clauses_include_upload_id_and_filename`**
   - Validates all MATCH clauses include composite key
   - Prevents relationships from crossing file boundaries

4. **`test_different_upload_ids_create_isolated_graphs`**
   - Tests that same data with different upload_ids remains isolated
   - Verifies no accidental node merging

### 2. Integration Tests (`api/tests/integration/test_graph_isolation_integration.py`)

#### Test Class: **TestMultiFileGraphIsolation**

Requires Neo4j service (runs in CI with Docker services)

#### Key Test Cases:

1. **`test_nodes_with_same_id_different_uploads_are_isolated`**
   - Creates nodes with identical IDs in different uploads
   - Verifies both nodes exist independently in Neo4j
   - Tests composite key querying

2. **`test_relationships_do_not_cross_file_boundaries`**
   - Creates person-address relationships in two separate uploads
   - Verifies no cross-upload relationships exist
   - Ensures complete graph isolation

3. **`test_same_filename_different_uploads_creates_separate_graphs`**
   - Tests uploading same filename multiple times
   - Verifies upload_id differentiates between uploads
   - Important for re-upload scenarios

4. **`test_filtering_by_upload_id_returns_isolated_subgraph`**
   - Tests querying by upload_id returns only that upload's nodes
   - Verifies filtering works correctly

5. **`test_filtering_by_source_file_returns_file_specific_nodes`**
   - Tests filtering by source filename
   - Important for multi-file filter UI feature

6. **`test_entity_resolution_can_link_across_uploads`**
   - **Critical test**: Verifies entity resolution can create RESOLVED_TO relationships
   - Ensures Senzing/text-based matching can link entities across uploads
   - Tests the intended use case for cross-upload connections

7. **`test_composite_key_prevents_accidental_merges`**
   - Tests MERGE with composite key doesn't merge distinct nodes
   - Validates Neo4j MERGE behavior with isolation properties

## Running Tests

### Locally (CI Environment)

Tests require Neo4j and are designed to run in CI or Docker:

```bash
# Start services
docker compose up -d

# Run unit tests (in CI or with pytest installed)
cd api
pytest tests/unit/services/test_graph_isolation.py -v

# Run integration tests (requires Neo4j)
pytest tests/integration/test_graph_isolation_integration.py -v \
  --neo4j-uri=bolt://localhost:7687 \
  --neo4j-user=neo4j \
  --neo4j-password=testpassword
```

### In GitHub Actions

Tests run automatically in PR checks:
- **Unit tests**: Run in `backend-quality` job
- **Integration tests**: Run in `api-integration-tests` job with Neo4j service

## Test Strategy Rationale

### Why These Tests Matter

1. **Data Integrity**: Prevents accidental data merging between unrelated uploads
2. **Multi-tenancy**: Supports multiple users uploading files simultaneously
3. **Entity Resolution**: Allows controlled linking only via explicit resolution
4. **UI Filtering**: Enables file-specific views in graph visualization

### Coverage Goals

- ✅ **Property Addition**: Verify isolation properties are added
- ✅ **Composite Keys**: Test MATCH/MERGE use full composite key
- ✅ **Isolation**: Verify no cross-file relationships
- ✅ **Resolution**: Test entity resolution can link across uploads
- ✅ **Edge Cases**: Handle special characters, empty values, long IDs

## Integration with UI

The tests validate backend behavior that enables UI features:

1. **Multi-select File Filter** (`ui/src/pages/graph.tsx`)
   - Tests ensure nodes have `_source_file` property
   - Validates filtering returns correct isolated subgraphs

2. **Related Nodes Display**
   - Tests ensure entity resolution relationships work
   - Validates cross-upload connections are visible

## Future Test Enhancements

Potential additions for comprehensive coverage:

1. **Performance tests**: Large multi-file uploads
2. **Concurrency tests**: Simultaneous uploads
3. **Entity resolution tests**: Full Senzing integration
4. **UI E2E tests**: Test file filter dropdown with real data

## Test Maintenance

When modifying converters:
- Update tests if new properties are added
- Add tests for new relationship types
- Test any changes to MATCH/MERGE logic
- Verify backward compatibility

## Success Criteria

All tests should pass to ensure:
1. ✅ Nodes have isolation properties (_upload_id, _source_file)
2. ✅ MATCH clauses use composite keys
3. ✅ No accidental cross-file relationships
4. ✅ Entity resolution can link entities
5. ✅ Backward compatibility maintained
