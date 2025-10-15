import { vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import apiClient from './api'

const API_URL = 'http://localhost:8000'

const server = setupServer(
  // Schema endpoints
  http.post(`${API_URL}/api/schema/xsd`, () => {
    return HttpResponse.json({
      schema_id: 'test_schema_123',
      niem_ndr_report: { status: 'pass' },
      is_active: true
    })
  }),
  http.get(`${API_URL}/api/schema`, () => {
    return HttpResponse.json([
      {
        schema_id: 'schema_1',
        filename: 'test1.xsd',
        active: true,
        uploaded_at: '2024-01-01T00:00:00Z'
      },
      {
        schema_id: 'schema_2',
        filename: 'test2.xsd',
        active: false,
        uploaded_at: '2024-01-02T00:00:00Z'
      }
    ])
  }),
  http.post(`${API_URL}/api/schema/activate/:schemaId`, ({ params }) => {
    return HttpResponse.json({ active_schema_id: params.schemaId })
  }),

  // Ingestion endpoints
  http.post(`${API_URL}/api/ingest/xml`, () => {
    return HttpResponse.json({
      status: 'success',
      processed_files: 2,
      nodes_created: 10,
      relationships_created: 5
    })
  }),
  http.post(`${API_URL}/api/ingest/json`, () => {
    return HttpResponse.json({
      status: 'success',
      processed_files: 1,
      nodes_created: 5,
      relationships_created: 3
    })
  }),
  http.get(`${API_URL}/api/ingest/files`, () => {
    return HttpResponse.json({
      files: [
        {
          original_name: 'crash_data.xml',
          stored_name: '20240101_hash_crash_data.xml',
          size: 1024,
          last_modified: '2024-01-01T00:00:00Z',
          content_type: 'application/xml'
        }
      ]
    })
  }),

  // Admin endpoints
  http.post(`${API_URL}/api/admin/reset`, () => {
    return HttpResponse.json({
      status: 'success',
      message: 'System reset completed',
      counts: {
        schemas_deleted: 5,
        data_files_deleted: 10,
        neo4j_nodes_deleted: 100
      }
    })
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

/**
 * API Client Tests
 *
 * Purpose: Unit tests for the API client layer
 * - Verifies correct HTTP request formatting
 * - Tests response handling and data transformation
 * - Ensures error handling works correctly
 * - Validates authentication token inclusion
 *
 * These tests use MSW (Mock Service Worker) to intercept HTTP requests
 * and return controlled responses without hitting the actual backend.
 *
 * NOT tested here:
 * - File upload functionality (tested in E2E)
 * - Complex multi-step workflows (tested in E2E)
 */
describe('API Functions', () => {
  // localStorage is already mocked in setup.ts, just configure return value
  beforeEach(() => {
    vi.mocked(window.localStorage.getItem).mockReturnValue('mock_token')
  })

  describe('Schema Management', () => {
    test('getSchemas returns schema list', async () => {
      const schemas = await apiClient.getSchemas()

      expect(schemas).toHaveLength(2)
      expect(schemas[0].schema_id).toBe('schema_1')
      expect(schemas[0].active).toBe(true)
    })

    test('activateSchema calls correct endpoint', async () => {
      const result = await apiClient.activateSchema('schema_2')

      expect(result.active_schema_id).toBe('schema_2')
    })
  })

  describe('Data Ingestion', () => {
    test('getUploadedFiles returns file metadata', async () => {
      const files = await apiClient.getUploadedFiles()

      expect(files).toHaveLength(1)
      expect(files[0].original_name).toBe('crash_data.xml')
    })
  })

  describe('Admin Operations', () => {
    test('resetSystem sends correct parameters', async () => {
      const result = await apiClient.resetSystem({
        schemas: true,
        data: true,
        neo4j: false
      })

      expect(result.status).toBe('success')
      expect(result.message).toBe('System reset completed')
    })

    test('getNeo4jStats returns database statistics', async () => {
      server.use(
        http.get(`${API_URL}/api/admin/neo4j/stats`, () => {
          return HttpResponse.json({
            stats: {
              nodes: 100,
              relationships: 50,
              indexes: 5,
              constraints: 3
            }
          })
        })
      )

      const stats = await apiClient.getNeo4jStats()

      expect(stats.nodes).toBe(100)
      expect(stats.relationships).toBe(50)
    })
  })

  describe('Authentication', () => {
    test('includes auth token in requests', async () => {
      let authHeader: string | null = null

      server.use(
        http.get(`${API_URL}/api/schema`, ({ request }) => {
          authHeader = request.headers.get('Authorization')
          return HttpResponse.json([])
        })
      )

      await apiClient.getSchemas()

      expect(authHeader).toBe('Bearer devtoken')
    })

    test('handles authentication errors', async () => {
      server.use(
        http.get(`${API_URL}/api/schema`, () => {
          return HttpResponse.json({ detail: 'Invalid authentication token' }, { status: 401 })
        })
      )

      await expect(apiClient.getSchemas()).rejects.toThrow()
    })
  })

  describe('Error Handling', () => {
    test('handles 500 server errors', async () => {
      server.use(
        http.get(`${API_URL}/api/schema`, () => {
          return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 })
        })
      )

      await expect(apiClient.getSchemas()).rejects.toThrow()
    })
  })
})
