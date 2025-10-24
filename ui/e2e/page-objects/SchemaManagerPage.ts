import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';
import path from 'path';

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
  readonly uploadButton: Locator;
  readonly fileInput: Locator;
  readonly schemaList: Locator;
  readonly uploadSchemaButton: Locator;

  constructor(page: Page) {
    super(page);
    this.uploadButton = page.locator('button:has-text("Upload Schema")');
    this.fileInput = page.locator('input[type="file"]');
    this.schemaList = page.locator('[data-testid="schema-list"]');
    this.uploadSchemaButton = page.locator('button:has-text("Upload")');
  }

  /**
   * Navigate to Schema Manager page
   */
  async goto() {
    await this.navigate('/schemas');
    await this.page.waitForSelector('h2:has-text("Schema Management")', { state: 'visible' });
  }

  /**
   * Upload a schema directory
   * @param dirName - Name of directory in e2e/fixtures/schemas/ (e.g., 'valid-simple-dir')
   */
  async uploadSchema(dirName: string) {
    const dirPath = path.join(process.cwd(), 'e2e', 'fixtures', 'schemas', dirName);

    // For directory inputs, pass the directory path directly (Playwright handles it)
    await this.fileInput.setInputFiles(dirPath);

    // Wait for files to appear in the list
    await this.page.waitForTimeout(500);

    // Click upload button if it exists
    const uploadBtn = this.page
      .locator('button')
      .filter({ hasText: /upload \d+ file|upload schema/i });
    if ((await uploadBtn.count()) > 0) {
      await uploadBtn.first().click();
    }
  }

  /**
   * Get schema by ID
   */
  getSchemaCard(schemaId: string): Locator {
    return this.page.locator(`[data-schema-id="${schemaId}"]`);
  }

  /**
   * Activate a schema
   */
  async activateSchema(schemaId: string) {
    const schemaCard = this.getSchemaCard(schemaId);
    await schemaCard.locator('button:has-text("Activate")').click();
  }

  /**
   * Delete a schema
   */
  async deleteSchema(schemaId: string) {
    const schemaCard = this.getSchemaCard(schemaId);
    await schemaCard.locator('button:has-text("Delete")').click();

    // Confirm deletion if modal appears
    const confirmButton = this.page.locator('button:has-text("Confirm")');
    if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmButton.click();
    }
  }

  /**
   * Get the active schema ID
   */
  async getActiveSchemaId(): Promise<string | null> {
    const activeSchema = this.page.locator('[data-testid="active-schema"]');
    if ((await activeSchema.count()) === 0) {
      return null;
    }
    return activeSchema.locator('[data-testid="schema-id"]').textContent();
  }

  /**
   * Check if schema exists in list
   */
  async schemaExists(schemaName: string): Promise<boolean> {
    const schema = this.page.locator(`text="${schemaName}"`);
    return (await schema.count()) > 0;
  }

  /**
   * Get all schema names from the list
   */
  async getAllSchemaNames(): Promise<string[]> {
    const schemaElements = this.page.locator('[data-testid="schema-name"]');
    return schemaElements.allTextContents();
  }

  /**
   * Wait for schema upload to complete
   * Instead of waiting for a toast, wait for the schema to appear in the uploaded list
   */
  async waitForUploadComplete(timeout = 30000) {
    // Wait for the "Uploaded Schemas" section to show at least one schema
    await this.page.waitForSelector('.bg-white.shadow:has-text("Uploaded Schemas") .p-4', {
      timeout,
      state: 'visible',
    });
  }

  /**
   * Get error message text
   */
  async getErrorMessage(): Promise<string> {
    const errorElement = await this.waitForError();
    const text = await errorElement.textContent();
    return text ?? '';
  }

  /**
   * Check if schema has "Active" badge
   */
  async isSchemaActive(schemaName: string): Promise<boolean> {
    const schemaRow = this.page.locator(`text="${schemaName}"`).locator('..');
    const activeBadge = schemaRow.locator('text="Active"');
    return (await activeBadge.count()) > 0;
  }

  /**
   * Download generated file (CMF or JSON)
   */
  async downloadGeneratedFile(schemaId: string, fileType: 'cmf' | 'json') {
    const schemaCard = this.getSchemaCard(schemaId);
    const downloadButton = schemaCard.locator(
      `button:has-text("Download ${fileType.toUpperCase()}")`
    );

    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      downloadButton.click(),
    ]);

    return download;
  }
}
