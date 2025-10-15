import { Page, Locator } from '@playwright/test'
import { BasePage } from './BasePage'
import path from 'path'

/**
 * Data Ingestion Page Object
 *
 * Encapsulates interactions with the Data Ingestion page:
 * - Uploading XML/JSON files
 * - Viewing ingestion results
 * - Checking ingestion history
 */
export class DataIngestionPage extends BasePage {
  // Locators
  readonly fileInput: Locator
  readonly ingestButton: Locator
  readonly fileList: Locator
  readonly ingestionStats: Locator
  readonly progressBar: Locator
  readonly historyTab: Locator

  constructor(page: Page) {
    super(page)
    this.fileInput = page.locator('input[type="file"][data-testid="xml-upload"]')
    this.ingestButton = page.locator('button:has-text("Ingest Data")')
    this.fileList = page.locator('[data-testid="file-list"]')
    this.ingestionStats = page.locator('[data-testid="ingestion-stats"]')
    this.progressBar = page.locator('[data-testid="progress"]')
    this.historyTab = page.locator('button:has-text("Ingestion History")')
  }

  /**
   * Navigate to Data Ingestion page
   */
  async goto() {
    await this.navigate('/ingest')
    await this.page.waitForSelector('h1:has-text("Data Ingestion")', { state: 'visible' })
  }

  /**
   * Upload XML file(s) for ingestion
   * @param fileNames - Array of file names from e2e/fixtures/data/
   */
  async uploadXmlFiles(fileNames: string | string[]) {
    const names = Array.isArray(fileNames) ? fileNames : [fileNames]
    const filePaths = names.map(name =>
      path.join(process.cwd(), 'e2e', 'fixtures', 'data', name)
    )

    await this.fileInput.setInputFiles(filePaths)

    // Wait for files to appear in list
    await this.page.waitForTimeout(500)
  }

  /**
   * Click the Ingest Data button
   */
  async clickIngest() {
    await this.ingestButton.click()
  }

  /**
   * Upload and ingest in one action
   */
  async uploadAndIngest(fileNames: string | string[]) {
    await this.uploadXmlFiles(fileNames)
    await this.clickIngest()
    await this.waitForIngestionComplete()
  }

  /**
   * Wait for ingestion to complete
   */
  async waitForIngestionComplete(timeout = 30000) {
    // Wait for success message
    await this.waitForSuccess(timeout)
  }

  /**
   * Get ingestion statistics
   */
  async getIngestionStats(): Promise<{
    filesProcessed: number
    nodesCreated: number
    relationshipsCreated: number
  }> {
    const statsText = await this.ingestionStats.textContent()

    const filesMatch = statsText?.match(/(\d+)\s+files?/i)
    const nodesMatch = statsText?.match(/(\d+)\s+nodes?\s+created/i)
    const relsMatch = statsText?.match(/(\d+)\s+relationships?\s+created/i)

    return {
      filesProcessed: filesMatch ? parseInt(filesMatch[1]) : 0,
      nodesCreated: nodesMatch ? parseInt(nodesMatch[1]) : 0,
      relationshipsCreated: relsMatch ? parseInt(relsMatch[1]) : 0
    }
  }

  /**
   * Check if progress bar is visible
   */
  async isProgressVisible(): Promise<boolean> {
    return this.progressBar.isVisible()
  }

  /**
   * Get list of uploaded files
   */
  async getUploadedFileNames(): Promise<string[]> {
    const fileElements = this.fileList.locator('[data-testid="file-name"]')
    return fileElements.allTextContents()
  }

  /**
   * Remove a file from upload list before ingestion
   */
  async removeFile(fileName: string) {
    const fileRow = this.page.locator(`text="${fileName}"`).locator('..')
    await fileRow.locator('button:has-text("Remove")').click()
  }

  /**
   * Navigate to ingestion history
   */
  async viewHistory() {
    await this.historyTab.click()
    await this.page.waitForSelector('table, [data-testid="history-table"]', { state: 'visible' })
  }

  /**
   * Get ingestion history entries
   */
  async getHistoryEntries(): Promise<Array<{
    date: string
    fileCount: number
    status: string
  }>> {
    await this.viewHistory()

    const rows = this.page.locator('tbody tr')
    const count = await rows.count()
    const entries = []

    for (let i = 0; i < count; i++) {
      const row = rows.nth(i)
      const cells = row.locator('td')

      entries.push({
        date: await cells.nth(0).textContent() || '',
        fileCount: parseInt(await cells.nth(1).textContent() || '0'),
        status: await cells.nth(2).textContent() || ''
      })
    }

    return entries
  }

  /**
   * Check if "View in Graph" link is present
   */
  async hasViewInGraphLink(): Promise<boolean> {
    const link = this.page.locator('a:has-text("View in Graph")')
    return (await link.count()) > 0
  }

  /**
   * Click "View in Graph" link
   */
  async viewInGraph() {
    await this.page.locator('a:has-text("View in Graph")').click()
    await this.waitForNavigation()
  }

  /**
   * Get validation errors if ingestion fails
   */
  async getValidationErrors(): Promise<string[]> {
    const errorsList = this.page.locator('[data-testid="validation-errors"] li')
    return errorsList.allTextContents()
  }

  /**
   * Check if active schema warning is displayed
   */
  async hasNoSchemaWarning(): Promise<boolean> {
    const warning = this.page.locator('text=/upload schema first/i')
    return (await warning.count()) > 0
  }
}
