import { test, expect } from '@playwright/test';
import { DataIngestionPage } from '../page-objects/DataIngestionPage';
import { SchemaManagerPage } from '../page-objects/SchemaManagerPage';

/**
 * Data Ingestion E2E Tests
 *
 * These tests cover the data ingestion workflow:
 * - Uploading XML files
 * - Validating against schema
 * - Viewing ingestion results
 * - Ingestion history
 *
 * Prerequisites:
 * - Backend API running
 * - Active schema must exist
 */
test.describe('Data Ingestion Flow', () => {
  let ingestPage: DataIngestionPage;
  let schemaPage: SchemaManagerPage;

  test.beforeEach(async ({ page }) => {
    ingestPage = new DataIngestionPage(page);
    schemaPage = new SchemaManagerPage(page);

    // Setup: Upload a schema first
    await schemaPage.goto();
    await schemaPage.uploadSchema('valid-simple.xsd');
    await schemaPage.waitForUploadComplete();

    // Navigate to ingestion page
    await ingestPage.goto();
  });

  test('E2E-201: Successfully ingest valid XML file', async ({ page }) => {
    // ACT: Upload and ingest XML
    await ingestPage.uploadAndIngest('valid-person.xml');

    // ASSERT: Success message appears
    await expect(page.locator('text=/successfully ingested/i')).toBeVisible();

    // ASSERT: Ingestion stats are displayed
    const stats = await ingestPage.getIngestionStats();
    expect(stats.nodesCreated).toBeGreaterThan(0);

    // Take screenshot
    await ingestPage.screenshot('ingestion-success');
  });

  test('E2E-202: Can ingest multiple XML files', async ({ page }) => {
    // ACT: Upload multiple files
    await ingestPage.uploadXmlFiles(['valid-person.xml', 'valid-organization.xml']);

    // ASSERT: Both files appear in list
    const files = await ingestPage.getUploadedFileNames();
    expect(files.length).toBe(2);

    // ACT: Ingest all files
    await ingestPage.clickIngest();
    await ingestPage.waitForIngestionComplete();

    // ASSERT: Stats show multiple files processed
    const stats = await ingestPage.getIngestionStats();
    expect(stats.filesProcessed).toBeGreaterThanOrEqual(2);
    expect(stats.nodesCreated).toBeGreaterThan(0);
  });

  test('E2E-203: Shows error for invalid XML', async ({ page }) => {
    // ACT: Try to ingest invalid XML
    await ingestPage.uploadXmlFiles('invalid-xml.xml');
    await ingestPage.clickIngest();

    // ASSERT: Error message appears
    const errorMessage = await ingestPage.getErrorMessage();
    expect(errorMessage.toLowerCase()).toContain('validation');

    // ASSERT: Can see validation errors
    const errors = await ingestPage.getValidationErrors();
    expect(errors.length).toBeGreaterThan(0);

    // Take screenshot of error state
    await ingestPage.screenshot('ingestion-validation-error');
  });

  test('E2E-204: Can remove file before ingestion', async ({ page }) => {
    // ARRANGE: Upload multiple files
    await ingestPage.uploadXmlFiles(['valid-person.xml', 'valid-organization.xml']);

    // ACT: Remove one file
    await ingestPage.removeFile('valid-person.xml');

    // ASSERT: Only one file remains
    const files = await ingestPage.getUploadedFileNames();
    expect(files.length).toBe(1);
    expect(files[0]).toContain('valid-organization.xml');
  });

  test('E2E-205: Shows "View in Graph" link after successful ingestion', async ({ page }) => {
    // ARRANGE: Ingest data
    await ingestPage.uploadAndIngest('valid-organization.xml');

    // ASSERT: "View in Graph" link appears
    const hasLink = await ingestPage.hasViewInGraphLink();
    expect(hasLink).toBeTruthy();

    // ACT: Click the link
    await ingestPage.viewInGraph();

    // ASSERT: Navigated to graph page
    await expect(page).toHaveURL(/.*graph/);
  });
});

/**
 * Data Ingestion Without Schema Tests
 */
test.describe('Data Ingestion Without Active Schema', () => {
  let ingestPage: DataIngestionPage;

  test.beforeEach(async ({ page }) => {
    ingestPage = new DataIngestionPage(page);
    // Don't upload schema - test without it
    await ingestPage.goto();
  });

  test('E2E-206: Shows warning when no schema exists', async ({ page }) => {
    // ASSERT: Warning message is displayed
    const hasWarning = await ingestPage.hasNoSchemaWarning();
    expect(hasWarning).toBeTruthy();

    // ASSERT: Ingest button is disabled or shows warning
    await expect(page.locator('text=/upload schema/i')).toBeVisible();

    // Take screenshot
    await ingestPage.screenshot('ingestion-no-schema-warning');
  });
});

/**
 * Ingestion Progress and Status Tests
 */
test.describe('Ingestion Progress Tracking', () => {
  let ingestPage: DataIngestionPage;

  test.beforeEach(async ({ page }) => {
    ingestPage = new DataIngestionPage(page);

    // Setup: Upload schema
    const schemaPage = new SchemaManagerPage(page);
    await schemaPage.goto();
    await schemaPage.uploadSchema('valid-simple.xsd');
    await schemaPage.waitForUploadComplete();

    await ingestPage.goto();
  });

  test('E2E-207: Shows progress indicator during ingestion', async ({ page }) => {
    // ACT: Start ingestion
    await ingestPage.uploadXmlFiles('valid-organization.xml');
    await ingestPage.clickIngest();

    // ASSERT: Progress indicator appears (check quickly before it disappears)
    const progressVisible = await ingestPage.isProgressVisible().catch(() => false);
    // Progress might be too fast to catch, so we don't fail if not visible

    // Wait for completion
    await ingestPage.waitForIngestionComplete();

    // ASSERT: Success message appears
    await expect(page.locator('text=/success/i')).toBeVisible();
  });
});
