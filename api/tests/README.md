# API Tests

## Overview
This directory contains the test suite for the NIEM API, including unit tests and integration tests.

## Prerequisites

Install the required dependencies:

```bash
# Install application dependencies
pip install -r requirements.txt

# Install test dependencies
pip install -r requirements-test.txt

# Install the package in editable mode (required for imports to work)
pip install -e .
```

## Running Tests

### All Tests
```bash
# Run all tests with coverage
pytest

# Run all tests without coverage (faster)
pytest -p no:cov
```

### Specific Test Categories
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests in a specific file
pytest tests/unit/handlers/test_admin.py

# Run a specific test function
pytest tests/unit/handlers/test_admin.py::test_reset_dry_run_returns_expected_structure
```

### With Verbose Output
```bash
pytest -v
```

### With Coverage Report
```bash
# Terminal report
pytest --cov=src --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Test Structure

```
tests/
├── README.md                           # This file
├── integration/                        # Integration tests (require services)
│   ├── test_minio_integration.py      # MinIO S3 storage tests
│   ├── test_neo4j_integration.py      # Neo4j graph database tests
│   └── test_ndr_validation_integration.py  # NIEM NDR validation tests
├── unit/                               # Unit tests (fast, isolated)
│   ├── clients/                        # Client layer tests
│   ├── handlers/                       # HTTP handler tests
│   └── services/                       # Service layer tests
└── utils/                              # Test utilities and helpers
    └── test_helpers.py
```

## Test Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Fast, isolated unit tests (no external dependencies)
- `@pytest.mark.integration` - Tests requiring external services (Neo4j, MinIO)
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.smoke` - Critical functionality smoke tests
- `@pytest.mark.security` - Security-related tests
- `@pytest.mark.performance` - Performance benchmark tests

## Configuration

Test configuration is defined in:
- `pytest.ini` - Main pytest configuration
- `pyproject.toml` - Additional pytest and coverage settings

### Key Settings
- **Coverage threshold**: 80%
- **Test timeout**: 300 seconds (5 minutes)
- **Python path**: `src/` (automatically configured)

## Integration Tests

Integration tests require external services. Use Docker Compose to start them:

```bash
# From project root
docker compose up -d neo4j minio

# Run integration tests
pytest -m integration

# Stop services
docker compose down
```

## Troubleshooting

### ModuleNotFoundError: No module named 'niem_api'
The `pythonpath = src` setting in `pytest.ini` should fix this automatically. If it doesn't work, ensure you're running pytest from the `api/` directory:
```bash
cd api
pytest
```

### Missing dependencies
Install both requirements files:
```bash
pip install -r requirements.txt -r requirements-test.txt
```

### Tests timing out
Adjust the timeout in `pytest.ini`:
```ini
timeout = 600  # Increase to 10 minutes
```

### Integration tests failing
Ensure Docker services are running:
```bash
docker compose ps
docker compose logs neo4j minio
```

## Writing New Tests

### Unit Test Example
```python
import pytest
from niem_api.handlers.admin import reset_system

@pytest.mark.unit
def test_reset_dry_run():
    """Test dry run returns expected structure without deleting."""
    result = reset_system(dry_run=True)
    assert result["dry_run"] is True
    assert "schemas_to_delete" in result
```

### Integration Test Example
```python
import pytest
from niem_api.clients.neo4j_client import Neo4jClient

@pytest.mark.integration
async def test_neo4j_connection():
    """Test Neo4j connection works."""
    client = Neo4jClient()
    await client.verify_connectivity()
    assert client.is_connected()
```

## Continuous Integration

Tests are automatically run in CI/CD pipelines. See `.github/workflows/test.yml` for the CI configuration.

## Code Coverage

Current coverage requirement: **80%**

View coverage report:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

Areas excluded from coverage:
- Abstract methods
- `if __name__ == "__main__"` blocks
- Type checking blocks (`if TYPE_CHECKING:`)
- Debug/repr methods
