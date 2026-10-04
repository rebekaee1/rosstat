import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import Chip from './Chip';
import { OverflowChipGroup } from './ChipGroup';

afterEach(cleanup);

const modes = ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8'].map((id) => ({ id, label: `Режим ${id}` }));

function view(currentId) {
  return render(
    <LocaleProvider locale="ru">
      <OverflowChipGroup
        label="Детализация"
        dense
        items={modes}
        isActive={(item) => item.id === currentId}
        renderChip={(item) => (
          <Chip key={item.id} active={item.id === currentId}>{item.label}</Chip>
        )}
      />
    </LocaleProvider>,
  );
}

describe('OverflowChipGroup', () => {
  it('прячет редкие режимы под «Ещё режимы» и раскрывает по нажатию', () => {
    view('m1');
    expect(screen.queryByRole('button', { name: 'Режим m8' })).toBeNull();
    const more = screen.getByRole('button', { name: /Ещё режимы \(3\)/ });
    expect(more.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(more);
    expect(screen.getByRole('button', { name: 'Режим m8' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Свернуть' }).getAttribute('aria-expanded')).toBe('true');
  });

  it('выбранный режим из «хвоста» остаётся на виду', () => {
    view('m8');
    expect(screen.getByRole('button', { name: 'Режим m8' }).getAttribute('aria-pressed')).toBe('true');
  });
});
