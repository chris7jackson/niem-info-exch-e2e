import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import Toast from '../../../src/components/Toast';

describe('Toast Component', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    mockOnClose.mockClear();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  test('renders success toast with correct styling', () => {
    render(<Toast id="test-1" type="success" message="Success message" onClose={mockOnClose} />);

    const toast = screen.getByText('Success message');
    expect(toast).toBeInTheDocument();

    // Check for green styling (success color)
    const container = toast.closest('div.bg-green-50');
    expect(container).toBeInTheDocument();
  });

  test('renders error toast with correct styling', () => {
    render(<Toast id="test-2" type="error" message="Error message" onClose={mockOnClose} />);

    const toast = screen.getByText('Error message');
    expect(toast).toBeInTheDocument();

    // Check for red styling (error color)
    const container = toast.closest('div.bg-red-50');
    expect(container).toBeInTheDocument();
  });

  test('displays message text', () => {
    const message = 'This is a test toast message';
    render(<Toast id="test-3" type="success" message={message} onClose={mockOnClose} />);

    expect(screen.getByText(message)).toBeInTheDocument();
  });

  test('calls onClose when close button clicked', async () => {
    const user = userEvent.setup({ delay: null });

    render(<Toast id="test-4" type="success" message="Click to close" onClose={mockOnClose} />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledWith('test-4');
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  test('auto-closes after 3 seconds', async () => {
    render(<Toast id="test-5" type="success" message="Auto-close toast" onClose={mockOnClose} />);

    // Initially, onClose should not be called
    expect(mockOnClose).not.toHaveBeenCalled();

    // Fast-forward time by 3 seconds
    vi.advanceTimersByTime(3000);

    // onClose should be called after 3 seconds
    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalledWith('test-5');
    });
  });

  test('does not auto-close before 3 seconds', () => {
    render(<Toast id="test-6" type="error" message="Wait for it" onClose={mockOnClose} />);

    // Fast-forward by 2.9 seconds (just before auto-close)
    vi.advanceTimersByTime(2900);

    // Should not have been called yet
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  test('renders CheckCircleIcon for success toast', () => {
    const { container } = render(
      <Toast id="test-7" type="success" message="Success" onClose={mockOnClose} />
    );

    // Check for the presence of an SVG (icon)
    const icon = container.querySelector('svg.text-green-400');
    expect(icon).toBeInTheDocument();
  });

  test('renders XCircleIcon for error toast', () => {
    const { container } = render(
      <Toast id="test-8" type="error" message="Error" onClose={mockOnClose} />
    );

    // Check for the presence of an SVG with error color
    const icon = container.querySelector('svg.text-red-400');
    expect(icon).toBeInTheDocument();
  });

  test('close button has proper accessibility attributes', () => {
    render(<Toast id="test-9" type="success" message="Accessible toast" onClose={mockOnClose} />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    expect(closeButton).toBeInTheDocument();
  });

  test('cleanup timer when component unmounts', () => {
    const { unmount } = render(
      <Toast id="test-10" type="success" message="Unmount test" onClose={mockOnClose} />
    );

    // Unmount before auto-close timer fires
    unmount();

    // Fast-forward past auto-close time
    vi.advanceTimersByTime(3000);

    // onClose should not be called because timer was cleaned up
    expect(mockOnClose).not.toHaveBeenCalled();
  });
});
