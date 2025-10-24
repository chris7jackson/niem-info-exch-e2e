import { test, expect } from '@playwright/test';
import { SchemaManagerPage } from '../page-objects/SchemaManagerPage';

/**
 * Schema Upload E2E Tests
 *
 * These tests cover the complete schema upload workflow:
 * - Uploading valid XSD schemas
 * - Handling invalid schemas
 * - Schema activation
 * - Schema deletion
 *
 * Prerequisites:
 * - Backend API running on localhost:8000
 * - Next.js dev server running on localhost:3000
 */
test.describe('Schema Upload Flow', () => {
  let schemaPage: SchemaManagerPage;

  test.beforeEach(async ({ page }) => {
    schemaPage = new SchemaManagerPage(page);
    await schemaPage.goto();
  });

  test('E2E-001: Upload valid schema successfully', async ({ page }) => {
    // ACT: Upload a valid XSD schema
    await schemaPage.uploadSchema('valid-simple.xsd');

    // ASSERT: Success message appears
    await schemaPage.waitForUploadComplete();

    // ASSERT: Schema appears in the list
    const schemaExists = await schemaPage.schemaExists('valid-simple.xsd');
    expect(schemaExists).toBeTruthy();

    // Take screenshot for visual verification
    await schemaPage.screenshot('schema-upload-success');
  });

  test('E2E-002: Upload invalid schema shows error', async ({ page }) => {
    // ACT: Upload an invalid XSD schema
    await schemaPage.uploadSchema('invalid-syntax.xsd');

    // ASSERT: Error message appears
    const errorMessage = await schemaPage.getErrorMessage();
    expect(errorMessage).toContain('validation');

    // ASSERT: Schema does NOT appear in list
    const schemaExists = await schemaPage.schemaExists('invalid-syntax.xsd');
    expect(schemaExists).toBeFalsy();

    // Take screenshot of error state
    await schemaPage.screenshot('schema-upload-error');
  });

  test('E2E-003: Uploaded schema is marked as active', async ({ page }) => {
    // ARRANGE: Upload a schema
    await schemaPage.uploadSchema('valid-simple.xsd');
    await schemaPage.waitForUploadComplete();

    // ASSERT: Schema has "Active" badge
    const isActive = await schemaPage.isSchemaActive('valid-simple.xsd');
    expect(isActive).toBeTruthy();
  });

  test('E2E-004: Can view uploaded schemas list', async ({ page }) => {
    // ARRANGE: Upload a schema
    await schemaPage.uploadSchema('valid-simple.xsd');
    await schemaPage.waitForUploadComplete();

    // ACT: Get all schema names
    const schemaNames = await schemaPage.getAllSchemaNames();

    // ASSERT: Our schema is in the list
    expect(schemaNames.length).toBeGreaterThan(0);
    expect(schemaNames.some((name) => name.includes('valid-simple'))).toBeTruthy();
  });
});

/**
 * Schema Management E2E Tests
 *
 * Tests for managing existing schemas:
 * - Activation
 * - Deletion
 * - Viewing details
 */
test.describe('Schema Management Flow', () => {
  let schemaPage: SchemaManagerPage;

  test.beforeEach(async ({ page }) => {
    schemaPage = new SchemaManagerPage(page);
    await schemaPage.goto();

    // Upload a test schema for management tests
    await schemaPage.uploadSchema('valid-simple.xsd');
    await schemaPage.waitForUploadComplete();
  });

  test('E2E-005: Can navigate to schema manager', async ({ page }) => {
    // ASSERT: Page title is correct
    await expect(page.locator('h1')).toContainText('Schema Management');

    // ASSERT: Key UI elements are present
    await expect(page.locator('text=/upload.*schema/i')).toBeVisible();
  });
});
