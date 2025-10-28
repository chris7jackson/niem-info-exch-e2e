import { test, expect } from '@playwright/test';
import { XmlToJsonConverterPage } from '../page-objects/XmlToJsonConverterPage';

/**
 * XML to JSON Converter E2E Tests
 *
 * These tests cover the XML to JSON conversion workflow:
 * - Converting XML files to JSON
 * - File upload and removal
 * - Schema selection
 * - Viewing conversion results
 * - Error handling
 *
 * Prerequisites:
 * - Backend API running
 * - Active schema must exist
 *
 * Note: These tests do NOT test actual file downloads (flaky and low value).
 * They verify that download buttons appear but don't click them.
 */
test.describe('XML to JSON Converter', () => {
  let converterPage: XmlToJsonConverterPage;

  test.beforeEach(async ({ page }) => {
    converterPage = new XmlToJsonConverterPage(page);

    // Note: Schema is uploaded via API in global-setup.ts before all tests
    // Navigate to converter page
    await converterPage.goto();
  });

  test('E2E-301: Successfully convert XML files to JSON', async ({ page }) => {
    // ARRANGE: Upload XML files
    await converterPage.uploadXmlFiles(['valid-person.xml', 'valid-organization.xml']);

    // Verify files appear in list
    const files = await converterPage.getSelectedFileNames();
    expect(files.length).toBe(2);

    // ACT: Convert files
    await converterPage.clickConvert();
    await converterPage.waitForConversionComplete();

    // ASSERT: Conversion results show success
    const stats = await converterPage.getConversionStats();
    expect(stats.filesProcessed).toBe(2);
    expect(stats.successful).toBe(2);
    expect(stats.failed).toBe(0);

    // ASSERT: Download buttons appear (not testing actual download)
    const hasDownloadButtons = await converterPage.hasDownloadButtons();
    expect(hasDownloadButtons).toBeTruthy();

    // ASSERT: Download All as ZIP button appears when multiple files succeed
    const hasDownloadAll = await converterPage.hasDownloadAllButton();
    expect(hasDownloadAll).toBeTruthy();

    // Take screenshot
    await converterPage.screenshot('converter-success');
  });

  test('E2E-302: Remove individual file before conversion', async ({ page }) => {
    // ARRANGE: Upload multiple files
    await converterPage.uploadXmlFiles(['valid-person.xml', 'valid-organization.xml']);

    // Verify both files are listed
    let files = await converterPage.getSelectedFileNames();
    expect(files.length).toBe(2);

    // ACT: Remove one file
    await converterPage.removeFile('valid-person.xml');

    // ASSERT: Only one file remains
    files = await converterPage.getSelectedFileNames();
    expect(files.length).toBe(1);
    expect(files[0]).toContain('valid-organization.xml');

    // ACT: Convert remaining file
    await converterPage.clickConvert();
    await converterPage.waitForConversionComplete();

    // ASSERT: Only 1 file was processed
    const stats = await converterPage.getConversionStats();
    expect(stats.filesProcessed).toBe(1);
  });

  test('E2E-303: Remove all files using Remove All button', async ({ page }) => {
    // ARRANGE: Upload multiple files
    await converterPage.uploadXmlFiles(['valid-person.xml', 'valid-organization.xml']);

    // Verify files are listed
    let files = await converterPage.getSelectedFileNames();
    expect(files.length).toBe(2);

    // ACT: Click Remove All button
    await converterPage.clickRemoveAll();

    // ASSERT: File list is empty
    const isEmpty = await converterPage.isFileListEmpty();
    expect(isEmpty).toBeTruthy();

    // ASSERT: Convert button should be disabled
    const isDisabled = await converterPage.isConvertButtonDisabled();
    expect(isDisabled).toBeTruthy();
  });

  test('E2E-304: Handle conversion failure gracefully', async ({ page }) => {
    // ARRANGE: Upload invalid XML file
    await converterPage.uploadXmlFiles('invalid-xml.xml');

    // ACT: Attempt conversion
    await converterPage.clickConvert();
    await converterPage.waitForConversionComplete();

    // ASSERT: Results show failure
    const stats = await converterPage.getConversionStats();
    expect(stats.filesProcessed).toBeGreaterThan(0);
    expect(stats.failed).toBeGreaterThan(0);

    // ASSERT: Error information is displayed
    const hasErrors = await converterPage.hasConversionErrors();
    expect(hasErrors).toBeTruthy();

    // Take screenshot of error state
    await converterPage.screenshot('converter-error');
  });

  test('E2E-305: Convert button disabled when no files selected', async ({ page }) => {
    // ASSERT: Convert button should be disabled initially (no files)
    const isDisabled = await converterPage.isConvertButtonDisabled();
    expect(isDisabled).toBeTruthy();

    // ARRANGE: Upload a file
    await converterPage.uploadXmlFiles('valid-person.xml');

    // ASSERT: Convert button should now be enabled
    const isEnabledAfterUpload = await converterPage.isConvertButtonDisabled();
    expect(isEnabledAfterUpload).toBeFalsy();
  });
});

/**
 * Converter Without Schema Tests
 */
test.describe('XML to JSON Converter Without Active Schema', () => {
  let converterPage: XmlToJsonConverterPage;

  test.beforeEach(async ({ page }) => {
    converterPage = new XmlToJsonConverterPage(page);
    // Don't upload schema - test without it
    await converterPage.goto();
  });

  test('E2E-307: Shows error when no schema exists', async ({ page }) => {
    // ASSERT: Error or warning message is displayed
    const errorMessage = await converterPage.getErrorMessage();
    expect(errorMessage.toLowerCase()).toMatch(/no schema|schema.*first|upload.*schema/i);

    // ASSERT: Convert button may be disabled or show warning
    // (implementation-dependent, just document the behavior)
    await converterPage.screenshot('converter-no-schema');
  });
});
