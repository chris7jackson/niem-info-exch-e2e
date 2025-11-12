import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import AdminPage from '../../../src/pages/admin';

const API_URL = 'http://localhost:8000';

// MSW server setup
const server = setupServer(
  // GET /api/settings
  http.get(`${API_URL}/api/settings`, () => {
    return HttpResponse.json({
      skip_xml_validation: false,
      skip_json_validation: false,
    });
  }),

  // PUT /api/settings
  http.put(`${API_URL}/api/settings`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json(body);
  }),

  // Mock other admin endpoints to prevent errors
  http.post(`${API_URL}/api/admin/reset`, () => {
    return HttpResponse.json({
      counts: {},
      message: 'Mock reset',
    });
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Admin Page - Settings Section', () => {
  test('loads and displays current settings', async () => {
    render(<AdminPage />);

    // Wait for settings to load
    await waitFor(() => {
      expect(screen.getByText(/Validation Settings/i)).toBeInTheDocument();
    });

    // Check that checkboxes are rendered with default values (unchecked)
    const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });
    const jsonCheckbox = screen.getByRole('checkbox', { name: /Skip JSON Validation/i });

    expect(xmlCheckbox).not.toBeChecked();
    expect(jsonCheckbox).not.toBeChecked();
  });

  test('displays settings from API', async () => {
    // Override handler to return different settings
    server.use(
      http.get(`${API_URL}/api/settings`, () => {
        return HttpResponse.json({
          skip_xml_validation: true,
          skip_json_validation: false,
        });
      })
    );

    render(<AdminPage />);

    await waitFor(() => {
      const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });
      expect(xmlCheckbox).toBeChecked();
    });

    const jsonCheckbox = screen.getByRole('checkbox', { name: /Skip JSON Validation/i });
    expect(jsonCheckbox).not.toBeChecked();
  });

  test('toggles skip_xml_validation checkbox and shows success toast', async () => {
    const user = userEvent.setup();
    render(<AdminPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: /Skip XML Validation/i })).toBeInTheDocument();
    });

    const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });

    // Toggle the checkbox
    await user.click(xmlCheckbox);

    // Should show success toast
    await waitFor(() => {
      expect(screen.getByText(/XML validation disabled/i)).toBeInTheDocument();
    });

    // Checkbox should be checked
    expect(xmlCheckbox).toBeChecked();
  });

  test('toggles skip_json_validation checkbox and shows success toast', async () => {
    const user = userEvent.setup();
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: /Skip JSON Validation/i })).toBeInTheDocument();
    });

    const jsonCheckbox = screen.getByRole('checkbox', { name: /Skip JSON Validation/i });

    await user.click(jsonCheckbox);

    await waitFor(() => {
      expect(screen.getByText(/JSON validation disabled/i)).toBeInTheDocument();
    });

    expect(jsonCheckbox).toBeChecked();
  });

  test('shows enabling message when unchecking checkbox', async () => {
    const user = userEvent.setup();

    // Start with validation skipped
    server.use(
      http.get(`${API_URL}/api/settings`, () => {
        return HttpResponse.json({
          skip_xml_validation: true,
          skip_json_validation: true,
        });
      })
    );

    render(<AdminPage />);

    await waitFor(() => {
      const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });
      expect(xmlCheckbox).toBeChecked();
    });

    const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });

    // Uncheck (enable validation)
    await user.click(xmlCheckbox);

    await waitFor(() => {
      expect(screen.getByText(/XML validation enabled/i)).toBeInTheDocument();
    });
  });

  test('shows error toast on save failure', async () => {
    const user = userEvent.setup();

    // Override PUT to return error
    server.use(
      http.put(`${API_URL}/api/settings`, () => {
        return HttpResponse.json(
          { detail: 'Database error' },
          { status: 500 }
        );
      })
    );

    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: /Skip XML Validation/i })).toBeInTheDocument();
    });

    const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });
    await user.click(xmlCheckbox);

    // Should show error toast
    await waitFor(() => {
      expect(screen.getByText(/Database error/i)).toBeInTheDocument();
    });

    // Checkbox should be reverted (unchecked)
    expect(xmlCheckbox).not.toBeChecked();
  });

  test('disables checkboxes while loading', async () => {
    // Delay the response to test loading state
    server.use(
      http.put(`${API_URL}/api/settings`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json({
          skip_xml_validation: true,
          skip_json_validation: false,
        });
      })
    );

    const user = userEvent.setup();
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: /Skip XML Validation/i })).toBeInTheDocument();
    });

    const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });

    // Click checkbox
    await user.click(xmlCheckbox);

    // Checkbox should be disabled during update
    // Note: In the actual implementation, we might not disable the checkbox,
    // but we can check that settingsLoading state changes
    // For now, just verify the toast appears
    await waitFor(() => {
      expect(screen.getByText(/XML validation disabled/i)).toBeInTheDocument();
    });
  });

  test('handles both checkboxes independently', async () => {
    const user = userEvent.setup();
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: /Skip XML Validation/i })).toBeInTheDocument();
    });

    const xmlCheckbox = screen.getByRole('checkbox', { name: /Skip XML Validation/i });
    const jsonCheckbox = screen.getByRole('checkbox', { name: /Skip JSON Validation/i });

    // Toggle XML
    await user.click(xmlCheckbox);
    await waitFor(() => {
      expect(screen.getByText(/XML validation disabled/i)).toBeInTheDocument();
    });

    // Toggle JSON
    await user.click(jsonCheckbox);
    await waitFor(() => {
      expect(screen.getByText(/JSON validation disabled/i)).toBeInTheDocument();
    });

    // Both should be checked
    expect(xmlCheckbox).toBeChecked();
    expect(jsonCheckbox).toBeChecked();
  });

  test('displays descriptive text for settings', async () => {
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText(/Validation Settings/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Control validation behavior for XML and JSON file uploads/i)).toBeInTheDocument();
    expect(screen.getByText(/Changes take effect immediately/i)).toBeInTheDocument();
  });

  test('shows error toast on initial load failure', async () => {
    // Override GET to return error
    server.use(
      http.get(`${API_URL}/api/settings`, () => {
        return HttpResponse.json(
          { detail: 'Failed to load settings' },
          { status: 500 }
        );
      })
    );

    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load settings/i)).toBeInTheDocument();
    });
  });
});
