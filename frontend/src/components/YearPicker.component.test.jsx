import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import YearPicker from './YearPicker';

describe('YearPicker', () => {
  it('shows nothing without years or without a value', () => {
    const { container, rerender } = render(<YearPicker years={[]} value={2025} label="Год" />);
    expect(container.firstChild).toBeNull();
    rerender(<YearPicker years={[2024, 2025]} value={null} label="Год" />);
    expect(container.firstChild).toBeNull();
  });

  it('lists newest years first, marks the current one and reports a changed year as a number', () => {
    const onChange = vi.fn();
    render(<YearPicker years={[2023, 2024, 2025]} value={2024} onChange={onChange} label="Год" />);
    const button = screen.getByRole('button', { name: 'Год: 2024' });
    expect(button.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(button);
    const options = screen.getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual(['2025', '2024', '2023']);
    expect(screen.getByRole('option', { name: '2024' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(screen.getByRole('option', { name: '2023' }));
    expect(onChange).toHaveBeenCalledWith(2023);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('does not report a change when the current year is chosen again, and closes on Escape or an outside tap', () => {
    const onChange = vi.fn();
    render(<div><YearPicker years={[2024, 2025]} value={2025} onChange={onChange} label="Год" /><p>outside</p></div>);
    fireEvent.click(screen.getByRole('button', { name: 'Год: 2025' }));
    fireEvent.click(screen.getByRole('option', { name: '2025' }));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Год: 2025' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Год: 2025' }));
    fireEvent.pointerDown(screen.getByText('outside'));
    expect(screen.queryByRole('listbox')).toBeNull();
  });
});
