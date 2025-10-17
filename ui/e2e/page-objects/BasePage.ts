import { Page, Locator } from '@playwright/test'

/**
 * Base Page Object
 *
 * Provides common functionality shared across all page objects:
 * - Navigation helpers
 * - Wait utilities
 * - Screenshot capture
 * - Success/Error message detection
 */
export class BasePage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  /**
   * Navigate to a specific path
   */
  async navigate(path: string) {
    await this.page.goto(path)
    await this.page.waitForLoadState('networkidle')
  }

  /**
   * Wait for success toast/message to appear
   */
  async waitForSuccess(timeout = 10000) {
    return this.page.waitForSelector('[data-testid="success-toast"], [data-testid="success-message"]', {
      timeout,
      state: 'visible'
    })
  }

  /**
   * Wait for error message to appear
   */
  async waitForError(timeout = 10000) {
    return this.page.waitForSelector('[data-testid="error-message"], [role="alert"]', {
      timeout,
      state: 'visible'
    })
  }

  /**
   * Take a screenshot with a descriptive name
   */
  async screenshot(name: string) {
    await this.page.screenshot({
      path: `screenshots/${name}-${Date.now()}.png`,
      fullPage: true
    })
  }

  /**
   * Wait for loading spinner to disappear
   */
  async waitForLoadingComplete(timeout = 30000) {
    await this.page.waitForSelector('[data-testid="loading-spinner"]', {
      state: 'hidden',
      timeout
    }).catch(() => {
      // Ignore if no spinner exists
    })
  }

  /**
   * Get the current URL
   */
  getCurrentUrl(): string {
    return this.page.url()
  }

  /**
   * Check if element exists without throwing
   */
  async elementExists(selector: string): Promise<boolean> {
    const element = await this.page.$(selector)
    return element !== null
  }

  /**
   * Wait for navigation to complete
   */
  async waitForNavigation() {
    await this.page.waitForLoadState('networkidle')
  }
}
