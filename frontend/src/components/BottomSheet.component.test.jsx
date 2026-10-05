import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LocaleProvider } from '../i18n';
import BottomSheet from './BottomSheet';

function renderSheet(props = {}) {
  const onClose = vi.fn();
  const view = render(
    <LocaleProvider locale="ru">
      <BottomSheet open onClose={onClose} id="sheet" ariaLabel="Проверка" footer={<button type="button">Войти</button>} {...props}>
        <a href="/x">Пункт</a>
      </BottomSheet>
    </LocaleProvider>,
  );
  return { onClose, ...view };
}

/** Событие указателя с координатой: jsdom без PointerEvent получает обычное событие с теми же полями (время не 0: React подменяет 0 на текущее). */
function pointer(type, target, clientY, timeStamp = 0) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperties(event, {
    clientY: { value: clientY },
    pointerId: { value: 1 },
    pointerType: { value: 'touch' },
    button: { value: 0 },
    timeStamp: { value: timeStamp },
  });
  fireEvent(target, event);
}

describe('BottomSheet: шторка снизу', () => {
  it('рисуется порталом в body: диалог, фон-затемнение, ручка, тело и закреплённая нижняя полоса', () => {
    renderSheet();
    const sheet = document.getElementById('sheet');
    expect(sheet.parentElement).toBe(document.body);
    expect(sheet.getAttribute('role')).toBe('dialog');
    expect(sheet.getAttribute('aria-modal')).toBe('true');
    expect(sheet.getAttribute('aria-label')).toBe('Проверка');
    expect(sheet.querySelector('.fe-bsheet__handle')).toBeTruthy();
    expect(sheet.querySelector('.fe-bsheet__body a').textContent).toBe('Пункт');
    expect(sheet.querySelector('.fe-bsheet__foot button').textContent).toBe('Войти');
    expect(screen.getByTestId('sheet-scrim')).toBeTruthy();
    // Подсказка про жест есть только для скринридера.
    expect(sheet.querySelector('.sr-only').textContent).toBe('Потяните вниз, чтобы закрыть');
  });

  it('закрыта: ничего не рисует', () => {
    renderSheet({ open: false });
    expect(document.getElementById('sheet')).toBeNull();
    expect(screen.queryByTestId('sheet-scrim')).toBeNull();
  });

  it('нажатие на затемнение и Esc закрывают', () => {
    const { onClose } = renderSheet();
    fireEvent.click(screen.getByTestId('sheet-scrim'));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('при открытии фокус уходит на лист', () => {
    renderSheet();
    expect(document.activeElement).toBe(document.getElementById('sheet'));
  });

  it('свайп вниз за ручку дальше порога закрывает, лист едет за пальцем', () => {
    const { onClose } = renderSheet();
    const grab = screen.getByTestId('sheet-grab');
    const sheet = document.getElementById('sheet');
    pointer('pointerdown', grab, 100, 1000);
    pointer('pointermove', grab, 220, 1100);
    expect(sheet.style.transform).toBe('translateY(120px)');
    pointer('pointerup', grab, 220, 1110);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('короткий и медленный свайп не закрывает: лист возвращается на место', () => {
    const { onClose } = renderSheet();
    const grab = screen.getByTestId('sheet-grab');
    const sheet = document.getElementById('sheet');
    pointer('pointerdown', grab, 100, 1000);
    pointer('pointermove', grab, 130, 1600);
    pointer('pointerup', grab, 130, 1620);
    expect(onClose).not.toHaveBeenCalled();
    expect(sheet.style.transform).toBe('');
  });

  it('свайп вверх лист не двигает', () => {
    renderSheet();
    const grab = screen.getByTestId('sheet-grab');
    const sheet = document.getElementById('sheet');
    pointer('pointerdown', grab, 300, 1000);
    pointer('pointermove', grab, 200, 1100);
    expect(sheet.style.transform).toBe('');
  });
});
