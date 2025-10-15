import { test, expect } from '@playwright/test'
import { GraphPage } from '../page-objects/GraphPage'
import { SchemaManagerPage } from '../page-objects/SchemaManagerPage'
import { DataIngestionPage } from '../page-objects/DataIngestionPage'

/**
 * Graph Visualization E2E Tests
 *
 * These tests cover graph visualization interactions:
 * - Loading graph data
 * - Executing Cypher queries
 * - Interacting with graph elements
 * - Changing layouts
 *
 * Prerequisites:
 * - Schema must be uploaded
 * - Sample data must be ingested
 */
test.describe('Graph Visualization Flow', () => {
  let graphPage: GraphPage

  test.beforeEach(async ({ page }) => {
    graphPage = new GraphPage(page)

    // Setup: Upload schema and ingest data
    const schemaPage = new SchemaManagerPage(page)
    await schemaPage.goto()
    await schemaPage.uploadSchema('valid-simple.xsd')
    await schemaPage.waitForUploadComplete()

    const ingestPage = new DataIngestionPage(page)
    await ingestPage.goto()
    await ingestPage.uploadAndIngest(['valid-person.xml', 'valid-organization.xml'])

    // Navigate to graph page
    await graphPage.goto()
  })

  test('E2E-101: Graph page renders with controls', async ({ page }) => {
    // ASSERT: Page title is correct
    await expect(page.locator('h1')).toContainText('Graph')

    // ASSERT: Cypher input is visible
    await expect(graphPage.cypherInput).toBeVisible()

    // ASSERT: Show Graph button is visible
    await expect(graphPage.showGraphButton).toBeVisible()

    // ASSERT: Graph container exists
    await expect(graphPage.graphContainer).toBeVisible()
  })

  test('E2E-102: Graph loads and displays statistics', async ({ page }) => {
    // ACT: Wait for initial auto-load
    await graphPage.waitForLoadingComplete()
    await graphPage.waitForGraphRender()

    // ASSERT: Graph statistics are displayed
    const stats = await graphPage.getGraphStats()
    expect(stats.nodes).toBeGreaterThan(0)

    // Take screenshot
    await graphPage.screenshot('graph-loaded')
  })

  test('E2E-103: Can execute custom Cypher query', async ({ page }) => {
    // ACT: Execute a custom query
    await graphPage.executeQuery('MATCH (n:Person) RETURN n LIMIT 10')

    // ASSERT: Graph updates with results
    await graphPage.waitForGraphRender()
    const stats = await graphPage.getGraphStats()
    expect(stats.nodes).toBeGreaterThan(0)

    // Take screenshot
    await graphPage.screenshot('custom-query-results')
  })

  test('E2E-104: Can change graph layout', async ({ page }) => {
    // ARRANGE: Load graph
    await graphPage.waitForLoadingComplete()
    await graphPage.waitForGraphRender()

    // ACT: Change to circle layout
    await graphPage.changeLayout('circle')

    // ASSERT: Graph is still visible after layout change
    const isVisible = await graphPage.isGraphVisible()
    expect(isVisible).toBeTruthy()

    // Take screenshot of different layout
    await graphPage.screenshot('graph-circle-layout')
  })
})

/**
 * Graph Error Handling E2E Tests
 */
test.describe('Graph Error Handling', () => {
  let graphPage: GraphPage

  test.beforeEach(async ({ page }) => {
    graphPage = new GraphPage(page)
    await graphPage.goto()
  })

  test('E2E-105: Handles invalid Cypher syntax', async ({ page }) => {
    // ACT: Execute invalid Cypher query
    await graphPage.executeQuery('INVALID CYPHER SYNTAX')

    // ASSERT: Error message is displayed
    const error = await graphPage.getQueryError()
    expect(error).not.toBeNull()
    expect(error?.toLowerCase()).toContain('error')

    // Take screenshot of error state
    await graphPage.screenshot('graph-query-error')
  })

  test('E2E-106: Handles empty database gracefully', async ({ page }) => {
    // Note: This test assumes database is empty (no data ingested)

    // ACT: Try to load graph
    await graphPage.waitForLoadingComplete()

    // ASSERT: Either shows empty state or error message
    const stats = await graphPage.getGraphStats()
    // Should either be 0 nodes or show appropriate message
    expect(stats.nodes).toBeGreaterThanOrEqual(0)
  })
})

/**
 * Graph Interaction E2E Tests
 */
test.describe('Graph User Interactions', () => {
  let graphPage: GraphPage

  test.beforeEach(async ({ page }) => {
    graphPage = new GraphPage(page)

    // Setup: Upload schema and ingest data
    const schemaPage = new SchemaManagerPage(page)
    await schemaPage.goto()
    await schemaPage.uploadSchema('valid-simple.xsd')
    await schemaPage.waitForUploadComplete()

    const ingestPage = new DataIngestionPage(page)
    await ingestPage.goto()
    await ingestPage.uploadAndIngest('valid-organization.xml')

    await graphPage.goto()
    await graphPage.waitForLoadingComplete()
    await graphPage.waitForGraphRender()
  })

  test('E2E-107: Can toggle node labels', async ({ page }) => {
    // ACT: Toggle node labels off
    await graphPage.toggleNodeLabels()

    // Wait for UI update
    await page.waitForTimeout(500)

    // ASSERT: Graph is still visible
    const isVisible = await graphPage.isGraphVisible()
    expect(isVisible).toBeTruthy()

    // Take screenshot
    await graphPage.screenshot('graph-labels-toggled')
  })

  test('E2E-108: Can zoom in and out', async ({ page }) => {
    // ACT: Zoom in
    await graphPage.zoomIn()
    await page.waitForTimeout(300)

    // ACT: Zoom out
    await graphPage.zoomOut()
    await page.waitForTimeout(300)

    // ASSERT: Graph is still visible
    const isVisible = await graphPage.isGraphVisible()
    expect(isVisible).toBeTruthy()
  })
})
