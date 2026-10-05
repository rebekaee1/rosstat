/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import { ViewModesPanel } from './ViewModesPanel';
import ModeGroupsPicker from './ModeGroupsPicker';
import ViewModePicker from './ViewModePicker';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, key) => String(key) }),
}));

afterEach(cleanup);

const wrap = (ui) => render(
  <LocaleProvider locale="ru"><MemoryRouter>{ui}</MemoryRouter></LocaleProvider>,
);

const GROUPS = [
  { id: 'yoy', label: 'Год к году', rawLabel: 'Год к году' },
  { id: 'end', label: 'На конец', rawLabel: 'На конец периода' },
];

describe('ViewModesPanel', () => {
  it('сворачивает переключатели в одну строку с тем, что выбрано сейчас', () => {
    const { container } = wrap(
      <ViewModesPanel>
        <ModeGroupsPicker
          title="Показать как"
          groups={GROUPS}
          activeGroupId="end"
          onTopClick={() => {}}
          subModes={[{ mode: 'm', label: 'По месяцам' }, { mode: 'q', label: 'По кварталам' }]}
          currentMode="q"
          onSubClick={() => {}}
        />
      </ViewModesPanel>,
    );
    const toggle = screen.getByRole('button', { name: /Изменить вид/ });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(toggle.textContent).toContain('На конец, по кварталам');
    expect(container.querySelector('.fe-vm-panel').getAttribute('data-open')).toBe('false');

    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(container.querySelector('.fe-vm-panel').getAttribute('data-open')).toBe('true');
    expect(toggle.textContent).toContain('Свернуть');
  });

  it('тот же переключатель, показанный дважды (телефон и компьютер), даёт одну подпись', () => {
    wrap(
      <ViewModesPanel>
        <ViewModePicker title="Показать как" modes={[{ mode: 'a', label: 'Значения' }, { mode: 'b', label: 'Индекс' }]} currentMode="b" onChange={() => {}} />
        <ViewModePicker title="Показать как" modes={[{ mode: 'a', label: 'Значения' }, { mode: 'b', label: 'Индекс' }]} currentMode="b" onChange={() => {}} />
      </ViewModesPanel>,
    );
    expect(screen.getByRole('button', { name: /Изменить вид/ }).textContent).toContain('Вид графикаИндекс');
    expect(screen.getByRole('button', { name: /Изменить вид/ }).textContent).not.toContain('Индекс, Индекс');
  });

  it('без переключателей со своей подписью ничего не сворачивает', () => {
    wrap(<ViewModesPanel><p>Содержимое</p></ViewModesPanel>);
    expect(screen.queryByRole('button', { name: /Изменить вид/ })).toBeNull();
    expect(screen.getByText('Содержимое')).toBeTruthy();
  });
});
