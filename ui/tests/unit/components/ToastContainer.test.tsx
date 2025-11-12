import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import ToastContainer, { ToastData } from '../../../src/components/ToastContainer';

describe('ToastContainer Component', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
  });

  test('renders multiple toasts', () => {
    const toasts: ToastData[] = [
      { id: '1', type: 'success', message: 'First toast' },
      { id: '2', type: 'error', message: 'Second toast' },
      { id: '3', type: 'success', message: 'Third toast' },
    ];

    render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    expect(screen.getByText('First toast')).toBeInTheDocument();
    expect(screen.getByText('Second toast')).toBeInTheDocument();
    expect(screen.getByText('Third toast')).toBeInTheDocument();
  });

  test('renders nothing when toasts array is empty', () => {
    const { container } = render(<ToastContainer toasts={[]} onClose={mockOnClose} />);

    // Container should exist but have no toast messages
    const toastMessages = container.querySelectorAll('[role="status"]');
    expect(toastMessages.length).toBe(0);
  });

  test('passes onClose handler to toast components', async () => {
    const user = userEvent.setup();
    const toasts: ToastData[] = [{ id: 'toast-1', type: 'success', message: 'Test toast' }];

    render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledWith('toast-1');
  });

  test('renders toasts in correct order', () => {
    const toasts: ToastData[] = [
      { id: '1', type: 'success', message: 'First' },
      { id: '2', type: 'error', message: 'Second' },
      { id: '3', type: 'success', message: 'Third' },
    ];

    const { container } = render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    const toastElements = container.querySelectorAll('.max-w-sm');
    expect(toastElements.length).toBe(3);

    // Check order (messages should appear in the same order as the array)
    expect(toastElements[0].textContent).toContain('First');
    expect(toastElements[1].textContent).toContain('Second');
    expect(toastElements[2].textContent).toContain('Third');
  });

  test('has proper accessibility attributes', () => {
    const toasts: ToastData[] = [{ id: '1', type: 'success', message: 'Accessible toast' }];

    const { container } = render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    const liveRegion = container.querySelector('[aria-live="assertive"]');
    expect(liveRegion).toBeInTheDocument();
  });

  test('renders different toast types with correct styling', () => {
    const toasts: ToastData[] = [
      { id: '1', type: 'success', message: 'Success toast' },
      { id: '2', type: 'error', message: 'Error toast' },
    ];

    const { container } = render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    // Check for success styling (green)
    const successToast = container.querySelector('.bg-green-50');
    expect(successToast).toBeInTheDocument();

    // Check for error styling (red)
    const errorToast = container.querySelector('.bg-red-50');
    expect(errorToast).toBeInTheDocument();
  });

  test('container has fixed positioning for overlay', () => {
    const toasts: ToastData[] = [{ id: '1', type: 'success', message: 'Test' }];

    const { container } = render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    const outerContainer = container.firstChild as HTMLElement;
    expect(outerContainer).toHaveClass('fixed');
    expect(outerContainer).toHaveClass('inset-0');
  });

  test('toasts are stacked with spacing', () => {
    const toasts: ToastData[] = [
      { id: '1', type: 'success', message: 'First' },
      { id: '2', type: 'success', message: 'Second' },
    ];

    const { container } = render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    const stackContainer = container.querySelector('.space-y-4');
    expect(stackContainer).toBeInTheDocument();
  });

  test('handles single toast correctly', () => {
    const toasts: ToastData[] = [{ id: 'solo', type: 'error', message: 'Single toast' }];

    render(<ToastContainer toasts={toasts} onClose={mockOnClose} />);

    expect(screen.getByText('Single toast')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /close/i })).toHaveLength(1);
  });
});
