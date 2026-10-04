import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import WorldViewModePicker from './WorldViewModePicker';

vi.mock('../lib/track', () => ({ track: vi.fn(), events: { CHART_MODE_CHANGE: 'chart_mode_change' } }));

const MODES = [
  { id: 'level-monthly', type: 'level', freq: 'monthly', group: 'Уровень', label: 'По месяцам', available: false, official: true },
  { id: 'level-quarterly', type: 'level', freq: 'quarterly', group: 'Уровень', label: 'По кварталам', available: true, official: true },
  { id: 'level-annual', type: 'level', freq: 'annual', group: 'Уровень', label: 'По годам', available: true, official: true },
  { id: 'yoy-annual', type: 'yoy', freq: 'annual', group: 'К году', label: 'По годам', available: true, official: true },
  { id: 'index-annual', type: 'index', freq: 'annual', group: 'Индекс', label: 'По годам', available: true, official: true },
];

function renderPicker(props) {
  return render(<LocaleProvider><WorldViewModePicker modes={MODES} currentMode="level-annual" onChange={() => {}} {...props} /></LocaleProvider>);
}

describe('WorldViewModePicker', () => {
  it('speaks plainly: «Показать как», «Детализация», no «режим», «срез» or «уровень»', () => {
    const { container } = renderPicker();
    expect(screen.getByText('Показать как')).toBeTruthy();
    expect(screen.getByText('Детализация')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Значения' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Год к году' })).toBeTruthy();
    expect(container.textContent).not.toMatch(/Режим|Срез|Уровень|нет официального ряда/);
  });

  it('hides unavailable frequencies instead of listing them as greyed-out chips', () => {
    renderPicker();
    expect(screen.queryByRole('button', { name: /По месяцам/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'По кварталам' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'По годам' })).toBeTruthy();
  });

  it('switches the mode on a click and keeps the current one pressed', () => {
    const onChange = vi.fn();
    renderPicker({ onChange });
    expect(screen.getByRole('button', { name: 'По годам' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'По кварталам' }));
    expect(onChange).toHaveBeenCalledWith('level-quarterly');
    fireEvent.click(screen.getByRole('button', { name: 'Год к году' }));
    expect(onChange).toHaveBeenLastCalledWith('yoy-annual');
  });

  it('renders nothing when there is no real choice', () => {
    const { container } = renderPicker({ modes: [MODES[2]] });
    expect(container.innerHTML).toBe('');
  });
});
