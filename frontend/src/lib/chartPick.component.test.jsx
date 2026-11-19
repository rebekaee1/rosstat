import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useChartPick } from './chartPick';

describe('useChartPick — закрепление точки нажатием (19.11.2026)', () => {
  it('нажатие закрепляет подпись точки и вызывает onPick один раз; повторное нажатие снимает выбор без onPick', () => {
    const onPick = vi.fn();
    const { result } = renderHook(() => useChartPick(onPick));
    act(() => result.current.handlePlotClick({ activeLabel: 2023 }));
    expect(result.current.picked).toBe(2023);
    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onPick).toHaveBeenCalledWith(2023);
    act(() => result.current.handlePlotClick({ activeLabel: 2023 }));
    expect(result.current.picked).toBeNull();
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  it('нажатие на другую точку переносит выбор', () => {
    const { result } = renderHook(() => useChartPick());
    act(() => result.current.handlePlotClick({ activeLabel: '2024-01-01' }));
    act(() => result.current.handlePlotClick({ activeLabel: '2024-02-01' }));
    expect(result.current.picked).toBe('2024-02-01');
  });

  it('нажатие мимо точек (нет activeLabel) ничего не меняет', () => {
    const onPick = vi.fn();
    const { result } = renderHook(() => useChartPick(onPick));
    act(() => result.current.handlePlotClick(null));
    act(() => result.current.handlePlotClick({ activeLabel: '' }));
    expect(result.current.picked).toBeNull();
    expect(onPick).not.toHaveBeenCalled();
  });

  it('отпускание после перетаскивания гасит ровно одно следующее нажатие', () => {
    const onPick = vi.fn();
    const { result } = renderHook(() => useChartPick(onPick));
    const suppress = result.current.suppressNextPick;
    act(() => result.current.suppressNextPick());
    act(() => result.current.handlePlotClick({ activeLabel: 2020 }));
    expect(result.current.picked).toBeNull();
    act(() => result.current.handlePlotClick({ activeLabel: 2020 }));
    expect(result.current.picked).toBe(2020);
    expect(onPick).toHaveBeenCalledTimes(1);
    // Ссылка стабильна: её держат обработчики указателя в useCallback.
    expect(result.current.suppressNextPick).toBe(suppress);
  });
});
