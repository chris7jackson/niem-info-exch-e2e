import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { vi } from 'vitest'

import GraphPage from '../../../src/pages/graph'

// Mock Cytoscape since it requires DOM
vi.mock('cytoscape', () => ({
  default: vi.fn(() => ({
    add: vi.fn(),
    layout: vi.fn(() => ({ run: vi.fn() })),
    on: vi.fn(),
    destroy: vi.fn(),
    elements: vi.fn(() => []),
    style: vi.fn(),
    fit: vi.fn()
  }))
}))

const mockGraphData = {
  nodes: [
    {
      id: '1',
      label: 'Person',
      labels: ['Person'],
      properties: { name: 'John Doe', age: 30 }
    },
    {
      id: '2',
      label: 'Company',
      labels: ['Company'],
      properties: { name: 'Acme Corp' }
    }
  ],
  relationships: [
    {
      id: '10',
      type: 'WORKS_FOR',
      startNode: '1',
      endNode: '2',
      properties: { since: '2020' }
    }
  ],
  metadata: {
    nodeLabels: ['Person', 'Company'],
    relationshipTypes: ['WORKS_FOR'],
    nodeCount: 2,
    relationshipCount: 1
  }
}

const API_URL = 'http://localhost:8000'

const server = setupServer(
  http.get(`${API_URL}/api/graph/full`, () => {
    return HttpResponse.json({
      status: 'success',
      data: mockGraphData
    })
  }),
  http.post(`${API_URL}/api/graph/query`, () => {
    return HttpResponse.json({
      status: 'success',
      data: mockGraphData
    })
  }),
  http.get(`${API_URL}/api/graph/summary`, () => {
    return HttpResponse.json({
      status: 'success',
      data: {
        node_count: 2,
        relationship_count: 1,
        labels: ['Person', 'Company'],
        relationship_types: ['WORKS_FOR'],
        node_counts_by_label: { Person: 1, Company: 1 },
        relationship_counts_by_type: { WORKS_FOR: 1 }
      }
    })
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

/**
 * Graph Page Component Tests
 *
 * Purpose: Graph visualization component rendering and data display tests
 * - Smoke test: Verifies component renders with all controls
 * - Data flow test: Ensures graph data loads and displays statistics
 * - Error handling tests: Validates error states display correctly
 *
 * These tests use React Testing Library with a mocked Cytoscape instance
 * since graph visualization requires complex DOM interactions.
 *
 * NOT tested here:
 * - Cytoscape interactions (click, zoom, pan) - tested in E2E
 * - Complex query execution workflows - tested in E2E
 * - Graph layout and rendering performance - tested in E2E
 */
describe('Graph Page', () => {
  test('renders graph interface with key elements', async () => {
    render(<GraphPage />)

    expect(screen.getByRole('heading', { name: /graph visualization/i, level: 1 })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /complete graph/i })).toHaveLength(1)
    expect(screen.getByRole('textbox', { name: /cypher query/i })).toBeInTheDocument()
  })

  test('loads and displays graph data with statistics', async () => {
    render(<GraphPage />)

    // Wait for initial load (happens automatically on mount)
    await waitFor(() => {
      expect(screen.getByText(/2 nodes/i)).toBeInTheDocument()
      expect(screen.getByText(/1 relationships/i)).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  test('handles errors gracefully', async () => {
    server.use(
      http.post(`${API_URL}/api/graph/query`, () => {
        return HttpResponse.json({ detail: 'Database connection failed' }, { status: 500 })
      })
    )

    render(<GraphPage />)

    // Component auto-loads on mount, so error should appear
    await waitFor(() => {
      expect(screen.getByText(/query error/i)).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  test('handles invalid Cypher syntax errors', async () => {
    server.use(
      http.post(`${API_URL}/api/graph/query`, () => {
        return HttpResponse.json({ detail: 'Invalid Cypher syntax' }, { status: 400 })
      })
    )

    render(<GraphPage />)

    // Wait for initial error from bad query
    await waitFor(() => {
      expect(screen.getByText(/query error/i)).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})
