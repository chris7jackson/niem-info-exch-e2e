import { chromium, FullConfig } from '@playwright/test'
import path from 'path'
import fs from 'fs'

/**
 * Global setup for E2E tests
 * Uploads a test schema via API before all tests run
 */
async function globalSetup(config: FullConfig) {
  const apiURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  console.log('🔧 Global Setup: Uploading test schema via API...')

  try {
    // Read the schema file
    const schemaPath = path.join(__dirname, 'fixtures', 'schemas', 'valid-simple-dir', 'valid-simple.xsd')
    const schemaContent = fs.readFileSync(schemaPath, 'utf-8')

    // Create form data
    const FormData = require('form-data')
    const form = new FormData()
    form.append('files', Buffer.from(schemaContent), {
      filename: 'valid-simple.xsd',
      contentType: 'application/xml'
    })

    // Upload schema via API
    const axios = require('axios')
    const response = await axios.post(`${apiURL}/api/schema/xsd`, form, {
      headers: {
        ...form.getHeaders(),
        'Authorization': 'Bearer devtoken'
      }
    })

    if (response.status === 200) {
      console.log('✅ Test schema uploaded successfully')
    } else {
      console.warn('⚠️  Schema upload returned status:', response.status)
    }
  } catch (error: any) {
    console.error('❌ Failed to upload test schema:', error.message)
    // Don't fail setup - tests should handle missing schema gracefully
  }
}

export default globalSetup
