import { vi } from 'vitest'
import { rest } from 'msw'
import { setupServer } from 'msw/node'
import apiClient from './api'

const API_URL = 'http://localhost:8000'

const server = setupServer(
  // Schema endpoints
  rest.post(`${API_URL}/api/schema/xsd`, (_req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        schema_id: 'test_schema_123',
        niem_ndr_report: { status: 'pass' },
        is_active: true
      })
    )
  }),
  rest.get(`${API_URL}/api/schema`, (_req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json([
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
    )
  }),
  rest.post(`${API_URL}/api/schema/activate/:schemaId`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ active_schema_id: req.params.schemaId })
    )
  }),

  // Ingestion endpoints
  rest.post(`${API_URL}/api/ingest/xml`, (_req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        processed_files: 2,
        nodes_created: 10,
        relationships_created: 5
      })
    )
  }),
  rest.post(`${API_URL}/api/ingest/json`, (_req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        processed_files: 1,
        nodes_created: 5,
        relationships_created: 3
      })
    )
  }),
  rest.get(`${API_URL}/api/ingest/files`, (_req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
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
    )
  }),

  // Admin endpoints
  rest.post(`${API_URL}/api/admin/reset`, (_req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        message: 'System reset completed',
        counts: {
          schemas_deleted: 5,
          data_files_deleted: 10,
          neo4j_nodes_deleted: 100
        }
      })
    )
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('API Functions', () => {
  // localStorage is already mocked in setup.ts, just configure return value
  beforeEach(() => {
    vi.mocked(window.localStorage.getItem).mockReturnValue('mock_token')
  })

  describe('Schema Management', () => {
    test('uploadSchema sends file correctly', async () => {
      const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })

      const result = await apiClient.uploadSchema([file], ['test.xsd'], false)

      expect(result.schema_id).toBe('test_schema_123')
      expect(result.is_active).toBe(true)
    })

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

    test('uploadSchema handles errors', async () => {
      server.use(
        rest.post(`${API_URL}/api/schema/xsd`, (_req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({ detail: 'Invalid schema format' })
          )
        })
      )

      const file = new File(['invalid'], 'invalid.xsd', { type: 'application/xml' })

      await expect(apiClient.uploadSchema([file], ['invalid.xsd'], false)).rejects.toThrow()
    })
  })

  describe('Data Ingestion', () => {
    test('ingestXml handles multiple files', async () => {
      const files = [
        new File(['<xml1>test</xml1>'], 'test1.xml', { type: 'application/xml' }),
        new File(['<xml2>test</xml2>'], 'test2.xml', { type: 'application/xml' })
      ]

      const result = await apiClient.ingestXml(files)

      expect(result.processed_files).toBe(2)
      expect(result.total_nodes_created).toBe(10)
    })

    test('ingestJson processes files', async () => {
      const files = [
        new File(['{"test": "data"}'], 'test.json', { type: 'application/json' })
      ]

      const result = await apiClient.ingestJson(files)

      expect(result.processed_files).toBe(1)
    })

    test('getUploadedFiles returns file metadata', async () => {
      const files = await apiClient.getUploadedFiles()

      expect(files).toHaveLength(1)
      expect(files[0].original_name).toBe('crash_data.xml')
    })

    test('ingestion handles authentication errors', async () => {
      server.use(
        rest.post(`${API_URL}/api/ingest/xml`, (_req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid authentication token' })
          )
        })
      )

      const files = [new File(['<xml>test</xml>'], 'test.xml', { type: 'application/xml' })]

      await expect(apiClient.ingestXml(files)).rejects.toThrow()
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
        rest.get('/api/admin/neo4j/stats', (_req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              stats: {
                nodes: 100,
                relationships: 50,
                indexes: 5,
                constraints: 3
              }
            })
          )
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
        rest.get(`${API_URL}/api/schema`, (req, res, ctx) => {
          authHeader = req.headers.get('Authorization')
          return res(ctx.status(200), ctx.json([]))
        })
      )

      await apiClient.getSchemas()

      expect(authHeader).toBe('Bearer devtoken')
    })

    test('handles authentication errors', async () => {
      server.use(
        rest.get(`${API_URL}/api/schema`, (_req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid authentication token' })
          )
        })
      )

      await expect(apiClient.getSchemas()).rejects.toThrow()
    })
  })

  describe('Error Handling', () => {
    test('handles 500 server errors', async () => {
      server.use(
        rest.get(`${API_URL}/api/schema`, (_req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({ detail: 'Internal server error' })
          )
        })
      )

      await expect(apiClient.getSchemas()).rejects.toThrow()
    })
  })
})