# Unit Testing Guide

**Focus**: Unit testing for API (Python/FastAPI) and UI (Next.js/React/TypeScript)

**Scope**: This guide covers unit testing only. Integration and E2E testing are out of scope.

---

## Table of Contents

1. [Philosophy and Principles](#philosophy-and-principles)
2. [API Unit Testing (Python/FastAPI)](#api-unit-testing-pythonfastapi)
3. [UI Unit Testing (Next.js/React/TypeScript)](#ui-unit-testing-nextjsreacttypescript)
4. [Best Practices](#best-practices)
5. [Coverage Requirements](#coverage-requirements)
6. [Running Tests](#running-tests)
7. [Test Templates](#test-templates)

---

## Philosophy and Principles

### What is a Unit Test?

A **unit test** validates a single unit of code (function, method, component) in **isolation** from external dependencies.

**Characteristics of good unit tests**:
- ✅ **Fast**: Run in milliseconds
- ✅ **Isolated**: No external dependencies (databases, APIs, file systems)
- ✅ **Repeatable**: Same input = same output, every time
- ✅ **Self-validating**: Pass or fail, no manual inspection
- ✅ **Focused**: Test one thing at a time

### AAA Pattern

All unit tests should follow the **Arrange-Act-Assert (AAA)** pattern:

```python
def test_example():
    # ARRANGE: Set up test data and mocks
    user = User(name="Alice", age=30)

    # ACT: Execute the code under test
    result = user.is_adult()

    # ASSERT: Verify the result
    assert result is True
```

### Test Isolation

**Always mock external dependencies** to ensure tests are isolated:

❌ **Bad** (not isolated):
```python
def test_upload_schema():
    # Calls real S3 service - slow and unpredictable
    result = upload_to_s3(file_data)
    assert result is not None
```

✅ **Good** (isolated):
```python
def test_upload_schema(mock_s3):
    # Uses mock - fast and predictable
    mock_s3.put_object.return_value = {"status": "success"}
    result = upload_to_s3(file_data)
    assert result == {"status": "success"}
```

---

## API Unit Testing (Python/FastAPI)

### Framework and Tools

- **pytest** 7.4.3 - Testing framework
- **pytest-cov** - Code coverage
- **pytest-mock** - Mocking utilities
- **pytest-asyncio** - Async test support
- **factory-boy** - Test data factories

### Directory Structure

```
api/tests/
├── unit/                          # Unit tests only
│   ├── handlers/                  # HTTP handler tests
│   ├── services/                  # Business logic tests
│   ├── clients/                   # Client wrapper tests
│   └── models/                    # Data model tests
└── utils/
    ├── factories.py               # Test data factories
    └── test_helpers.py            # Helper functions
```

### Test File Naming

- Files: `test_*.py` (e.g., `test_admin.py`)
- Classes: `Test*` (e.g., `TestAdminHandlers`)
- Functions: `test_*` (e.g., `test_count_schemas`)

### Basic Test Structure

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException

from niem_api.handlers.admin import count_schemas, reset_neo4j
from niem_api.clients.neo4j_client import Neo4jClient


class TestAdminHandlers:
    """Test suite for admin handler functions"""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock MinIO S3 client"""
        mock_client = Mock()
        mock_client.bucket_exists.return_value = True
        return mock_client

    def test_count_schemas_with_objects(self, mock_s3_client):
        """Test counting schemas with objects in bucket"""
        # ARRANGE
        mock_objects = [Mock(), Mock(), Mock()]
        mock_s3_client.list_objects.return_value = iter(mock_objects)

        # ACT
        result = count_schemas(mock_s3_client)

        # ASSERT
        assert result == 3
        mock_s3_client.list_objects.assert_called_once_with(
            "niem-schemas",
            recursive=True
        )
```

### Async Test Support

Use `@pytest.mark.asyncio` for async functions:

```python
@pytest.mark.asyncio
async def test_async_handler():
    # ARRANGE
    mock_service = AsyncMock()
    mock_service.process.return_value = {"status": "success"}

    # ACT
    result = await handle_request(mock_service)

    # ASSERT
    assert result["status"] == "success"
    mock_service.process.assert_awaited_once()
```

### Mocking Strategies

#### 1. Mock Return Values

```python
def test_with_mock_return():
    mock_client = Mock()
    mock_client.get_data.return_value = {"id": 123, "name": "test"}

    result = process_data(mock_client)

    assert result["id"] == 123
```

#### 2. Mock Side Effects (for exceptions)

```python
def test_error_handling():
    mock_client = Mock()
    mock_client.connect.side_effect = ConnectionError("Connection failed")

    with pytest.raises(HTTPException) as exc_info:
        connect_to_service(mock_client)

    assert exc_info.value.status_code == 500
    assert "Connection failed" in str(exc_info.value.detail)
```

#### 3. Patch Dependencies

```python
@patch('niem_api.handlers.admin.Neo4jClient')
def test_with_patch(mock_neo4j_class):
    # ARRANGE
    mock_instance = Mock()
    mock_neo4j_class.return_value = mock_instance
    mock_instance.query.return_value = [{"count": 42}]

    # ACT
    result = get_node_count()

    # ASSERT
    assert result == 42
    mock_instance.query.assert_called_once()
```

### Testing Exception Handling

```python
def test_validation_error_handling():
    """Test that validation errors are raised correctly"""
    # ARRANGE
    invalid_data = {"missing": "required_field"}

    # ACT & ASSERT
    with pytest.raises(HTTPException) as exc_info:
        validate_schema(invalid_data)

    # Verify exception details
    assert exc_info.value.status_code == 400
    assert "required_field" in str(exc_info.value.detail)
```

### Using Fixtures

Fixtures provide reusable setup code:

```python
@pytest.fixture
def sample_schema():
    """Provide sample schema data for tests"""
    return {
        "schema_id": "test_schema_001",
        "namespace": "http://example.com/test",
        "version": "1.0"
    }

@pytest.fixture
def mock_neo4j():
    """Provide mock Neo4j client"""
    mock = Mock(spec=Neo4jClient)
    mock.query.return_value = []
    return mock

def test_with_fixtures(sample_schema, mock_neo4j):
    """Test using both fixtures"""
    result = store_schema(sample_schema, mock_neo4j)

    assert result is not None
    mock_neo4j.query.assert_called_once()
```

### Test Data Factories

Use factories for complex test data:

```python
from tests.utils.factories import SchemaResponseFactory, TestDataFactories

def test_with_factory():
    # Create test schema with defaults
    schema = SchemaResponseFactory()
    assert schema.schema_id.startswith("schema_")

    # Create with custom values
    schema = SchemaResponseFactory(
        schema_id="custom_123",
        is_active=False
    )
    assert schema.schema_id == "custom_123"

    # Use static factories for raw data
    xsd_content = TestDataFactories.sample_xsd_content()
    assert "<xs:schema" in xsd_content
```

### Parameterized Tests

Test multiple scenarios with one test:

```python
@pytest.mark.parametrize("input_value,expected", [
    (0, False),
    (17, False),
    (18, True),
    (100, True),
])
def test_is_adult(input_value, expected):
    """Test age validation with multiple inputs"""
    person = Person(age=input_value)
    assert person.is_adult() == expected
```

---

## UI Unit Testing (Next.js/React/TypeScript)

### Framework and Tools

- **vitest** 0.34.6 - Fast Vite-based test framework
- **@testing-library/react** - React component testing
- **@testing-library/user-event** - User interaction simulation
- **@testing-library/jest-dom** - Custom DOM matchers
- **msw** (Mock Service Worker) - API mocking

### Directory Structure

```
ui/src/
├── test/
│   ├── setup.ts                   # Global test setup
│   └── templates/                 # Test templates
│       ├── component.test.template.tsx
│       ├── api-client.test.template.ts
│       └── README.md
├── components/
│   ├── Component.tsx
│   └── Component.test.tsx         # Co-located with component
└── lib/
    ├── api.ts
    └── api.test.ts                # Co-located with module
```

### Test File Naming

- Files: `*.test.tsx`, `*.test.ts`, `*.spec.tsx`, `*.spec.ts`
- Test suites: `describe('ComponentName', () => {})`
- Test cases: `test('should do something', () => {})` or `it('should do something', () => {})`

### Component Test Structure

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, test, expect } from 'vitest'

import SchemaUpload from './SchemaUpload'

describe('SchemaUpload Component', () => {
  test('renders upload form correctly', () => {
    // ARRANGE
    const mockOnSuccess = vi.fn()

    // ACT
    render(<SchemaUpload onUploadSuccess={mockOnSuccess} />)

    // ASSERT
    expect(screen.getByText(/upload xsd schema/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /upload/i })).toBeInTheDocument()
  })

  test('handles file selection', async () => {
    // ARRANGE
    const user = userEvent.setup()
    render(<SchemaUpload onUploadSuccess={vi.fn()} />)

    const file = new File(['<schema>test</schema>'], 'test.xsd', {
      type: 'application/xml'
    })

    // ACT
    const input = screen.getByLabelText(/choose file/i)
    await user.upload(input, file)

    // ASSERT
    expect(input.files[0]).toBe(file)
    expect(input.files).toHaveLength(1)
  })
})
```

### Querying Components

**Prefer accessibility-focused queries** (in order of preference):

1. `getByRole` - Best for interactive elements
2. `getByLabelText` - Best for form fields
3. `getByPlaceholderText` - For inputs without labels
4. `getByText` - For non-interactive content
5. `getByTestId` - Last resort

```typescript
// ✅ Good: Accessible queries
const button = screen.getByRole('button', { name: /submit/i })
const input = screen.getByLabelText(/email address/i)
const heading = screen.getByRole('heading', { name: /welcome/i })

// ❌ Bad: Fragile queries
const button = screen.getByClassName('btn-submit')
const input = screen.getByTestId('email-input')
```

### User Interaction Testing

Use `@testing-library/user-event` for realistic interactions:

```typescript
import userEvent from '@testing-library/user-event'

test('handles user input', async () => {
  const user = userEvent.setup()
  render(<LoginForm />)

  // Type into input
  await user.type(screen.getByLabelText(/username/i), 'alice')
  await user.type(screen.getByLabelText(/password/i), 'secret123')

  // Click button
  await user.click(screen.getByRole('button', { name: /login/i }))

  // Verify result
  await waitFor(() => {
    expect(screen.getByText(/welcome, alice/i)).toBeInTheDocument()
  })
})
```

### Mocking API Calls with MSW

MSW (Mock Service Worker) provides realistic HTTP mocking:

```typescript
import { rest } from 'msw'
import { setupServer } from 'msw/node'

// Define mock handlers
const server = setupServer(
  rest.post('/api/schema/xsd', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        schema_id: 'test_schema_123',
        is_active: true
      })
    )
  })
)

// Setup/teardown
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

test('uploads schema successfully', async () => {
  const user = userEvent.setup()
  render(<SchemaUpload onUploadSuccess={vi.fn()} />)

  const file = new File(['<schema/>'], 'test.xsd', { type: 'application/xml' })
  await user.upload(screen.getByLabelText(/choose file/i), file)
  await user.click(screen.getByRole('button', { name: /upload/i }))

  await waitFor(() => {
    expect(screen.getByText(/upload successful/i)).toBeInTheDocument()
  })
})

test('handles upload error', async () => {
  // Override handler for this test
  server.use(
    rest.post('/api/schema/xsd', (req, res, ctx) => {
      return res(
        ctx.status(400),
        ctx.json({ detail: 'Validation failed' })
      )
    })
  )

  const user = userEvent.setup()
  render(<SchemaUpload onUploadSuccess={vi.fn()} />)

  const file = new File(['invalid'], 'test.xsd', { type: 'application/xml' })
  await user.upload(screen.getByLabelText(/choose file/i), file)
  await user.click(screen.getByRole('button', { name: /upload/i }))

  await waitFor(() => {
    expect(screen.getByText(/validation failed/i)).toBeInTheDocument()
  })
})
```

### Testing Async State

Use `waitFor` for async state changes:

```typescript
test('displays loading state', async () => {
  render(<DataFetcher />)

  // Initially shows loading
  expect(screen.getByText(/loading/i)).toBeInTheDocument()

  // Wait for data to load
  await waitFor(() => {
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
  })

  // Data is displayed
  expect(screen.getByText(/data loaded/i)).toBeInTheDocument()
})
```

### Testing Component Props

```typescript
test('calls callback on success', async () => {
  const mockCallback = vi.fn()
  const user = userEvent.setup()

  render(<Form onSuccess={mockCallback} />)

  await user.click(screen.getByRole('button', { name: /submit/i }))

  await waitFor(() => {
    expect(mockCallback).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'success' })
    )
  })
})
```

### Testing Conditional Rendering

```typescript
test('shows error when validation fails', () => {
  const { rerender } = render(<FormField error={null} />)

  // No error initially
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()

  // Rerender with error
  rerender(<FormField error="Required field" />)

  // Error is displayed
  expect(screen.getByRole('alert')).toHaveTextContent(/required field/i)
})
```

---

## Best Practices

### 1. One Assertion Per Test (When Possible)

❌ **Bad**: Testing multiple things
```typescript
test('user registration', () => {
  const user = createUser('alice', 'alice@example.com')
  expect(user.name).toBe('alice')
  expect(user.email).toBe('alice@example.com')
  expect(user.isActive).toBe(true)
  expect(user.createdAt).toBeDefined()
})
```

✅ **Good**: Focused tests
```typescript
test('creates user with correct name', () => {
  const user = createUser('alice', 'alice@example.com')
  expect(user.name).toBe('alice')
})

test('creates user with active status', () => {
  const user = createUser('alice', 'alice@example.com')
  expect(user.isActive).toBe(true)
})
```

### 2. Descriptive Test Names

Use descriptive names that explain **what** is tested and **what** the expected behavior is:

❌ **Bad**:
```python
def test_user():
def test_case_1():
def test_success():
```

✅ **Good**:
```python
def test_count_schemas_returns_zero_when_bucket_empty():
def test_upload_schema_raises_400_when_file_invalid():
def test_validate_xml_succeeds_with_valid_niem_content():
```

### 3. Test Behavior, Not Implementation

❌ **Bad**: Testing implementation details
```typescript
test('uses useState hook', () => {
  // Don't test that a component uses specific React APIs
})
```

✅ **Good**: Testing behavior
```typescript
test('updates display when button clicked', async () => {
  const user = userEvent.setup()
  render(<Counter />)

  await user.click(screen.getByRole('button', { name: /increment/i }))

  expect(screen.getByText(/count: 1/i)).toBeInTheDocument()
})
```

### 4. Avoid Test Interdependence

Each test must be independent and not rely on other tests:

❌ **Bad**: Tests depend on order
```python
counter = 0

def test_increment():
    global counter
    counter += 1
    assert counter == 1

def test_increment_again():  # Depends on previous test!
    global counter
    counter += 1
    assert counter == 2
```

✅ **Good**: Independent tests
```python
def test_increment():
    counter = Counter(0)
    counter.increment()
    assert counter.value == 1

def test_increment_from_zero():
    counter = Counter(0)
    counter.increment()
    assert counter.value == 1
```

### 5. Use Fixtures and Factories for Setup

Avoid duplicated setup code:

✅ **Good**:
```python
@pytest.fixture
def sample_user():
    return User(name="Alice", email="alice@example.com")

def test_user_greeting(sample_user):
    assert sample_user.greeting() == "Hello, Alice"

def test_user_email(sample_user):
    assert sample_user.email == "alice@example.com"
```

### 6. Mock at the Right Level

Mock at the **boundary** of your unit:

❌ **Bad**: Mocking internal implementation
```python
@patch('my_module.internal_helper_function')
def test_business_logic(mock_helper):
    # Don't mock internal functions
    pass
```

✅ **Good**: Mocking external dependencies
```python
@patch('my_module.external_api_client')
def test_business_logic(mock_api):
    # Mock external services at the boundary
    mock_api.fetch_data.return_value = {"result": "success"}
    # Test your logic
```

### 7. Test Edge Cases

Don't just test the happy path:

```python
def test_divide_by_zero_raises_error():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

def test_empty_list_returns_none():
    result = get_first_element([])
    assert result is None

def test_negative_age_raises_validation_error():
    with pytest.raises(ValidationError):
        Person(age=-5)
```

### 8. Keep Tests Simple

Tests should be easier to understand than the code they test:

❌ **Bad**: Complex test logic
```python
def test_complex():
    data = [generate_random_data() for _ in range(100)]
    expected = [complex_transformation(d) for d in data]
    result = process_batch(data)
    for i, item in enumerate(result):
        assert item == expected[i]
```

✅ **Good**: Simple, explicit test
```python
def test_process_batch_transforms_data():
    data = [{"value": 1}, {"value": 2}]
    result = process_batch(data)
    assert result == [{"value": 2}, {"value": 4}]
```

---

## Coverage Requirements

### API (Python)

**Minimum**: 80% coverage enforced by pytest

```bash
pytest --cov=src --cov-fail-under=80
```

**Coverage is measured for**:
- Line coverage
- Branch coverage

**Excluded from coverage**:
- Test files
- `__init__.py` files
- Migration scripts

### UI (TypeScript)

**Minimum**: 70% coverage (configured in vitest.config.ts)

```bash
npm run test:coverage
```

**Coverage thresholds**:
- Lines: 70%
- Functions: 70%
- Branches: 70%
- Statements: 70%

**Excluded from coverage**:
- Test files (`*.test.ts`, `*.spec.ts`)
- Config files (`*.config.ts`)
- Type definitions (`*.d.ts`)
- Next.js generated files (`.next/`)

---

## Running Tests

### API Tests

```bash
cd api

# Run all unit tests
pytest tests/unit -v

# Run specific test file
pytest tests/unit/handlers/test_admin.py -v

# Run specific test function
pytest tests/unit/handlers/test_admin.py::TestAdminHandlers::test_count_schemas -v

# Run with coverage report
pytest tests/unit --cov=src --cov-report=html
open htmlcov/index.html

# Run tests matching a pattern
pytest tests/unit -k "test_schema" -v

# Run in parallel (faster)
pytest tests/unit -n auto
```

### UI Tests

```bash
cd ui

# Run all tests in watch mode
npm test

# Run all tests once (CI mode)
npm run test:run

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- SchemaUpload.test.tsx

# Run with UI dashboard
npm run test:ui

# Run tests matching a pattern
npm test -- --grep "upload"
```

### Debugging Tests

**API (Python)**:
```bash
# Run with verbose output
pytest tests/unit -vv

# Show print statements
pytest tests/unit -s

# Drop into debugger on failure
pytest tests/unit --pdb

# Show local variables on failure
pytest tests/unit -l
```

**UI (TypeScript)**:
```bash
# Run in debug mode
npm test -- --inspect

# Run with verbose output
npm test -- --reporter=verbose

# Update snapshots (if using snapshot testing)
npm test -- -u
```

---

## Test Templates

See `ui/src/test/templates/` for ready-to-use test templates:

- `component.test.template.tsx` - React component test template
- `api-client.test.template.ts` - API client test template
- `README.md` - Template usage guide

**Example usage**:
```bash
cd ui/src/test/templates
cp component.test.template.tsx ../../components/MyComponent.test.tsx
# Edit MyComponent.test.tsx and replace placeholders
```

---

## Additional Resources

### API Testing
- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)

### UI Testing
- [Vitest documentation](https://vitest.dev/)
- [React Testing Library documentation](https://testing-library.com/react)
- [Testing Library queries](https://testing-library.com/docs/queries/about)
- [MSW documentation](https://mswjs.io/)
- [user-event documentation](https://testing-library.com/docs/user-event/intro)

### Best Practices
- [Testing Best Practices (Kent C. Dodds)](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Effective Python Testing](https://realpython.com/pytest-python-testing/)

---

## Questions?

For questions or suggestions about testing:
1. Check existing test files for examples
2. Review this documentation
3. Ask the team in development channels

**Remember**: Good tests make refactoring safe and catch bugs early. Invest time in writing quality tests!
