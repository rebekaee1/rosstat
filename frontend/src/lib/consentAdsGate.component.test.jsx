/**
 * Гейт рекламы РСЯ в `public/consent.js` (инцидент fill-rate 2026-08-27).
 *
 * Инвариант: `context.js` (запрос объявления) подключается ТОЛЬКО после
 * доверенного ввода человека. Робот (bot-UA / webdriver) и синтетические
 * события рекламу не запрашивают — иначе площадка копит нераспроданный
 * инвентарь, fill rate падает (97% → 11%) и Яндекс снижает оценку качества.
 *
 * Метрика при этом грузится всем: роботов она фильтрует сама, а нам нужен
 * полный трафик. Файл тестируется в jsdom, потому что bootstrap — не модуль,
 * а IIFE: читаем исходник с диска и исполняем в окне.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

// Путь от самого теста, а не от cwd: работает и в CI, и при запуске из корня.
const SRC = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), '../../public/consent.js'),
  'utf8'
);

const ADS_SRC = 'https://yandex.ru/ads/system/context.js';

/**
 * Живой ввод человека. В jsdom `dispatchEvent` всегда даёт isTrusted=false,
 * поэтому настоящий жест воспроизводим вызовом того же обработчика с
 * trusted-событием — гейт слушает именно его.
 */
function humanGesture(type = 'pointermove') {
  const handler = window.__feAdsGate?.signal;
  if (!handler) return false;
  handler({ type, isTrusted: true });
  return true;
}

function adsRequested() {
  return [...document.scripts].some((s) => s.src === ADS_SRC);
}

function metrikaRequested() {
  return [...document.scripts].some((s) => s.src.includes('mc.yandex.ru/metrika'));
}

/** Запускает bootstrap в текущем окне с подменённым userAgent. */
function boot({ ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145', webdriver = false } = {}) {
  // Метрика вставляется через insertBefore относительно первого <script>
  // документа. В реальном HTML это сам /consent.js — воспроизводим.
  document.head.appendChild(
    Object.assign(document.createElement('script'), { src: '/consent.js' })
  );
  Object.defineProperty(window.navigator, 'userAgent', {
    value: ua,
    configurable: true,
  });
  Object.defineProperty(window.navigator, 'webdriver', {
    value: webdriver,
    configurable: true,
  });
  new Function(SRC).call(window);
  // Bootstrap ждёт window.load, если документ ещё не complete.
  window.dispatchEvent(new Event('load'));
}

beforeEach(() => {
  document.head.innerHTML = '';
  document.body.innerHTML = '';
  window.localStorage.clear();
  delete window.__feApplyConsent;
  delete window.__feAdsGate;
  delete window.ym;
  delete window.yaContextCb;
});

afterEach(() => {
  document.head.innerHTML = '';
});

describe('гейт рекламы: человек', () => {
  it('до ввода реклама не запрошена, Метрика — уже да', () => {
    boot();
    expect(window.__feAdsGate.armed).toBe(true);
    expect(window.__feAdsGate.requested).toBe(false);
    expect(adsRequested()).toBe(false);
    expect(metrikaRequested()).toBe(true);
  });

  it('доверенный ввод (движение мыши) запрашивает рекламу', () => {
    boot();
    humanGesture('pointermove');
    expect(window.__feAdsGate.requested).toBe(true);
    expect(adsRequested()).toBe(true);
  });

  it('скролл мобильного читателя тоже открывает гейт', () => {
    boot({ ua: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) Safari' });
    humanGesture('scroll');
    expect(adsRequested()).toBe(true);
  });

  it('гейт слушает жесты чтения: мышь, тач, скролл, клавиши', () => {
    boot();
    // Контракт списка HUMAN_EVENTS: без scroll/touchstart мобильный читатель
    // остался бы без рекламы (он не двигает мышью).
    for (const type of ['pointerdown', 'pointermove', 'touchstart', 'wheel', 'scroll', 'keydown']) {
      expect(SRC).toContain(`'${type}'`);
    }
  });

  it('второй жест не создаёт второй тег context.js', () => {
    boot();
    humanGesture('pointermove');
    humanGesture('keydown');
    const tags = [...document.scripts].filter((s) => s.src === ADS_SRC);
    expect(tags).toHaveLength(1);
  });
});

describe('гейт рекламы: роботы', () => {
  it('YandexBot не запрашивает рекламу даже после событий', () => {
    boot({
      ua: 'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots) Chrome/145',
    });
    // Робот вообще не получает обработчика: слушателей не навешиваем.
    expect(window.__feAdsGate.robot).toBe(true);
    expect(window.__feAdsGate.signal).toBeFalsy();
    expect(humanGesture('pointermove')).toBe(false);
    window.dispatchEvent(new Event('scroll'));
    expect(adsRequested()).toBe(false);
  });

  it('headless/webdriver не запрашивает рекламу', () => {
    boot({ webdriver: true });
    expect(window.__feAdsGate.robot).toBe(true);
    expect(humanGesture('pointermove')).toBe(false);
    expect(adsRequested()).toBe(false);
  });

  it('синтетический клик (isTrusted=false) рекламу не открывает', () => {
    boot();
    // Ровно так headless имитирует человека: dispatchEvent из скрипта.
    window.dispatchEvent(new Event('pointerdown'));
    window.dispatchEvent(new Event('scroll'));
    expect(adsRequested()).toBe(false);
    expect(window.__feAdsGate.requested).toBe(false);
  });

  it('США/Сингапур-скрейперы на Chrome-UA: без жеста рекламы нет', () => {
    // Инцидент 2026-09-03: 8k сессий с Chrome-UA и нулём следов ввода.
    boot({ ua: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/145.0.0.0 Safari/537.36' });
    expect(window.__feAdsGate.robot).toBe(false);
    expect(adsRequested()).toBe(false);
  });
});

describe('явный выбор в баннере', () => {
  it('согласие кликом открывает рекламу без второго жеста', () => {
    boot();
    window.__feApplyConsent({ analytics: true, ads: true }, { explicit: true });
    expect(adsRequested()).toBe(true);
  });

  it('отказ от рекламы не грузит context.js даже при вводе', () => {
    window.localStorage.setItem(
      'fe:consent:v1',
      JSON.stringify({ v: '2026-06-16', analytics: true, ads: false })
    );
    boot();
    window.dispatchEvent(new Event('pointermove'));
    expect(adsRequested()).toBe(false);
  });
});
