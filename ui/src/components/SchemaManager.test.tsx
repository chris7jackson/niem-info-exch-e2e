import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { http, HttpResponse } from 'msw'
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
  http.get(`${API_URL}/api/schema`, () => {
    return HttpResponse.json(mockSchemas)
  }),
  http.post(`${API_URL}/api/schema/xsd`, () => {
    return HttpResponse.json({
      schema_id: 'new_schema',
      niem_ndr_report: { status: 'pass', violations: [] },
      import_validation_report: { status: 'pass' },
      is_active: true
    })
  }),
  http.post(`${API_URL}/api/schema/activate/:schemaId`, ({ params }) => {
    return HttpResponse.json({ active_schema_id: params.schemaId })
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

/**
 * SchemaManager Component Tests
 *
 * Purpose: Component rendering and data display tests
 * - Smoke test: Verifies component renders without crashing
 * - Data flow test: Ensures API data displays correctly
 * - Interaction test: Tests schema activation workflow
 *
 * These tests use React Testing Library to render components
 * in a test environment and MSW to mock API responses.
 *
 * NOT tested here:
 * - File uploads (tested in E2E due to jsdom limitations)
 * - Drag and drop interactions (tested in E2E)
 * - Complex multi-step workflows (tested in E2E)
 */
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
      http.get(`${API_URL}/api/schema`, () => {
        return HttpResponse.json([
          { ...mockSchemas[0], active: false },
          { ...mockSchemas[1], active: true }
        ])
      })
    )

    await user.click(activateButtons[0])

    await waitFor(() => {
      const activeLabels = screen.getAllByText(/active/i)
      expect(activeLabels.length).toBeGreaterThan(0)
    })
  })


})

