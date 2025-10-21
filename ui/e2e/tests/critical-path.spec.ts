import { test, expect } from '@playwright/test';
import { SchemaManagerPage } from '../page-objects/SchemaManagerPage';
import { DataIngestionPage } from '../page-objects/DataIngestionPage';
import { GraphPage } from '../page-objects/GraphPage';

/**
 * Critical Path E2E Test
 *
 * This test covers the complete user journey from schema upload to visualization:
 * 1. Upload XSD schema
 * 2. Verify schema is active
 * 3. Ingest XML data
 * 4. Verify ingestion success
 * 5. Navigate to graph
 * 6. Verify data is visualized
 * 7. Execute custom query
 * 8. Clean up (delete schema)
 *
 * This is the most important E2E test - it validates the entire happy path
 * that users will follow when using the application.
 *
 * Prerequisites:
 * - Clean database state
 * - Backend API running
 * - Frontend dev server running
 */
test.describe('Critical Path: Complete NIEM Workflow', () => {
  test('E2E-301: Complete workflow from schema to visualization', async ({ page }) => {
    // Initialize page objects
    const schemaPage = new SchemaManagerPage(page);
    const ingestPage = new DataIngestionPage(page);
    const graphPage = new GraphPage(page);

    // ========================================
    // STEP 1: Upload Schema
    // ========================================
    await test.step('Upload XSD Schema', async () => {
      await schemaPage.goto();

      // Verify we're on the schema page
      await expect(page.locator('h1')).toContainText('Schema Management');

      // Upload a valid schema
      await schemaPage.uploadSchema('valid-simple.xsd');

      // Wait for upload to complete
      await schemaPage.waitForUploadComplete();

      // Verify success
      await expect(page.locator('text=/success/i')).toBeVisible();

      // Take screenshot
      await schemaPage.screenshot('critical-path-01-schema-uploaded');
    });

    // ========================================
    // STEP 2: Verify Schema is Active
    // ========================================
    await test.step('Verify Schema is Active', async () => {
      // Check that schema appears in list
      const schemaExists = await schemaPage.schemaExists('valid-simple.xsd');
      expect(schemaExists).toBeTruthy();

      // Check that it has "Active" badge
      const isActive = await schemaPage.isSchemaActive('valid-simple.xsd');
      expect(isActive).toBeTruthy();

      // Take screenshot
      await schemaPage.screenshot('critical-path-02-schema-active');
    });

    // ========================================
    // STEP 3: Navigate to Data Ingestion
    // ========================================
    await test.step('Navigate to Data Ingestion', async () => {
      await ingestPage.goto();

      // Verify we're on ingestion page
      await expect(page.locator('h1')).toContainText('Data Ingestion');

      // Verify no "upload schema first" warning
      const hasWarning = await ingestPage.hasNoSchemaWarning();
      expect(hasWarning).toBeFalsy();
    });

    // ========================================
    // STEP 4: Ingest XML Data
    // ========================================
    await test.step('Ingest XML Data', async () => {
      // Upload XML files
      await ingestPage.uploadXmlFiles(['valid-person.xml', 'valid-organization.xml']);

      // Verify files appear in list
      const files = await ingestPage.getUploadedFileNames();
      expect(files.length).toBe(2);

      // Click ingest button
      await ingestPage.clickIngest();

      // Wait for ingestion to complete
      await ingestPage.waitForIngestionComplete(30000);

      // Verify success message
      await expect(page.locator('text=/successfully ingested/i')).toBeVisible();

      // Take screenshot
      await ingestPage.screenshot('critical-path-03-data-ingested');
    });

    // ========================================
    // STEP 5: Verify Ingestion Statistics
    // ========================================
    await test.step('Verify Ingestion Statistics', async () => {
      // Get ingestion stats
      const stats = await ingestPage.getIngestionStats();

      // Verify stats make sense
      expect(stats.filesProcessed).toBeGreaterThanOrEqual(2);
      expect(stats.nodesCreated).toBeGreaterThan(0);

      console.log('Ingestion stats:', stats);

      // Take screenshot
      await ingestPage.screenshot('critical-path-04-ingestion-stats');
    });

    // ========================================
    // STEP 6: Navigate to Graph
    // ========================================
    await test.step('Navigate to Graph Visualization', async () => {
      // Click "View in Graph" link
      const hasLink = await ingestPage.hasViewInGraphLink();
      if (hasLink) {
        await ingestPage.viewInGraph();
      } else {
        // Manual navigation
        await graphPage.goto();
      }

      // Verify we're on graph page
      await expect(page).toHaveURL(/.*graph/);
      await expect(page.locator('h1')).toContainText('Graph');

      // Take screenshot
      await graphPage.screenshot('critical-path-05-navigated-to-graph');
    });

    // ========================================
    // STEP 7: Verify Data Appears in Graph
    // ========================================
    await test.step('Verify Data is Visualized', async () => {
      // Wait for graph to load
      await graphPage.waitForLoadingComplete();
      await graphPage.waitForGraphRender();

      // Get graph statistics
      const stats = await graphPage.getGraphStats();

      // Verify we have data
      expect(stats.nodes).toBeGreaterThan(0);
      console.log('Graph stats:', stats);

      // Verify graph container is visible
      const isVisible = await graphPage.isGraphVisible();
      expect(isVisible).toBeTruthy();

      // Take screenshot
      await graphPage.screenshot('critical-path-06-graph-rendered');
    });

    // ========================================
    // STEP 8: Execute Custom Query
    // ========================================
    await test.step('Execute Custom Cypher Query', async () => {
      // Execute a query to find Person nodes
      await graphPage.executeQuery('MATCH (n:Person) RETURN n LIMIT 10');

      // Wait for results
      await graphPage.waitForGraphRender();

      // Verify query executed successfully
      const error = await graphPage.getQueryError();
      expect(error).toBeNull();

      // Get updated stats
      const stats = await graphPage.getGraphStats();
      expect(stats.nodes).toBeGreaterThan(0);

      // Take screenshot
      await graphPage.screenshot('critical-path-07-custom-query');
    });

    // ========================================
    // STEP 9: Interact with Graph
    // ========================================
    await test.step('Interact with Graph Visualization', async () => {
      // Change layout
      await graphPage.changeLayout('circle');
      await page.waitForTimeout(1000);

      // Verify graph is still visible
      const isVisible = await graphPage.isGraphVisible();
      expect(isVisible).toBeTruthy();

      // Toggle labels
      await graphPage.toggleNodeLabels();
      await page.waitForTimeout(500);

      // Take screenshot
      await graphPage.screenshot('critical-path-08-graph-interactions');
    });

    // ========================================
    // STEP 10: Summary
    // ========================================
    await test.step('Test Summary', async () => {
      console.log('✅ Critical Path Test Completed Successfully');
      console.log('- Schema uploaded and activated');
      console.log('- Data ingested from XML files');
      console.log('- Graph visualization rendered');
      console.log('- Custom queries executed');
      console.log('- User interactions tested');
    });
  });
});

/**
 * Critical Path Error Scenarios
 *
 * Tests for common failure points in the workflow
 */
test.describe('Critical Path Error Scenarios', () => {
  test('E2E-302: Cannot ingest data without schema', async ({ page }) => {
    const ingestPage = new DataIngestionPage(page);

    // Go directly to ingestion without uploading schema
    await ingestPage.goto();

    // Should show warning
    const hasWarning = await ingestPage.hasNoSchemaWarning();
    expect(hasWarning).toBeTruthy();

    // Take screenshot
    await ingestPage.screenshot('critical-path-error-no-schema');
  });

  test('E2E-303: Graph shows empty state with no data', async ({ page }) => {
    const graphPage = new GraphPage(page);

    // Navigate to graph without ingesting data
    await graphPage.goto();

    // Wait for load
    await graphPage.waitForLoadingComplete();

    // Should either show 0 nodes or empty state message
    const stats = await graphPage.getGraphStats();
    expect(stats.nodes).toBe(0);

    // Take screenshot
    await graphPage.screenshot('critical-path-error-empty-graph');
  });
});
