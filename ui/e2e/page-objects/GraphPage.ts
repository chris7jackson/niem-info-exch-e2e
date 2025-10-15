import { Page, Locator } from '@playwright/test'
import { BasePage } from './BasePage'

/**
 * Graph Page Object
 *
 * Encapsulates interactions with the Graph Visualization page:
 * - Loading graph data
 * - Executing Cypher queries
 * - Interacting with graph visualization
 * - Changing layouts
 */
export class GraphPage extends BasePage {
  // Locators
  readonly graphContainer: Locator
  readonly cypherInput: Locator
  readonly showGraphButton: Locator
  readonly graphStats: Locator
  readonly layoutSelect: Locator
  readonly completeGraphButton: Locator
  readonly limitedGraphButton: Locator

  constructor(page: Page) {
    super(page)
    this.graphContainer = page.locator('#graph-viz')
    this.cypherInput = page.locator('textarea[id="cypher-query"]')
    this.showGraphButton = page.locator('button:has-text("Show Graph")')
    this.graphStats = page.locator('[data-testid="graph-stats"]')
    this.layoutSelect = page.locator('select').first()
    this.completeGraphButton = page.locator('button:has-text("Complete Graph")')
    this.limitedGraphButton = page.locator('button:has-text("Limited (100)")')
  }

  /**
   * Navigate to Graph page
   */
  async goto() {
    await this.navigate('/graph')
    await this.page.waitForSelector('h1:has-text("Graph Schema")', { state: 'visible' })
  }

  /**
   * Execute a Cypher query
   */
  async executeQuery(query: string) {
    await this.cypherInput.clear()
    await this.cypherInput.fill(query)
    await this.showGraphButton.click()
    await this.waitForLoadingComplete()
  }

  /**
   * Load complete graph
   */
  async loadCompleteGraph() {
    await this.completeGraphButton.click()
    await this.waitForLoadingComplete()
  }

  /**
   * Load limited graph (100 nodes)
   */
  async loadLimitedGraph() {
    await this.limitedGraphButton.click()
    await this.waitForLoadingComplete()
  }

  /**
   * Get graph statistics (node and relationship counts)
   */
  async getGraphStats(): Promise<{ nodes: number; relationships: number }> {
    // Wait for stats to be visible
    await this.page.waitForSelector('text=/\\d+ nodes/', { timeout: 10000 })

    const statsText = await this.page.textContent('body')
    const nodeMatch = statsText?.match(/(\d+)\s+nodes/i)
    const relMatch = statsText?.match(/(\d+)\s+relationships/i)

    return {
      nodes: nodeMatch ? parseInt(nodeMatch[1]) : 0,
      relationships: relMatch ? parseInt(relMatch[1]) : 0
    }
  }

  /**
   * Click on a node in the graph
   * @param x - X coordinate
   * @param y - Y coordinate
   */
  async clickNode(x: number, y: number) {
    await this.graphContainer.click({ position: { x, y } })
  }

  /**
   * Change graph layout
   */
  async changeLayout(layout: 'cose' | 'circle' | 'grid' | 'breadthfirst' | 'concentric') {
    await this.layoutSelect.selectOption(layout)
    // Wait for layout animation
    await this.page.waitForTimeout(1500)
  }

  /**
   * Toggle node labels
   */
  async toggleNodeLabels() {
    await this.page.locator('button:has-text("Node Labels")').click()
  }

  /**
   * Toggle edge labels
   */
  async toggleEdgeLabels() {
    await this.page.locator('button:has-text("Edge Labels")').click()
  }

  /**
   * Check if graph is visible
   */
  async isGraphVisible(): Promise<boolean> {
    return this.graphContainer.isVisible()
  }

  /**
   * Get error message if query fails
   */
  async getQueryError(): Promise<string | null> {
    const errorElement = this.page.locator('text=/query error/i')
    if (await errorElement.count() > 0) {
      return errorElement.textContent()
    }
    return null
  }

  /**
   * Wait for graph to render
   */
  async waitForGraphRender(timeout = 10000) {
    await this.page.waitForSelector('#graph-viz canvas, #graph-viz svg', {
      state: 'visible',
      timeout
    }).catch(() => {
      // Graph might use different rendering method
    })
    await this.page.waitForTimeout(1000) // Additional wait for Cytoscape initialization
  }

  /**
   * Get node details panel text (when node is selected)
   */
  async getNodeDetailsText(): Promise<string | null> {
    const detailsPanel = this.page.locator('[data-testid="node-details"]')
    if (await detailsPanel.count() > 0) {
      return detailsPanel.textContent()
    }
    return null
  }

  /**
   * Zoom in on graph
   */
  async zoomIn() {
    await this.graphContainer.hover()
    await this.page.mouse.wheel(0, -100)
  }

  /**
   * Zoom out on graph
   */
  async zoomOut() {
    await this.graphContainer.hover()
    await this.page.mouse.wheel(0, 100)
  }

  /**
   * Pan graph view
   */
  async panGraph(fromX: number, fromY: number, toX: number, toY: number) {
    await this.page.mouse.move(fromX, fromY)
    await this.page.mouse.down()
    await this.page.mouse.move(toX, toY)
    await this.page.mouse.up()
  }
}
