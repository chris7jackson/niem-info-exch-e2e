import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';
import path from 'path';

/**
 * XML to JSON Converter Page Object
 *
 * Encapsulates interactions with the XML to JSON Converter page:
 * - Selecting schemas
 * - Uploading XML files for conversion
 * - Converting files
 * - Viewing conversion results
 * - Managing file lists
 */
export class XmlToJsonConverterPage extends BasePage {
  // Locators
  readonly schemaSelect: Locator;
  readonly includeContextCheckbox: Locator;
  readonly fileInput: Locator;
  readonly convertButton: Locator;
  readonly removeAllButton: Locator;

  constructor(page: Page) {
    super(page);
    this.schemaSelect = page.locator('select');
    this.includeContextCheckbox = page.locator('input[type="checkbox"]#includeContext');
    this.fileInput = page.locator('input[type="file"]');
    this.convertButton = page.locator('button:has-text("Convert")');
    this.removeAllButton = page.locator('button:has-text("Remove All")');
  }

  /**
   * Navigate to XML to JSON Converter page (on Helper Tools tab)
   */
  async goto() {
    await this.navigate('/tools');
    await this.page.waitForSelector('h1:has-text("Helper Tools")', { state: 'visible' });
    // Converter is in the first tab and auto-selected, so no need to click
    await this.page.waitForSelector('h2:has-text("XML to JSON Converter")', { state: 'visible' });
  }

  /**
   * Select a schema from the dropdown
   */
  async selectSchema(schemaName: string) {
    await this.schemaSelect.selectOption({ label: schemaName });
  }

  /**
   * Upload XML file(s) for conversion
   * @param fileNames - Array of file names from e2e/fixtures/data/
   */
  async uploadXmlFiles(fileNames: string | string[]) {
    const names = Array.isArray(fileNames) ? fileNames : [fileNames];
    const filePaths = names.map((name) =>
      path.join(process.cwd(), 'e2e', 'fixtures', 'data', name)
    );

    await this.fileInput.setInputFiles(filePaths);

    // Wait for files to appear in list
    await this.page.waitForTimeout(500);
  }

  /**
   * Toggle the "Include complete @context" checkbox
   */
  async toggleIncludeContext(checked: boolean) {
    const isChecked = await this.includeContextCheckbox.isChecked();
    if (isChecked !== checked) {
      await this.includeContextCheckbox.click();
    }
  }

  /**
   * Click the Convert button
   */
  async clickConvert() {
    await this.convertButton.click();
  }

  /**
   * Wait for conversion to complete
   */
  async waitForConversionComplete(timeout = 30000) {
    // Wait for results to appear
    await this.page.waitForSelector('text=/Conversion Results/i', {
      timeout,
      state: 'visible',
    });
  }

  /**
   * Upload and convert in one action
   */
  async uploadAndConvert(fileNames: string | string[]) {
    await this.uploadXmlFiles(fileNames);
    await this.clickConvert();
    await this.waitForConversionComplete();
  }

  /**
   * Get list of selected files before conversion
   */
  async getSelectedFileNames(): Promise<string[]> {
    const fileRows = this.page.locator('[class*="bg-gray-50"]').filter({ hasText: '.xml' });
    const count = await fileRows.count();
    const names: string[] = [];

    for (let i = 0; i < count; i++) {
      const text = await fileRows.nth(i).textContent();
      if (text) {
        // Extract filename from the text
        const match = text.match(/([^\s]+\.xml)/i);
        if (match) {
          names.push(match[1]);
        }
      }
    }

    return names;
  }

  /**
   * Remove a specific file from the upload list
   */
  async removeFile(fileName: string) {
    const fileRow = this.page.locator(`text="${fileName}"`).locator('..');
    await fileRow.locator('button:has-text("Remove")').first().click();
  }

  /**
   * Click the "Remove All" button
   */
  async clickRemoveAll() {
    await this.removeAllButton.click();
  }

  /**
   * Get conversion results statistics
   */
  async getConversionStats(): Promise<{
    filesProcessed: number;
    successful: number;
    failed: number;
  }> {
    const resultsSection = this.page.locator('text=/Conversion Results/i').locator('..');

    const filesProcessedText = await resultsSection
      .locator('text=/Files Processed/i')
      .locator('..')
      .locator('div')
      .first()
      .textContent();
    const successfulText = await resultsSection
      .locator('text=/Successful/i')
      .locator('..')
      .locator('div')
      .first()
      .textContent();
    const failedText = await resultsSection
      .locator('text=/Failed/i')
      .locator('..')
      .locator('div')
      .first()
      .textContent();

    return {
      filesProcessed: parseInt(filesProcessedText?.trim() || '0'),
      successful: parseInt(successfulText?.trim() || '0'),
      failed: parseInt(failedText?.trim() || '0'),
    };
  }

  /**
   * Check if conversion results show any errors
   */
  async hasConversionErrors(): Promise<boolean> {
    const errorElements = this.page.locator('text=/failed/i, text=/error/i');
    return (await errorElements.count()) > 0;
  }

  /**
   * Check if download buttons are visible
   */
  async hasDownloadButtons(): Promise<boolean> {
    const downloadButtons = this.page.locator('button:has-text("Download")');
    return (await downloadButtons.count()) > 0;
  }

  /**
   * Check if "Download All as ZIP" button is visible
   */
  async hasDownloadAllButton(): Promise<boolean> {
    const downloadAllButton = this.page.locator('button:has-text("Download All as ZIP")');
    return await downloadAllButton.isVisible().catch(() => false);
  }

  /**
   * Check if convert button is disabled
   */
  async isConvertButtonDisabled(): Promise<boolean> {
    return await this.convertButton.isDisabled();
  }

  /**
   * Get error message if displayed
   */
  async getErrorMessage(): Promise<string> {
    const errorDiv = this.page.locator('[class*="bg-red-50"]').first();
    return (await errorDiv.textContent()) || '';
  }

  /**
   * Check if file list is empty
   */
  async isFileListEmpty(): Promise<boolean> {
    const selectedFilesHeader = this.page.locator('text=/Selected Files/i');
    return !(await selectedFilesHeader.isVisible().catch(() => false));
  }
}
