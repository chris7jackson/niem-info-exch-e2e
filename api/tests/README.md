# Senzing Entity Resolution Tests

Automated test suite to ensure Senzing entity resolution functionality doesn't break.

## Test Structure

```
api/tests/
├── integration/
│   └── test_senzing_entity_resolution.py  # End-to-end Senzing tests
├── unit/
│   ├── handlers/
│   │   └── test_entity_resolution.py      # Handler function tests
│   ├── services/
│   │   └── test_entity_to_senzing.py      # NIEM→Senzing conversion tests
│   └── clients/
│       └── test_senzing_client.py         # Senzing gRPC client tests
├── fixtures/
│   └── senzing_fixtures.py                # Reusable test data and helpers
└── README.md                               # This file
```

## Running Tests

### Prerequisites

Rebuild the API container to install test dependencies:
```bash
docker compose build api
docker compose up -d api
```

### Run All Tests

```bash
docker compose exec api pytest tests/ -v
```

### Run Specific Test Suites

**Unit Tests Only (fast, no external dependencies):**
```bash
docker compose exec api pytest tests/unit/ -v
```

**Integration Tests (requires services running):**
```bash
docker compose exec api pytest tests/integration/ -v
```

**Specific Test File:**
```bash
docker compose exec api pytest tests/unit/services/test_entity_to_senzing.py -v
```

**Single Test:**
```bash
docker compose exec api pytest tests/integration/test_senzing_entity_resolution.py::TestSenzingEntityResolution::test_entity_resolution_with_duplicates -v
```

### With Coverage Report

```bash
docker compose exec api pytest tests/ --cov=niem_api.handlers.entity_resolution --cov=niem_api.services.entity_to_senzing --cov=niem_api.clients.senzing_client --cov-report=html
```

View coverage: `open api/htmlcov/index.html`

## Test Coverage

### Integration Tests (`test_senzing_entity_resolution.py`)

**Tests Full Senzing Flow:**
- ✅ Entity extraction from Neo4j
- ✅ NIEM → Senzing field mapping
- ✅ Senzing gRPC communication
- ✅ ResolvedEntity node creation
- ✅ Graph isolation property aggregation
- ✅ RESOLVED_TO relationship creation
- ✅ Reset functionality
- ✅ Cross-document duplicate detection
- ✅ No duplicates scenario
- ✅ Empty dataset handling

**Tests (10 total):**
1. `test_get_available_node_types` - Node type discovery
2. `test_entity_resolution_with_duplicates` - Core duplicate detection
3. `test_resolution_status` - Status endpoint
4. `test_reset_entity_resolution` - Reset and cleanup
5. `test_cross_document_resolution` - Multi-file matching
6. `test_senzing_match_details` - Match metadata
7. `test_graph_isolation_properties` - Property aggregation
8. `test_no_duplicates_scenario` - Unique entities
9. `test_senzing_sdk_available` - SDK availability
10. `test_senzing_entity_id_tracking` - Senzing ID persistence

### Unit Tests (`test_entity_to_senzing.py`)

**Tests NIEM → Senzing Conversion:**
- ✅ Entity categorization (person/organization/address)
- ✅ Field mapping (74 NIEM fields → Senzing fields)
- ✅ Date formatting
- ✅ Confidence score extraction
- ✅ Batch conversion
- ✅ Empty property handling

**Tests (15+ total):**
- Entity categorization (person, organization, address, unknown)
- Field mapping (names, IDs, dates)
- Date formatting (ISO, US formats, invalid dates)
- Confidence extraction (various score ranges)
- Batch processing

### Unit Tests (`test_entity_resolution.py`)

**Tests Handler Logic:**
- ✅ Entity key creation (full name, given+surname, empty)
- ✅ Name normalization
- ✅ Entity grouping (duplicates, unique, empty)
- ✅ Senzing field counting
- ✅ Field mapping with prefixes

**Tests (15+ total):**
- Entity key generation from various name formats
- Duplicate grouping logic
- Senzing mappable field counting
- Prefix/suffix handling in property names

### Unit Tests (`test_senzing_client.py`)

**Tests gRPC Client:**
- ✅ Client initialization
- ✅ Record operations (add, get, delete)
- ✅ Batch processing
- ✅ Error handling
- ✅ Resource cleanup

**Tests (12+ total):**
- Initialization success/failure
- Add/get/delete record operations
- Batch processing with mixed results
- Connection failure handling
- Factory cleanup

## Test Fixtures

### Sample Entities (`senzing_fixtures.py`)

Provides:
- `SAMPLE_ENTITIES` - Pre-built test entities (Peter Wimsey, Harriet Vane, Jason Ohlendorf)
- `SAMPLE_SENZING_RESPONSES` - Mock Senzing API responses
- `create_mock_senzing_client()` - Mock client for unit tests
- `assert_resolved_entity_structure()` - Validation helpers
- `SAMPLE_FIELD_MAPPINGS` - Test configuration

## CI/CD Integration

### GitHub Actions (Recommended)

Create `.github/workflows/tests.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5.20-community
        env:
          NEO4J_AUTH: neo4j/password
        ports:
          - 7687:7687

      senzing-postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: senzing
          POSTGRES_USER: senzing
          POSTGRES_PASSWORD: senzing123
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Build and test
        run: |
          docker compose build api
          docker compose up -d
          docker compose exec -T api pytest tests/ -v --cov
```

### Local Development

Add to `package.json` or create `Makefile`:
```makefile
.PHONY: test test-unit test-integration test-cov

test:
	docker compose exec api pytest tests/ -v

test-unit:
	docker compose exec api pytest tests/unit/ -v

test-integration:
	docker compose exec api pytest tests/integration/ -v

test-cov:
	docker compose exec api pytest tests/ --cov --cov-report=html
	open api/htmlcov/index.html
```

## Test Data

Tests use sample CrashDriver entities with:
- **Peter Wimsey** (appears 2x - duplicate)
- **Harriet Vane** (unique)
- **Jason Ohlendorf** (unique, from NIECE data)

## What Tests Verify

### ✅ **Core Functionality**
- Duplicate entities are detected
- ResolvedEntity nodes created
- RESOLVED_TO relationships established
- Senzing is actually used (not text-based fallback)

### ✅ **Graph Isolation**
- `_upload_ids` aggregated from all resolved entities
- `_schema_ids` aggregated correctly
- `sourceDocs` tracks all source files

### ✅ **Data Integrity**
- Original entities unchanged
- No data loss during resolution
- Clean reset removes all resolution data

### ✅ **Error Handling**
- Graceful fallback when Senzing unavailable
- Empty datasets handled
- Invalid inputs rejected

### ✅ **API Contract**
- All endpoints return expected structure
- Status accurately reflects resolution state
- Reset completely cleans up

## Running Tests After Code Changes

**Before committing:**
```bash
# Run all tests
docker compose exec api pytest tests/ -v

# Check coverage
docker compose exec api pytest tests/ --cov --cov-report=term-missing

# Ensure >80% coverage on entity resolution code
```

**What should ALWAYS pass:**
- All unit tests (isolated, fast)
- Integration test: duplicate detection
- Integration test: reset functionality
- No regressions in existing features

## Troubleshooting

**If tests fail:**
1. Check all services are running: `docker compose ps`
2. Verify Senzing gRPC server is accessible: `nc -zv localhost 8261`
3. Check API logs: `docker compose logs api --tail=100`
4. Ensure PostgreSQL has Senzing data: Check senzing-init completed
5. Run with verbose output: `pytest tests/ -vv -s`

**To rebuild test environment:**
```bash
docker compose down
docker volume rm schema-designer1_senzing-postgres-data
docker compose up -d
```

## Test Maintenance

- Update tests when adding new Senzing features
- Add regression tests for any bugs found
- Keep test data minimal but representative
- Mock external dependencies in unit tests
- Use real services for integration tests
