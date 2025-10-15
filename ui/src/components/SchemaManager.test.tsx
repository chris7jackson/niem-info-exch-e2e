import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { rest } from 'msw'
import { setupServer } from 'msw/node'
import { vi } from 'vitest'

import SchemaManager from './SchemaManager'

const mockSchemas = [
  {
    schema_id: 'schema_1',
    filename: 'main.xsd',
    primary_filename: 'main.xsd',
    all_filenames: ['main.xsd', 'niem-core.xsd'],
    uploaded_at: '2024-01-01T00:00:00Z',
    active: true,
    cmf_filename: 'main.cmf',
    json_schema_filename: 'main.json'
  },
  {
    schema_id: 'schema_2',
    filename: 'other.xsd',
    uploaded_at: '2024-01-02T00:00:00Z',
    active: false
  }
]

const API_URL = 'http://localhost:8000'

const server = setupServer(
  rest.get(`${API_URL}/api/schema`, (_req, res, ctx) => {
    return res(ctx.status(200), ctx.json(mockSchemas))
  }),
  rest.post(`${API_URL}/api/schema/xsd`, (_req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        schema_id: 'new_schema',
        niem_ndr_report: { status: 'pass', violations: [] },
        import_validation_report: { status: 'pass' },
        is_active: true
      })
    )
  }),
  rest.post(`${API_URL}/api/schema/activate/:schemaId`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ active_schema_id: req.params.schemaId })
    )
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('SchemaManager Component', () => {
  test('renders schema manager interface', async () => {
    render(<SchemaManager />)

    expect(screen.getByText(/schema management/i)).toBeInTheDocument()
    expect(screen.getByText(/upload xsd schema/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/uploaded schemas/i)).toBeInTheDocument()
    })
  })

  test('loads and displays existing schemas', async () => {
    render(<SchemaManager />)

    await waitFor(() => {
      expect(screen.getByText('main.xsd')).toBeInTheDocument()
      expect(screen.getByText('other.xsd')).toBeInTheDocument()
    })

    expect(screen.getByText(/active/i)).toBeInTheDocument()
  })

  test('handles file selection via dropzone click', async () => {
    const user = userEvent.setup()
    render(<SchemaManager />)

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText(/select schema folder/i)).toBeInTheDocument()
    })

    // Create a mock file input
    const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement

    if (input) {
      // Simulate file selection
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      })

      await user.upload(input, file)

      await waitFor(() => {
        expect(screen.getByText('test.xsd')).toBeInTheDocument()
      })
    }
  })

  test('handles successful schema upload', async () => {
    const user = userEvent.setup()
    render(<SchemaManager />)

    await waitFor(() => {
      expect(screen.getByText(/select schema folder/i)).toBeInTheDocument()
    })

    const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement

    if (input) {
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      })

      await user.upload(input, file)

      const uploadButton = await screen.findByRole('button', { name: /upload \d+ file/i })
      await user.click(uploadButton)

      await waitFor(() => {
        // After successful upload, file list should be cleared
        expect(screen.queryByText('test.xsd')).not.toBeInTheDocument()
      })
    }
  })

  test('handles upload errors with validation failures', async () => {
    server.use(
      rest.post(`${API_URL}/api/schema/xsd`, (_req, res, ctx) => {
        return res(
          ctx.status(400),
          ctx.json({
            detail: {
              message: 'Schema validation failed',
              niem_ndr_report: {
                status: 'fail',
                violations: [
                  {
                    type: 'error',
                    file: 'test.xsd',
                    message: 'Invalid NIEM element'
                  }
                ]
              }
            }
          })
        )
      })
    )

    const user = userEvent.setup()
    render(<SchemaManager />)

    await waitFor(() => {
      expect(screen.getByText(/select schema folder/i)).toBeInTheDocument()
    })

    const file = new File(['<schema>invalid</schema>'], 'invalid.xsd', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement

    if (input) {
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      })

      await user.upload(input, file)

      const uploadButton = await screen.findByRole('button', { name: /upload \d+ file/i })
      await user.click(uploadButton)

      await waitFor(() => {
        expect(screen.getByText(/schema validation failed/i)).toBeInTheDocument()
      })
    }
  })

  test('activates inactive schema', async () => {
    const user = userEvent.setup()
    render(<SchemaManager />)

    await waitFor(() => {
      expect(screen.getByText('other.xsd')).toBeInTheDocument()
    })

    const activateButtons = screen.getAllByRole('button', { name: /activate/i })
    expect(activateButtons.length).toBeGreaterThan(0)

    // Mock successful activation
    server.use(
      rest.get(`${API_URL}/api/schema`, (_req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            { ...mockSchemas[0], active: false },
            { ...mockSchemas[1], active: true }
          ])
        )
      })
    )

    await user.click(activateButtons[0])

    await waitFor(() => {
      const activeLabels = screen.getAllByText(/active/i)
      expect(activeLabels.length).toBeGreaterThan(0)
    })
  })

  test('allows removing files before upload', async () => {
    const user = userEvent.setup()
    render(<SchemaManager />)

    await waitFor(() => {
      expect(screen.getByText(/select schema folder/i)).toBeInTheDocument()
    })

    const files = [
      new File(['<schema>1</schema>'], 'test1.xsd', { type: 'application/xml' }),
      new File(['<schema>2</schema>'], 'test2.xsd', { type: 'application/xml' })
    ]
    const input = document.querySelector('input[type="file"]') as HTMLInputElement

    if (input) {
      Object.defineProperty(input, 'files', {
        value: files,
        writable: false
      })

      await user.upload(input, files)

      await waitFor(() => {
        expect(screen.getByText('test1.xsd')).toBeInTheDocument()
        expect(screen.getByText('test2.xsd')).toBeInTheDocument()
      })

      // Find remove buttons
      const removeButtons = screen.getAllByRole('button', { name: /remove/i })
      expect(removeButtons.length).toBeGreaterThan(0)

      await user.click(removeButtons[0])

      await waitFor(() => {
        // One file should remain
        const fileNames = screen.queryAllByText(/test\d+\.xsd/)
        expect(fileNames.length).toBeLessThan(2)
      })
    }
  })

  test('filters non-XSD files automatically', async () => {
    const user = userEvent.setup()
    render(<SchemaManager />)

    await waitFor(() => {
      expect(screen.getByText(/select schema folder/i)).toBeInTheDocument()
    })

    const files = [
      new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' }),
      new File(['not xml'], 'test.txt', { type: 'text/plain' }),
      new File(['{}'], 'test.json', { type: 'application/json' })
    ]
    const input = document.querySelector('input[type="file"]') as HTMLInputElement

    if (input) {
      const consoleSpy = vi.spyOn(console, 'info').mockImplementation(() => {})

      Object.defineProperty(input, 'files', {
        value: files,
        writable: false
      })

      await user.upload(input, files)

      await waitFor(() => {
        expect(screen.getByText('test.xsd')).toBeInTheDocument()
        expect(screen.queryByText('test.txt')).not.toBeInTheDocument()
        expect(screen.queryByText('test.json')).not.toBeInTheDocument()
      })

      consoleSpy.mockRestore()
    }
  })
})
