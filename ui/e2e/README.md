# E2E Test Suite

End-to-end tests for the NIEM GraphRAG UI using Playwright.

## Overview

This E2E test suite validates complete user workflows in a real browser environment, covering scenarios that cannot be tested with unit tests (like file uploads, graph interactions, and multi-page workflows).

## Test Structure

```
e2e/
├── fixtures/          # Test data files
│   ├── schemas/       # Sample XSD schemas
│   └── data/          # Sample XML data files
├── page-objects/      # Page Object Models
│   ├── BasePage.ts
│   ├── SchemaManagerPage.ts
│   ├── GraphPage.ts
│   └── DataIngestionPage.ts
├── tests/             # Test specs
│   ├── schema-upload.spec.ts
│   ├── graph-interaction.spec.ts
│   ├── data-ingestion.spec.ts
│   └── critical-path.spec.ts
└── utils/             # Test utilities
```

## Test Suites

### 1. Schema Upload Tests (`schema-upload.spec.ts`)
- **E2E-001**: Upload valid schema successfully
- **E2E-002**: Upload invalid schema shows error
- **E2E-003**: Uploaded schema is marked as active
- **E2E-004**: Can view uploaded schemas list
- **E2E-005**: Can navigate to schema manager

**Coverage**: Schema upload, validation, activation, listing

### 2. Graph Interaction Tests (`graph-interaction.spec.ts`)
- **E2E-101**: Graph page renders with controls
- **E2E-102**: Graph loads and displays statistics
- **E2E-103**: Can execute custom Cypher query
- **E2E-104**: Can change graph layout
- **E2E-105**: Handles invalid Cypher syntax
- **E2E-106**: Handles empty database gracefully
- **E2E-107**: Can toggle node labels
- **E2E-108**: Can zoom in and out

**Coverage**: Graph visualization, Cypher queries, layouts, interactions

### 3. Data Ingestion Tests (`data-ingestion.spec.ts`)
- **E2E-201**: Successfully ingest valid XML file
- **E2E-202**: Can ingest multiple XML files
- **E2E-203**: Shows error for invalid XML
- **E2E-204**: Can remove file before ingestion
- **E2E-205**: Shows "View in Graph" link after success
- **E2E-206**: Shows warning when no schema exists
- **E2E-207**: Shows progress indicator during ingestion

**Coverage**: Data ingestion, validation, batch processing, error handling

### 4. Critical Path Test (`critical-path.spec.ts`)
- **E2E-301**: Complete workflow from schema to visualization
- **E2E-302**: Cannot ingest data without schema
- **E2E-303**: Graph shows empty state with no data

**Coverage**: Complete user journey, happy path, error scenarios

## Running Tests

### Prerequisites

1. **Backend API** must be running on `localhost:8000`
2. **Frontend dev server** must be running on `localhost:3000` (or will be started automatically)
3. **Neo4j database** should be running (if testing with real data)

### Commands

```bash
# Run all E2E tests
npm run test:e2e

# Run tests in UI mode (interactive)
npm run test:e2e:ui

# Run tests in debug mode
npm run test:e2e:debug

# Run specific test file
npx playwright test e2e/tests/schema-upload.spec.ts

# Run tests in a specific browser
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit

# Show HTML report
npm run test:e2e:report
```

### Running Against Different Environments

```bash
# Run against staging
BASE_URL=https://staging.example.com npm run test:e2e

# Run against production (be careful!)
BASE_URL=https://prod.example.com npm run test:e2e
```

## Test Data

### Fixtures

**Schemas** (`e2e/fixtures/schemas/`):
- `valid-simple.xsd` - Simple valid XSD schema
- `invalid-syntax.xsd` - Invalid XML syntax (for error testing)

**Data Files** (`e2e/fixtures/data/`):
- `valid-person.xml` - Valid Person XML document
- `valid-organization.xml` - Valid Organization XML document
- `invalid-xml.xml` - Malformed XML (for error testing)

### Adding New Fixtures

1. Add XSD file to `e2e/fixtures/schemas/`
2. Add XML file to `e2e/fixtures/data/`
3. Reference in tests: `await schemaPage.uploadSchema('your-file.xsd')`

## Page Object Model (POM)

All E2E tests use the Page Object Model pattern to:
- Encapsulate page interactions
- Improve test maintainability
- Reduce code duplication
- Provide better error messages

### Example Usage

```typescript
import { test } from '@playwright/test'
import { SchemaManagerPage } from '../page-objects/SchemaManagerPage'

test('upload schema', async ({ page }) => {
  const schemaPage = new SchemaManagerPage(page)
  await schemaPage.goto()
  await schemaPage.uploadSchema('valid-simple.xsd')
  await schemaPage.waitForUploadComplete()
})
```

## Writing New Tests

### 1. Create Test File

```typescript
// e2e/tests/my-feature.spec.ts
import { test, expect } from '@playwright/test'
import { MyPage } from '../page-objects/MyPage'

test.describe('My Feature', () => {
  test('E2E-XXX: should do something', async ({ page }) => {
    const myPage = new MyPage(page)
    await myPage.goto()

    // Test steps
    await myPage.doSomething()

    // Assertions
    await expect(page.locator('text=Success')).toBeVisible()
  })
})
```

### 2. Update Page Object (if needed)

```typescript
// e2e/page-objects/MyPage.ts
import { Page } from '@playwright/test'
import { BasePage } from './BasePage'

export class MyPage extends BasePage {
  async doSomething() {
    await this.page.click('button.my-button')
  }
}
```

### 3. Add Test Data (if needed)

- Add fixtures to `e2e/fixtures/`
- Update README with new fixture documentation

## Best Practices

### DO ✅
- Use Page Object Model for all interactions
- Wait for elements explicitly (avoid hardcoded waits)
- Take screenshots on important steps
- Use descriptive test names with E2E-XXX IDs
- Test both happy path and error scenarios
- Clean up test data when necessary

### DON'T ❌
- Use `page.waitForTimeout()` unless absolutely necessary
- Hardcode URLs (use `baseURL` from config)
- Share state between tests (each test should be independent)
- Test implementation details (test user-visible behavior)
- Skip assertions (always verify expected outcomes)

## Debugging

### Visual Debugging

```bash
# Run tests in headed mode (see browser)
npx playwright test --headed

# Run tests in debug mode (step through)
npm run test:e2e:debug

# Run with UI mode (interactive)
npm run test:e2e:ui
```

### Troubleshooting

**Tests timing out?**
- Check backend API is running
- Check frontend dev server is running
- Increase timeout in `playwright.config.ts`

**File upload tests failing?**
- Verify fixture files exist in `e2e/fixtures/`
- Check file paths are correct
- Ensure backend accepts multipart/form-data

**Graph tests failing?**
- Ensure Neo4j is running
- Check data was successfully ingested
- Verify Cytoscape renders correctly

## CI/CD Integration

Tests run automatically in GitHub Actions on:
- Pull requests to `main` or `develop`
- Pushes to `main` or `develop`

### CI Configuration

See `.github/workflows/test.yml` for:
- Unit tests (fast, run first)
- E2E tests (slower, run after unit tests pass)
- Artifact uploads (screenshots, videos, reports)

### Viewing CI Results

- Test results: Check GitHub Actions workflow
- Screenshots: Download from workflow artifacts
- Videos: Download from workflow artifacts (only on failure)
- HTML Report: Download and open `playwright-report/index.html`

## Performance

### Test Execution Times

- **Unit tests**: ~3 seconds (15 tests)
- **E2E tests**: ~5 minutes (all tests in parallel)
- **Critical path**: ~1-2 minutes (single test)

### Optimization Tips

- Run tests in parallel (default with Playwright)
- Use `fullyParallel: true` in config
- Mock external dependencies when possible
- Use `reuseDev Server: true` for local development

## Maintenance

### When to Update Tests

- **UI changes**: Update selectors in Page Objects
- **New features**: Add new test specs
- **API changes**: Update fixtures and expectations
- **Bug fixes**: Add regression tests

### Review Checklist

- [ ] Tests pass locally
- [ ] Tests pass in CI
- [ ] Screenshots look correct
- [ ] Test names are descriptive
- [ ] Page Objects are updated
- [ ] README is updated (if needed)

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Page Object Model Pattern](https://playwright.dev/docs/pom)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [Debugging](https://playwright.dev/docs/debug)

## Support

For questions or issues:
1. Check this README
2. Review Playwright docs
3. Check existing tests for examples
4. Ask the team in #testing channel
