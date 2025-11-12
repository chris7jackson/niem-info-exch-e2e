import { renderHook, act } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import { useToast } from '../../../src/hooks/useToast';

describe('useToast Hook', () => {
  test('initializes with empty toasts array', () => {
    const { result } = renderHook(() => useToast());

    expect(result.current.toasts).toEqual([]);
  });

  test('showSuccess adds success toast to array', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showSuccess('Operation successful');
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]).toMatchObject({
      type: 'success',
      message: 'Operation successful',
    });
    expect(result.current.toasts[0].id).toBeDefined();
  });

  test('showError adds error toast to array', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showError('Something went wrong');
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]).toMatchObject({
      type: 'error',
      message: 'Something went wrong',
    });
    expect(result.current.toasts[0].id).toBeDefined();
  });

  test('closeToast removes toast by id', () => {
    const { result } = renderHook(() => useToast());

    // Add two toasts
    act(() => {
      result.current.showSuccess('First toast');
      result.current.showError('Second toast');
    });

    expect(result.current.toasts).toHaveLength(2);

    const firstToastId = result.current.toasts[0].id;

    // Remove first toast
    act(() => {
      result.current.closeToast(firstToastId);
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].message).toBe('Second toast');
  });

  test('multiple toasts can be displayed simultaneously', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showSuccess('Toast 1');
      result.current.showSuccess('Toast 2');
      result.current.showError('Toast 3');
    });

    expect(result.current.toasts).toHaveLength(3);
    expect(result.current.toasts[0].message).toBe('Toast 1');
    expect(result.current.toasts[1].message).toBe('Toast 2');
    expect(result.current.toasts[2].message).toBe('Toast 3');
  });

  test('each toast has a unique id', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showSuccess('Toast 1');
      result.current.showSuccess('Toast 2');
      result.current.showSuccess('Toast 3');
    });

    const ids = result.current.toasts.map((toast) => toast.id);
    const uniqueIds = new Set(ids);

    expect(uniqueIds.size).toBe(3); // All IDs should be unique
  });

  test('showToast can be called directly with type', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showToast('success', 'Direct call');
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]).toMatchObject({
      type: 'success',
      message: 'Direct call',
    });
  });

  test('closeToast does nothing if id not found', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showSuccess('Test toast');
    });

    expect(result.current.toasts).toHaveLength(1);

    act(() => {
      result.current.closeToast('non-existent-id');
    });

    // Should still have the original toast
    expect(result.current.toasts).toHaveLength(1);
  });

  test('toasts maintain order when added', () => {
    const { result } = renderHook(() => useToast());

    const messages = ['First', 'Second', 'Third'];

    act(() => {
      messages.forEach((msg) => result.current.showSuccess(msg));
    });

    expect(result.current.toasts.map((t) => t.message)).toEqual(messages);
  });
});
