// @vitest-environment jsdom
// 20.11.2026, Пульс за 19.11 (пункт 11): «злые серии» на пагинации таблицы истории ipi и fuel-diesel —
// быстрое листание кнопкой, которая отвечает на каждое нажатие. Кнопка-шаг (`data-fe-step`) пишет серию
// как `step_burst`, а не rage; серия по обычной кнопке остаётся злой.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { behaviorInit, flush, _resetForTests } from './behavior';

vi.mock('web-vitals', () => ({ onLCP: vi.fn(), onCLS: vi.fn(), onFCP: vi.fn(), onTTFB: vi.fn() }));
vi.mock('web-vitals/attribution', () => ({ onINP: vi.fn() }));

const ok = () => ({ ok: true, status: 200, headers: { get: () => null }, json: async () => ({ accepted: true }) });
const settle = async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); };

let fetchMock;
const clicks = () => fetchMock.mock.calls
  .filter(([url]) => url === '/api/v1/analytics/behavior')
  .flatMap(([, init]) => JSON.parse(init.body).events)
  .filter((event) => event.t === 'click');

beforeEach(() => {
  _resetForTests();
  localStorage.clear(); sessionStorage.clear();
  document.body.innerHTML = `
    <div class="fe-histtable__pager">
      <button id="earlier" type="button" data-fe-step="next"><svg id="icon"></svg>Раньше</button>
    </div>
    <button id="plain" type="button">Скачать</button>`;
  window.history.replaceState({}, '', '/russia/indicator/ipi');
  Object.defineProperty(navigator, 'webdriver', { configurable: true, value: false });
  Object.defineProperty(navigator, 'sendBeacon', { configurable: true, value: undefined });
  fetchMock = vi.fn().mockResolvedValue(ok());
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('IntersectionObserver', undefined);
  behaviorInit();
});

afterEach(() => {
  _resetForTests();
  vi.restoreAllMocks(); vi.unstubAllGlobals();
});

async function sent() {
  await settle();
  flush();
  await settle();
  return clicks();
}

describe('быстрое листание кнопкой-шагом — не злая серия', () => {
  it('три быстрых нажатия «Раньше»: все клики записаны, rage нет, третий помечен step_burst', async () => {
    for (let i = 0; i < 3; i += 1) document.getElementById('earlier').click();
    const events = await sent();
    expect(events).toHaveLength(3);
    expect(events.every((event) => event.rage === 0)).toBe(true);
    expect(events[2].step_burst).toBe(1);
    expect(events[0].step_burst).toBeUndefined();
  });

  it('нажатие на значок внутри кнопки-шага тоже листание', async () => {
    for (let i = 0; i < 3; i += 1) {
      document.getElementById('icon').dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }
    const events = await sent();
    expect(events[2]).toMatchObject({ rage: 0, step_burst: 1 });
  });

  it('серия по обычной кнопке по-прежнему злая', async () => {
    for (let i = 0; i < 3; i += 1) document.getElementById('plain').click();
    const events = await sent();
    expect(events[2].rage).toBe(1);
    expect(events[2].step_burst).toBeUndefined();
  });
});
