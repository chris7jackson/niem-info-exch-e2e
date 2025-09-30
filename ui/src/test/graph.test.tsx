import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { rest } from 'msw'
import { setupServer } from 'msw/node'

import GraphPage from './graph'

// Mock Cytoscape since it requires DOM
jest.mock('cytoscape', () => {
  return jest.fn(() => ({
    add: jest.fn(),
    layout: jest.fn(() => ({ run: jest.fn() })),
    on: jest.fn(),
    destroy: jest.fn(),
    elements: jest.fn(() => []),
    style: jest.fn(),
    fit: jest.fn()
  }))
})

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

const server = setupServer(
  rest.get('/api/graph/full', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        data: mockGraphData
      })
    )
  }),
  rest.post('/api/graph/query', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'success',
        data: mockGraphData
      })
    )
  }),
  rest.get('/api/graph/summary', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
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
    )
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('Graph Page', () => {
  test('renders graph interface correctly', async () => {
    render(<GraphPage />)

    expect(screen.getByText(/graph visualization/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /load full graph/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/enter cypher query/i)).toBeInTheDocument()
  })

  test('loads full graph data on button click', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    await user.click(screen.getByRole('button', { name: /load full graph/i }))

    await waitFor(() => {
      expect(screen.getByText(/nodes: 2/i)).toBeInTheDocument()
      expect(screen.getByText(/relationships: 1/i)).toBeInTheDocument()
    })
  })

  test('executes custom cypher query', async () => {
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

  test('handles graph loading errors', async () => {
    server.use(
      rest.get('/api/graph/full', (req, res, ctx) => {
        return res(
          ctx.status(500),
          ctx.json({ detail: 'Database connection failed' })
        )
      })
    )

    const user = userEvent.setup()
    render(<GraphPage />)

    await user.click(screen.getByRole('button', { name: /load full graph/i }))

    await waitFor(() => {
      expect(screen.getByText(/failed to load graph/i)).toBeInTheDocument()
    })
  })

  test('shows loading state while fetching data', async () => {
    server.use(
      rest.get('/api/graph/full', (req, res, ctx) => {
        return res(
          ctx.delay(1000),
          ctx.status(200),
          ctx.json({ status: 'success', data: mockGraphData })
        )
      })
    )

    const user = userEvent.setup()
    render(<GraphPage />)

    await user.click(screen.getByRole('button', { name: /load full graph/i }))

    expect(screen.getByText(/loading graph/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /load full graph/i })).toBeDisabled()
  })

  test('displays graph statistics', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    // Trigger graph load to fetch summary
    await user.click(screen.getByRole('button', { name: /load full graph/i }))

    await waitFor(() => {
      expect(screen.getByText(/database summary/i)).toBeInTheDocument()
      expect(screen.getByText(/person: 1/i)).toBeInTheDocument()
      expect(screen.getByText(/company: 1/i)).toBeInTheDocument()
      expect(screen.getByText(/works_for: 1/i)).toBeInTheDocument()
    })
  })

  test('validates cypher query input', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    const queryInput = screen.getByPlaceholderText(/enter cypher query/i)
    const executeButton = screen.getByRole('button', { name: /execute query/i })

    // Try to execute empty query
    await user.click(executeButton)

    expect(screen.getByText(/please enter a query/i)).toBeInTheDocument()

    // Enter valid query
    await user.type(queryInput, 'MATCH (n) RETURN n')
    expect(screen.queryByText(/please enter a query/i)).not.toBeInTheDocument()
  })

  test('handles query execution errors', async () => {
    server.use(
      rest.post('/api/graph/query', (req, res, ctx) => {
        return res(
          ctx.status(400),
          ctx.json({ detail: 'Invalid Cypher syntax' })
        )
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

  test('provides query examples', () => {
    render(<GraphPage />)

    expect(screen.getByText(/example queries/i)).toBeInTheDocument()
    expect(screen.getByText(/match \(n\) return n limit 25/i)).toBeInTheDocument()
    expect(screen.getByText(/match \(p:person\)/i)).toBeInTheDocument()
  })

  test('allows query limit configuration', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    const limitInput = screen.getByLabelText(/result limit/i)

    // Change limit value
    await user.clear(limitInput)
    await user.type(limitInput, '50')

    expect(limitInput).toHaveValue(50)
  })

  test('updates graph visualization when data changes', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)

    // Load initial data
    await user.click(screen.getByRole('button', { name: /load full graph/i }))

    await waitFor(() => {
      expect(screen.getByText(/nodes: 2/i)).toBeInTheDocument()
    })

    // Execute different query
    const queryInput = screen.getByPlaceholderText(/enter cypher query/i)
    await user.type(queryInput, 'MATCH (n:Person) RETURN n')
    await user.click(screen.getByRole('button', { name: /execute query/i }))

    // Graph should update with new data
    await waitFor(() => {
      expect(screen.getByText(/query executed successfully/i)).toBeInTheDocument()
    })
  })
})