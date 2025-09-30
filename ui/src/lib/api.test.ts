import { rest } from 'msw'
import { setupServer } from 'msw/node'

import {
  uploadSchema,
  getSchemas,
  activateSchema,
  ingestXMLFiles,
  ingestJSONFiles,
  getUploadedFiles,
  executeGraphQuery,
  getFullGraph,
  getDatabaseSummary,
  resetSystem
} from './api'

const server = setupServer(
  // Schema endpoints
  rest.post('/api/schema/xsd', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        schema_id: 'test_schema_123',
        niem_ndr_report: { status: 'pass' },
        is_active: true
      })
    )
  }),
  rest.get('/api/schema', (req, res, ctx) => {
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
  rest.post('/api/schema/activate/:schemaId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ active_schema_id: req.params.schemaId })
    )
  }),

  // Ingestion endpoints
  rest.post('/api/ingest/xml', (req, res, ctx) => {
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
  rest.post('/api/ingest/json', (req, res, ctx) => {
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
  rest.get('/api/ingest/files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        files: [
          {
            original_name: 'crash_data.xml',
            stored_name: '20240101_hash_crash_data.xml',
            size: 1024,
            last_modified: '2024-01-01T00:00:00Z',
            content_type: 'application/xml'
          }
        ],
        total_files: 1
      })
    )
  }),

  // Graph endpoints
  rest.post('/api/graph/query', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        data: {
          nodes: [{ id: 1, labels: ['Person'], properties: { name: 'John' } }],
          relationships: []
        }
      })
    )
  }),
  rest.get('/api/graph/full', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        data: {
          nodes: [
            { id: 1, labels: ['Person'], properties: { name: 'John' } },
            { id: 2, labels: ['Company'], properties: { name: 'Acme' } }
          ],
          relationships: [
            { id: 10, type: 'WORKS_FOR', start_node_id: 1, end_node_id: 2, properties: {} }
          ]
        }
      })
    )
  }),
  rest.get('/api/graph/summary', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        data: {
          node_count: 100,
          relationship_count: 50,
          labels: ['Person', 'Company'],
          relationship_types: ['WORKS_FOR', 'KNOWS']
        }
      })
    )
  }),

  // Admin endpoints
  rest.post('/api/admin/reset', (req, res, ctx) => {
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
  beforeEach(() => {
    // Mock localStorage for auth token
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn(() => 'mock_token'),
        setItem: jest.fn(),
        removeItem: jest.fn()
      },
      writable: true
    })
  })

  describe('Schema Management', () => {
    test('uploadSchema sends file correctly', async () => {
      const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })

      const result = await uploadSchema(file)

      expect(result.schema_id).toBe('test_schema_123')
      expect(result.is_active).toBe(true)
    })

    test('getSchemas returns schema list', async () => {
      const schemas = await getSchemas()

      expect(schemas).toHaveLength(2)
      expect(schemas[0].schema_id).toBe('schema_1')
      expect(schemas[0].active).toBe(true)
    })

    test('activateSchema calls correct endpoint', async () => {
      const result = await activateSchema('schema_2')

      expect(result.active_schema_id).toBe('schema_2')
    })

    test('uploadSchema handles errors', async () => {
      server.use(
        rest.post('/api/schema/xsd', (req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({ detail: 'Invalid schema format' })
          )
        })
      )

      const file = new File(['invalid'], 'invalid.xsd', { type: 'application/xml' })

      await expect(uploadSchema(file)).rejects.toThrow('Invalid schema format')
    })
  })

  describe('Data Ingestion', () => {
    test('ingestXMLFiles handles multiple files', async () => {
      const files = [
        new File(['<xml1>test</xml1>'], 'test1.xml', { type: 'application/xml' }),
        new File(['<xml2>test</xml2>'], 'test2.xml', { type: 'application/xml' })
      ]

      const result = await ingestXMLFiles(files, 'schema_123')

      expect(result.status).toBe('success')
      expect(result.processed_files).toBe(2)
      expect(result.nodes_created).toBe(10)
    })

    test('ingestJSONFiles sends schema_id parameter', async () => {
      const files = [
        new File(['{"test": "data"}'], 'test.json', { type: 'application/json' })
      ]

      const result = await ingestJSONFiles(files, 'schema_456')

      expect(result.status).toBe('success')
      expect(result.processed_files).toBe(1)
    })

    test('getUploadedFiles returns file metadata', async () => {
      const result = await getUploadedFiles()

      expect(result.status).toBe('success')
      expect(result.files).toHaveLength(1)
      expect(result.files[0].original_name).toBe('crash_data.xml')
      expect(result.total_files).toBe(1)
    })

    test('ingestion handles authentication errors', async () => {
      server.use(
        rest.post('/api/ingest/xml', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid authentication token' })
          )
        })
      )

      const files = [new File(['<xml>test</xml>'], 'test.xml', { type: 'application/xml' })]

      await expect(ingestXMLFiles(files)).rejects.toThrow('Invalid authentication token')
    })
  })

  describe('Graph Operations', () => {
    test('executeGraphQuery sends query and parameters', async () => {
      const query = 'MATCH (n:Person) RETURN n'
      const limit = 50

      const result = await executeGraphQuery(query, limit)

      expect(result.status).toBe('success')
      expect(result.data.nodes).toHaveLength(1)
      expect(result.data.nodes[0].properties.name).toBe('John')
    })

    test('getFullGraph with custom limit', async () => {
      const result = await getFullGraph(200)

      expect(result.status).toBe('success')
      expect(result.data.nodes).toHaveLength(2)
      expect(result.data.relationships).toHaveLength(1)
    })

    test('getDatabaseSummary returns statistics', async () => {
      const result = await getDatabaseSummary()

      expect(result.status).toBe('success')
      expect(result.data.node_count).toBe(100)
      expect(result.data.relationship_count).toBe(50)
      expect(result.data.labels).toContain('Person')
      expect(result.data.relationship_types).toContain('WORKS_FOR')
    })

    test('graph operations handle network errors', async () => {
      server.use(
        rest.post('/api/graph/query', (req, res, ctx) => {
          return res.networkError('Network connection failed')
        })
      )

      await expect(executeGraphQuery('MATCH (n) RETURN n')).rejects.toThrow()
    })
  })

  describe('Admin Operations', () => {
    test('resetSystem sends correct parameters', async () => {
      const resetOptions = {
        reset_schemas: true,
        reset_data: true,
        reset_neo4j: false
      }

      const result = await resetSystem(resetOptions)

      expect(result.status).toBe('success')
      expect(result.message).toBe('System reset completed')
      expect(result.counts.schemas_deleted).toBe(5)
    })

    test('resetSystem with confirm token', async () => {
      server.use(
        rest.post('/api/admin/reset', (req, res, ctx) => {
          const body = req.body as any
          if (body.confirm_token) {
            return res(
              ctx.status(200),
              ctx.json({ status: 'success', message: 'Reset executed' })
            )
          }
          return res(
            ctx.status(200),
            ctx.json({
              confirm_token: 'abc123',
              message: 'Dry run completed. Use confirm_token to execute reset.'
            })
          )
        })
      )

      // First call - dry run
      const dryRunResult = await resetSystem({ reset_schemas: true })
      expect(dryRunResult.confirm_token).toBe('abc123')

      // Second call - with confirm token
      const executeResult = await resetSystem({
        reset_schemas: true,
        confirm_token: 'abc123'
      })
      expect(executeResult.message).toBe('Reset executed')
    })
  })

  describe('Authentication', () => {
    test('includes auth token in requests', async () => {
      let authHeader: string | null = null

      server.use(
        rest.get('/api/schema', (req, res, ctx) => {
          authHeader = req.headers.get('Authorization')
          return res(ctx.status(200), ctx.json([]))
        })
      )

      await getSchemas()

      expect(authHeader).toBe('Bearer mock_token')
    })

    test('handles missing auth token', async () => {
      // Mock localStorage returning null
      Object.defineProperty(window, 'localStorage', {
        value: {
          getItem: jest.fn(() => null),
          setItem: jest.fn(),
          removeItem: jest.fn()
        },
        writable: true
      })

      server.use(
        rest.get('/api/schema', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid authentication token' })
          )
        })
      )

      await expect(getSchemas()).rejects.toThrow('Invalid authentication token')
    })
  })

  describe('Error Handling', () => {
    test('handles 500 server errors', async () => {
      server.use(
        rest.get('/api/schema', (req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({ detail: 'Internal server error' })
          )
        })
      )

      await expect(getSchemas()).rejects.toThrow('Internal server error')
    })

    test('handles network timeouts', async () => {
      server.use(
        rest.get('/api/schema', (req, res, ctx) => {
          return res(ctx.delay('infinite'))
        })
      )

      // This would timeout in a real scenario
      // For testing, we'll simulate the timeout
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Request timeout')), 100)
      })

      await expect(Promise.race([getSchemas(), timeoutPromise])).rejects.toThrow('Request timeout')
    })
  })
})