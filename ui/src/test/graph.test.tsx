import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { vi } from 'vitest'

import GraphPage from '../pages/graph'

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
      id: 1,
      labels: ['Person'],
      properties: { name: 'John Doe', age: 30 }
    },
    {
      id: 2,
      labels: ['Company'],
      properties: { name: 'Acme Corp' }
    }
  ],
  relationships: [
    {
      id: 10,
      type: 'WORKS_FOR',
      start_node_id: 1,
      end_node_id: 2,
      properties: { since: '2020' }
    }
  ]
}

const API_URL = 'http://localhost:8000'

const server = setupServer(
  http.get(`${API_URL}/api/graph/full`, (_req, res, ctx) => {
    return HttpResponse.json({
        status: 'success',
        data: mockGraphData
      })
  }),
  http.post(`${API_URL}/api/graph/query`, (_req, res, ctx) => {
    return HttpResponse.json({
        status: 'success',
        data: mockGraphData
      })
  }),
  http.get(`${API_URL}/api/graph/summary`, (_req, res, ctx) => {
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

describe('Graph Page', () => {
  test('renders graph interface with key elements', async () => {
    render(<GraphPage />)

    expect(screen.getByText(/graph visualization/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /load full graph/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/enter cypher query/i)).toBeInTheDocument()
  })

  test('loads and displays graph data with statistics', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    await user.click(screen.getByRole('button', { name: /load full graph/i }))

    await waitFor(() => {
      expect(screen.getByText(/nodes: 2/i)).toBeInTheDocument()
      expect(screen.getByText(/relationships: 1/i)).toBeInTheDocument()
      expect(screen.getByText(/database summary/i)).toBeInTheDocument()
    })
  })

  test('executes custom cypher queries', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    const queryInput = screen.getByPlaceholderText(/enter cypher query/i)
    const executeButton = screen.getByRole('button', { name: /execute query/i })

    await user.type(queryInput, 'MATCH (n:Person) RETURN n')
    await user.click(executeButton)

    await waitFor(() => {
      expect(screen.getByText(/query executed successfully/i)).toBeInTheDocument()
    })
  })

  test('handles errors gracefully', async () => {
    server.use(
      http.get(`${API_URL}/api/graph/full`, (_req, res, ctx) => {
        return HttpResponse.json({ detail: 'Database connection failed' }, { status: 500 })
      })
    )

    const user = userEvent.setup()
    render(<GraphPage />)

    await user.click(screen.getByRole('button', { name: /load full graph/i }))

    await waitFor(() => {
      expect(screen.getByText(/failed to load graph/i)).toBeInTheDocument()
    })
  })

  test('validates query input before execution', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    const executeButton = screen.getByRole('button', { name: /execute query/i })

    // Try to execute empty query
    await user.click(executeButton)

    expect(screen.getByText(/please enter a query/i)).toBeInTheDocument()
  })

  test('handles invalid Cypher syntax errors', async () => {
    server.use(
      http.post(`${API_URL}/api/graph/query`, (_req, res, ctx) => {
        return HttpResponse.json({ detail: 'Invalid Cypher syntax' }, { status: 400 })
      })
    )

    const user = userEvent.setup()
    render(<GraphPage />)

    const queryInput = screen.getByPlaceholderText(/enter cypher query/i)
    const executeButton = screen.getByRole('button', { name: /execute query/i })

    await user.type(queryInput, 'INVALID CYPHER')
    await user.click(executeButton)

    await waitFor(() => {
      expect(screen.getByText(/invalid cypher syntax/i)).toBeInTheDocument()
    })
  })
})
