// @vitest-environment jsdom
// 19.11.2026, Пульс id 256: клик по подписи чекбокса браузер повторяет кликом по самому чекбоксу.
// Раньше трекер писал оба: один клик человека = два события, два клика = «злая серия».
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
    <label id="consent"><input id="box" type="checkbox"><span id="txt">Я ознакомлен с условиями</span></label>
    <label for="email" id="email-label">Email</label><input id="email" type="email">`;
  window.history.replaceState({}, '', '/register');
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

describe('клик по подписи поля — одно событие', () => {
  it('браузер дублирует клик по подписи на чекбокс, трекер пишет только клик человека', async () => {
    document.getElementById('txt').click();
    expect(document.getElementById('box').checked).toBe(true); // поведение страницы не тронуто
    const events = await sent();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ rage: 0, dead: 0 });
  });

  it('два быстрых клика по подписи — два события и не «злая серия»', async () => {
    document.getElementById('txt').click();
    document.getElementById('txt').click();
    const events = await sent();
    expect(events).toHaveLength(2);
    expect(events.every((event) => event.rage === 0)).toBe(true);
  });

  it('три быстрых клика человека по-прежнему серия', async () => {
    for (let i = 0; i < 3; i += 1) document.getElementById('txt').click();
    const events = await sent();
    expect(events).toHaveLength(3);
    expect(events[2].rage).toBe(1);
  });

  it('прямой клик по чекбоксу и подпись через for= считаются по одному разу', async () => {
    document.getElementById('box').click();
    document.getElementById('email-label').click();
    const events = await sent();
    expect(events).toHaveLength(2);
  });
});
