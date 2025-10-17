import { Page, Locator } from '@playwright/test'
import { BasePage } from './BasePage'
import path from 'path'

/**
 * Schema Manager Page Object
 *
 * Encapsulates interactions with the Schema Manager page:
 * - Schema upload
 * - Schema activation
 * - Schema deletion
 * - Schema list viewing
 */
export class SchemaManagerPage extends BasePage {
  // Locators
  readonly uploadButton: Locator
  readonly fileInput: Locator
  readonly schemaList: Locator
  readonly uploadSchemaButton: Locator

  constructor(page: Page) {
    super(page)
    this.uploadButton = page.locator('button:has-text("Upload Schema")')
    this.fileInput = page.locator('input[type="file"]')
    this.schemaList = page.locator('[data-testid="schema-list"]')
    this.uploadSchemaButton = page.locator('button:has-text("Upload")')
  }

  /**
   * Navigate to Schema Manager page
   */
  async goto() {
    await this.navigate('/schemas')
    await this.page.waitForSelector('h1:has-text("Schema Management")', { state: 'visible' })
  }

  /**
   * Upload a schema file
   * @param fileName - Name of file in e2e/fixtures/schemas/
   */
  async uploadSchema(fileName: string) {
    const filePath = path.join(process.cwd(), 'e2e', 'fixtures', 'schemas', fileName)

    // Set the file on the input element
    await this.fileInput.setInputFiles(filePath)

    // Wait for file to appear in the list (if component shows selected files)
    await this.page.waitForTimeout(500) // Small delay for UI to update

    // Click upload button if it exists
    const uploadBtn = this.page.locator('button').filter({ hasText: /upload \d+ file|upload schema/i })
    if (await uploadBtn.count() > 0) {
      await uploadBtn.first().click()
    }
  }

  /**
   * Get schema by ID
   */
  getSchemaCard(schemaId: string): Locator {
    return this.page.locator(`[data-schema-id="${schemaId}"]`)
  }

  /**
   * Activate a schema
   */
  async activateSchema(schemaId: string) {
    const schemaCard = this.getSchemaCard(schemaId)
    await schemaCard.locator('button:has-text("Activate")').click()
  }

  /**
   * Delete a schema
   */
  async deleteSchema(schemaId: string) {
    const schemaCard = this.getSchemaCard(schemaId)
    await schemaCard.locator('button:has-text("Delete")').click()

    // Confirm deletion if modal appears
    const confirmButton = this.page.locator('button:has-text("Confirm")')
    if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmButton.click()
    }
  }

  /**
   * Get the active schema ID
   */
  async getActiveSchemaId(): Promise<string | null> {
    const activeSchema = this.page.locator('[data-testid="active-schema"]')
    if (await activeSchema.count() === 0) {
      return null
    }
    return activeSchema.locator('[data-testid="schema-id"]').textContent()
  }

  /**
   * Check if schema exists in list
   */
  async schemaExists(schemaName: string): Promise<boolean> {
    const schema = this.page.locator(`text="${schemaName}"`)
    return (await schema.count()) > 0
  }

  /**
   * Get all schema names from the list
   */
  async getAllSchemaNames(): Promise<string[]> {
    const schemaElements = this.page.locator('[data-testid="schema-name"]')
    return schemaElements.allTextContents()
  }

  /**
   * Wait for schema upload to complete
   */
  async waitForUploadComplete(timeout = 30000) {
    await this.waitForSuccess(timeout)
  }

  /**
   * Get error message text
   */
  async getErrorMessage(): Promise<string> {
    const errorElement = await this.waitForError()
    return errorElement.textContent() || ''
  }

  /**
   * Check if schema has "Active" badge
   */
  async isSchemaActive(schemaName: string): Promise<boolean> {
    const schemaRow = this.page.locator(`text="${schemaName}"`).locator('..')
    const activeBadge = schemaRow.locator('text="Active"')
    return (await activeBadge.count()) > 0
  }

  /**
   * Download generated file (CMF or JSON)
   */
  async downloadGeneratedFile(schemaId: string, fileType: 'cmf' | 'json') {
    const schemaCard = this.getSchemaCard(schemaId)
    const downloadButton = schemaCard.locator(`button:has-text("Download ${fileType.toUpperCase()}")`)

    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      downloadButton.click()
    ])

    return download
  }
}
