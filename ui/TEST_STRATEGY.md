# UI Test Strategy

## Overview

This document outlines the comprehensive test strategy for the NIEM GraphRAG UI, balancing fast unit tests with thorough end-to-end tests to achieve high confidence with minimal maintenance overhead.

## Strategy Summary

We use a **balanced test pyramid**:
- **Unit Tests (15)**: Fast feedback on component rendering and API client logic
- **E2E Tests (20+)**: Complete user workflows including file uploads and interactions

## Test Organization

### Directory Structure

We follow **co-located unit tests** with **separate E2E tests**:

```
ui/
├── src/
│   ├── components/
│   │   ├── SchemaManager.tsx
│   │   └── SchemaManager.test.tsx      # Unit test co-located
│   ├── lib/
│   │   ├── api.ts
│   │   └── api.test.ts                 # Unit test co-located
│   ├── pages/
│   │   ├── graph.tsx
│   │   └── graph.test.tsx              # Unit test co-located
│   └── test/
│       └── setup.ts                    # Global test configuration
└── e2e/                                # E2E tests separate
    ├── tests/
    ├── page-objects/
    └── fixtures/
```

**Why this structure?**
- ✅ **Unit tests co-located**: Easy to find and maintain alongside source code
- ✅ **E2E tests separate**: Different purpose, tooling (Playwright), and fixtures
- ✅ **Global config isolated**: Shared test setup in `src/test/setup.ts`
- ✅ **Clear separation**: Unit tests for logic, E2E tests for workflows
- ✅ **Standard practice**: Follows Next.js and Vitest conventions

### Naming Conventions

- **Unit tests**: `*.test.{ts,tsx}` (Vitest + React Testing Library)
- **E2E tests**: `*.spec.ts` (Playwright)
- **Test setup**: `setup.ts` (global mocks and configuration)

---

## Test Coverage

### Unit Tests (Vitest + React Testing Library + MSW)

**Location**: Co-located with source files (`src/**/*.test.{ts,tsx}`)

#### API Client Tests (`src/lib/api.test.ts`) - 8 tests
- ✅ Schema management (getSchemas, activateSchema)
- ✅ Data ingestion metadata (getUploadedFiles)
- ✅ Admin operations (resetSystem, getNeo4jStats)
- ✅ Authentication (token handling, auth errors)
- ✅ Error handling (401, 500 responses)

**Purpose**: Verify HTTP requests are formatted correctly and responses are handled properly.

**Execution time**: <1 second

#### Schema Manager Tests (`src/components/SchemaManager.test.tsx`) - 3 tests
- ✅ Component renders without crashing
- ✅ Displays API data correctly
- ✅ Schema activation workflow

**Purpose**: Smoke tests for component rendering and data display.

**Execution time**: <1 second

#### Graph Page Tests (`src/pages/graph.test.tsx`) - 4 tests
- ✅ Component renders with controls
- ✅ Loads and displays graph statistics
- ✅ Handles server errors gracefully
- ✅ Handles invalid Cypher syntax

**Purpose**: Verify graph component renders and handles data/errors correctly.

**Execution time**: <1 second

**Total Unit Test Execution**: ~3 seconds

---

### E2E Tests (Playwright)

**Location**: `e2e/tests/*.spec.ts`

#### Schema Upload Tests (`schema-upload.spec.ts`) - 5 tests
- E2E-001: Upload valid schema successfully
- E2E-002: Upload invalid schema shows error
- E2E-003: Uploaded schema is marked as active
- E2E-004: Can view uploaded schemas list
- E2E-005: Can navigate to schema manager

**Why E2E**: File uploads cannot be reliably tested in jsdom, require real browser APIs.

#### Graph Interaction Tests (`graph-interaction.spec.ts`) - 8 tests
- E2E-101: Graph page renders with controls
- E2E-102: Graph loads and displays statistics
- E2E-103: Can execute custom Cypher query
- E2E-104: Can change graph layout
- E2E-105: Handles invalid Cypher syntax
- E2E-106: Handles empty database gracefully
- E2E-107: Can toggle node labels
- E2E-108: Can zoom in and out

**Why E2E**: Cytoscape interactions (zoom, pan, click) require real DOM and canvas rendering.

#### Data Ingestion Tests (`data-ingestion.spec.ts`) - 7 tests
- E2E-201: Successfully ingest valid XML file
- E2E-202: Can ingest multiple XML files
- E2E-203: Shows error for invalid XML
- E2E-204: Can remove file before ingestion
- E2E-205: Shows "View in Graph" link after success
- E2E-206: Shows warning when no schema exists
- E2E-207: Shows progress indicator during ingestion

**Why E2E**: Tests complete data flow from upload through backend processing to UI feedback.

#### Critical Path Tests (`critical-path.spec.ts`) - 3 tests
- E2E-301: Complete workflow from schema to visualization
- E2E-302: Cannot ingest data without schema
- E2E-303: Graph shows empty state with no data

**Why E2E**: Validates entire user journey across multiple pages and systems.

**Total E2E Test Execution**: ~5 minutes (parallelized)

---

## Test Pyramid Metrics

```
       /\
      /  \  E2E Tests
     /____\ 20+ tests (~5 min)
    /      \
   / Unit   \ 15 tests (~3 sec)
  /  Tests   \
 /____________\
```

### Coverage Targets

- **Unit Tests**: 70% code coverage for src/lib and src/components
- **E2E Tests**: 100% coverage of critical user paths
- **Total Test Count**: ~35 tests
- **Total Execution Time**:
  - Unit only: 3 seconds
  - E2E only: 5 minutes
  - All tests: 5 minutes (parallel)

---

## What Changed

### Removed (High Maintenance, Low Value)

❌ **Deleted 5 SchemaManager file upload unit tests**
- Reason: jsdom can't reliably simulate file uploads
- Moved to: E2E tests with real browser

❌ **Removed 2 redundant graph unit tests**
- "executes custom cypher queries" - redundant with load test
- "validates query input" - doesn't actually test validation
- Moved to: E2E tests for complete query workflows

### Added (High Value, Manageable Maintenance)

✅ **Playwright E2E Test Suite**
- Real browser testing
- File upload workflows
- Graph interactions
- Complete user journeys

✅ **Page Object Model Pattern**
- Encapsulates UI interactions
- Easy to update when UI changes
- Reduces test maintenance

✅ **Comprehensive Test Fixtures**
- Sample XSD schemas
- Sample XML data files
- Invalid files for error testing

✅ **JSDoc Documentation**
- Every test suite documented
- Purpose and scope clearly defined
- Maintenance instructions included

---

## When to Use Each Test Type

### Use Unit Tests For:
✅ API client method logic
✅ Component rendering (smoke tests)
✅ Error state handling
✅ Data transformation
✅ Utility functions

### Use E2E Tests For:
✅ File uploads
✅ Multi-page workflows
✅ Graph visualizations
✅ Real backend integration
✅ Critical user journeys

### Don't Test:
❌ Third-party libraries (Cytoscape, Next.js)
❌ Implementation details (internal state)
❌ Styling (use visual regression instead)
❌ Already covered by backend tests

---

## Running Tests

### Local Development

```bash
# Run unit tests (fast feedback)
npm run test

# Run unit tests in watch mode
npm run test:watch

# Run E2E tests (requires backend running)
npm run test:e2e

# Run E2E tests in UI mode (interactive)
npm run test:e2e:ui

# Run all tests
npm run test:all
```

### CI/CD Pipeline

```bash
# Runs automatically on PR and push to main
1. Lint check
2. Type check
3. Unit tests (fail fast)
4. Build
5. E2E tests (only if unit tests pass)
6. Upload artifacts (screenshots, videos, reports)
```

---

## Maintenance Guidelines

### When UI Changes

1. **Locators break** → Update Page Objects only (not individual tests)
2. **New feature** → Add E2E test if it's a user-facing workflow
3. **Bug fix** → Add regression test at appropriate level

### Monthly Review

- [ ] Remove flaky tests or fix root cause
- [ ] Archive obsolete test fixtures
- [ ] Update documentation
- [ ] Review test execution times
- [ ] Check coverage reports

### Test Health Metrics

Monitor these metrics monthly:

- **Flakiness Rate**: <5% (E2E tests may retry)
- **Execution Time**: Unit <5s, E2E <10min
- **Pass Rate**: >95% on main branch
- **Coverage**: >70% unit, 100% critical paths

---

## Best Practices

### Unit Tests

```typescript
/**
 * Good: Tests component behavior
 */
test('displays error message when API fails', async () => {
  server.use(
    http.get('/api/schema', () => HttpResponse.error())
  )
  render(<SchemaManager />)
  await waitFor(() => {
    expect(screen.getByText(/error/i)).toBeInTheDocument()
  })
})

/**
 * Bad: Tests implementation details
 */
test('calls useState hook', () => {
  // Don't test hooks directly
})
```

### E2E Tests

```typescript
/**
 * Good: Tests user workflow
 */
test('user can upload schema and view in list', async ({ page }) => {
  const schemaPage = new SchemaManagerPage(page)
  await schemaPage.goto()
  await schemaPage.uploadSchema('valid.xsd')
  expect(await schemaPage.schemaExists('valid.xsd')).toBe(true)
})

/**
 * Bad: Tests too many things
 */
test('tests entire application', async ({ page }) => {
  // Split into multiple focused tests
})
```

---

## Test Data Management

### Fixtures

- **Location**: `e2e/fixtures/`
- **Schemas**: Simple, valid XSD files
- **Data**: Small XML files (<10KB)
- **Invalid Files**: For error testing

### Database State

- **Unit Tests**: No database (MSW mocks)
- **E2E Tests**: Clean state before each test
- **CI**: Fresh database per test run

---

## Troubleshooting

### Unit Tests Failing

1. Check MSW handlers are correct
2. Verify mock data structure matches API
3. Check for async/await issues
4. Review component props

### E2E Tests Failing

1. Ensure backend is running on localhost:8000
2. Check test fixtures exist
3. Verify selectors haven't changed
4. Review screenshots in artifacts
5. Run in headed mode: `npx playwright test --headed`

### Flaky Tests

1. Add explicit waits instead of arbitrary timeouts
2. Check for race conditions
3. Verify test isolation (no shared state)
4. Review CI logs for environment issues

---

## Future Improvements

### Short Term (Next Sprint)
- [ ] Add visual regression testing (Percy/Chromatic)
- [ ] Configure coverage thresholds in CI
- [ ] Add performance benchmarks to E2E tests

### Long Term (Next Quarter)
- [ ] Implement contract testing for API
- [ ] Add accessibility tests (axe-core)
- [ ] Create load tests for graph visualization
- [ ] Set up test data generator

---

## Resources

- [Vitest Documentation](https://vitest.dev)
- [React Testing Library](https://testing-library.com/react)
- [Playwright Documentation](https://playwright.dev)
- [Testing Trophy](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications)
- [Page Object Model](https://playwright.dev/docs/pom)

---

## Team Contacts

- **Test Strategy**: Development Team
- **CI/CD Pipeline**: DevOps Team
- **Test Infrastructure**: QA Team

---

## Changelog

### 2025-01-XX
- Initial test strategy document
- Migrated from 22 unit tests to 15 unit + 20+ E2E
- Removed file upload unit tests (moved to E2E)
- Added comprehensive Page Object Models
- Configured Playwright for E2E testing
- Created test fixtures and documentation

---

**Last Updated**: 2025-01-XX
**Next Review**: 2025-02-XX
