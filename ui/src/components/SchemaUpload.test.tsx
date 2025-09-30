import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { rest } from 'msw'
import { setupServer } from 'msw/node'

import SchemaUpload from './SchemaUpload'

// Mock server for API calls
const server = setupServer(
  rest.post('/api/schema/xsd', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        schema_id: 'test_schema_123',
        niem_ndr_report: {
          status: 'pass',
          message: 'Schema validation successful',
          conformance_target: 'niem-6.0',
          violations: [],
          summary: { error_count: 0 }
        },
        is_active: true
      })
    )
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('SchemaUpload Component', () => {
  test('renders upload form correctly', () => {
    render(<SchemaUpload onUploadSuccess={() => {}} />)

    expect(screen.getByText(/upload xsd schema/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /select file/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /upload schema/i })).toBeDisabled()
  })

  test('enables upload button when file is selected', async () => {
    const user = userEvent.setup()
    render(<SchemaUpload onUploadSuccess={() => {}} />)

    const fileInput = screen.getByLabelText(/choose xsd file/i)
    const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })

    await user.upload(fileInput, file)

    expect(screen.getByRole('button', { name: /upload schema/i })).toBeEnabled()
    expect(screen.getByText('test.xsd')).toBeInTheDocument()
  })

  test('validates file type correctly', async () => {
    const user = userEvent.setup()
    render(<SchemaUpload onUploadSuccess={() => {}} />)

    const fileInput = screen.getByLabelText(/choose xsd file/i)
    const invalidFile = new File(['test content'], 'test.txt', { type: 'text/plain' })

    await user.upload(fileInput, invalidFile)

    expect(screen.getByText(/please select a valid xsd file/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /upload schema/i })).toBeDisabled()
  })

  test('handles successful upload', async () => {
    const user = userEvent.setup()
    const mockOnSuccess = jest.fn()

    render(<SchemaUpload onUploadSuccess={mockOnSuccess} />)

    const fileInput = screen.getByLabelText(/choose xsd file/i)
    const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })

    await user.upload(fileInput, file)
    await user.click(screen.getByRole('button', { name: /upload schema/i }))

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledWith({
        schema_id: 'test_schema_123',
        niem_ndr_report: expect.objectContaining({
          status: 'pass'
        }),
        is_active: true
      })
    })

    expect(screen.getByText(/schema uploaded successfully/i)).toBeInTheDocument()
  })

  test('handles upload failure', async () => {
    server.use(
      rest.post('/api/schema/xsd', (req, res, ctx) => {
        return res(
          ctx.status(400),
          ctx.json({
            detail: 'Schema upload rejected due to NIEM NDR validation failures'
          })
        )
      })
    )

    const user = userEvent.setup()
    render(<SchemaUpload onUploadSuccess={() => {}} />)

    const fileInput = screen.getByLabelText(/choose xsd file/i)
    const file = new File(['<invalid>schema</invalid>'], 'invalid.xsd', { type: 'application/xml' })

    await user.upload(fileInput, file)
    await user.click(screen.getByRole('button', { name: /upload schema/i }))

    await waitFor(() => {
      expect(screen.getByText(/validation failures/i)).toBeInTheDocument()
    })
  })

  test('shows loading state during upload', async () => {
    server.use(
      rest.post('/api/schema/xsd', (req, res, ctx) => {
        return res(
          ctx.delay(1000),
          ctx.status(200),
          ctx.json({ schema_id: 'test', niem_ndr_report: { status: 'pass' }, is_active: true })
        )
      })
    )

    const user = userEvent.setup()
    render(<SchemaUpload onUploadSuccess={() => {}} />)

    const fileInput = screen.getByLabelText(/choose xsd file/i)
    const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })

    await user.upload(fileInput, file)
    const uploadButton = screen.getByRole('button', { name: /upload schema/i })

    await user.click(uploadButton)

    expect(screen.getByText(/uploading/i)).toBeInTheDocument()
    expect(uploadButton).toBeDisabled()
  })

  test('handles authentication errors', async () => {
    server.use(
      rest.post('/api/schema/xsd', (req, res, ctx) => {
        return res(
          ctx.status(401),
          ctx.json({ detail: 'Invalid authentication token' })
        )
      })
    )

    const user = userEvent.setup()
    render(<SchemaUpload onUploadSuccess={() => {}} />)

    const fileInput = screen.getByLabelText(/choose xsd file/i)
    const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })

    await user.upload(fileInput, file)
    await user.click(screen.getByRole('button', { name: /upload schema/i }))

    await waitFor(() => {
      expect(screen.getByText(/authentication/i)).toBeInTheDocument()
    })
  })

  test('resets form after successful upload', async () => {
    const user = userEvent.setup()
    render(<SchemaUpload onUploadSuccess={() => {}} />)

    const fileInput = screen.getByLabelText(/choose xsd file/i)
    const file = new File(['<schema>test</schema>'], 'test.xsd', { type: 'application/xml' })

    await user.upload(fileInput, file)
    await user.click(screen.getByRole('button', { name: /upload schema/i }))

    await waitFor(() => {
      expect(screen.getByText(/schema uploaded successfully/i)).toBeInTheDocument()
    })

    // Form should reset
    expect(screen.getByRole('button', { name: /upload schema/i })).toBeDisabled()
    expect(screen.queryByText('test.xsd')).not.toBeInTheDocument()
  })
})