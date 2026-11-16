import { describe, expect, it } from 'vitest';
import {
  NEW_VISITOR_MAX_VISITS, TELEGRAM_BOT_URL, TELEGRAM_CHANNEL_URL, WELCOME_KEY, WELCOME_STEPS, WELCOME_STEPS_EN, canRemember, clampStep,
  isCrawlerUa, isManualRequest, manualStartStep, markWelcomeSeen, readWelcomeSeen, searchHref, shouldAutoOpenWelcome, welcomeMotionLevel,
  welcomeScreens,
} from './welcome';

function memoryStorage({ broken = false } = {}) {
  const data = new Map();
  return {
    getItem: (k) => (broken ? (() => { throw new Error('denied'); })() : (data.has(k) ? data.get(k) : null)),
    setItem: (k, v) => { if (broken) throw new Error('denied'); data.set(k, String(v)); },
    removeItem: (k) => { data.delete(k); },
  };
}

const NEW_GUEST_ON_HOME = {
  enabled: true, pathname: '/', authLoading: false, isAuthed: false, seen: false, visits: 1, canStore: true,
  automation: false, crawler: false, standalone: false, embedded: false,
};

describe('приветственный экран: кому открывать', () => {
  it('открывается новому гостю на главной при включённом флаге', () => {
    expect(shouldAutoOpenWelcome(NEW_GUEST_ON_HOME)).toBe(true);
  });

  it('без флага сервера не открывается никогда (по умолчанию выключено)', () => {
    expect(shouldAutoOpenWelcome({ ...NEW_GUEST_ON_HOME, enabled: false })).toBe(false);
    expect(shouldAutoOpenWelcome({ ...NEW_GUEST_ON_HOME, enabled: undefined })).toBe(false);
    expect(shouldAutoOpenWelcome({ ...NEW_GUEST_ON_HOME, enabled: 'true' })).toBe(false);
  });

  it('не перебивает того, кто пришёл из поиска на страницу с данными', () => {
    for (const pathname of ['/russia/indicator/cpi', '/germany', '/compare', '/calculator', '/login', '/register']) {
      expect(shouldAutoOpenWelcome({ ...NEW_GUEST_ON_HOME, pathname })).toBe(false);
    }
  });

  it.each([
    ['уже видел', { seen: true }],
    ['вошёл в аккаунт', { isAuthed: true }],
    ['вход ещё проверяется', { authLoading: true }],
    ['давний посетитель', { visits: NEW_VISITOR_MAX_VISITS + 1 }],
    ['память браузера недоступна', { canStore: false }],
    ['автоматика', { automation: true }],
    ['поисковый робот', { crawler: true }],
    ['установленное приложение', { standalone: true }],
    ['встроенная страница', { embedded: true }],
  ])('не открывается: %s', (_name, patch) => {
    expect(shouldAutoOpenWelcome({ ...NEW_GUEST_ON_HOME, ...patch })).toBe(false);
  });

  it('первые заходы считаются новыми включительно по порог', () => {
    expect(shouldAutoOpenWelcome({ ...NEW_GUEST_ON_HOME, visits: NEW_VISITOR_MAX_VISITS })).toBe(true);
    expect(shouldAutoOpenWelcome({ ...NEW_GUEST_ON_HOME, visits: undefined })).toBe(true);
  });
});

describe('приветственный экран: память и служебное', () => {
  it('запоминает исход и читает его обратно', () => {
    const storage = memoryStorage();
    expect(readWelcomeSeen(storage)).toBeNull();
    expect(markWelcomeSeen('skip', 2, storage)).toBe(true);
    const seen = readWelcomeSeen(storage);
    expect(seen.outcome).toBe('skip');
    expect(seen.step).toBe(2);
    expect(typeof seen.at).toBe('number');
    expect(JSON.parse(storage.getItem(WELCOME_KEY)).outcome).toBe('skip');
  });

  it('сломанное хранилище не роняет страницу и читается как «нельзя запомнить»', () => {
    const storage = memoryStorage({ broken: true });
    expect(readWelcomeSeen(storage)).toBeNull();
    expect(markWelcomeSeen('done', 3, storage)).toBe(false);
    expect(canRemember(storage)).toBe(false);
    expect(canRemember(memoryStorage())).toBe(true);
  });

  it('мусор в хранилище читается как «не видел»', () => {
    const storage = memoryStorage();
    storage.setItem(WELCOME_KEY, '{oops');
    expect(readWelcomeSeen(storage)).toBeNull();
    storage.setItem(WELCOME_KEY, '{"outcome":"skip"}');
    expect(readWelcomeSeen(storage)).toBeNull();
  });

  it('ручной показ только по ?welcome=1', () => {
    expect(isManualRequest('?welcome=1')).toBe(true);
    expect(isManualRequest('?preview_locale=en&welcome=1')).toBe(true);
    expect(isManualRequest('?welcome=0')).toBe(false);
    expect(isManualRequest('')).toBe(false);
    expect(manualStartStep('?welcome=1&welcome_step=3')).toBe(2);
    expect(manualStartStep('?welcome=1&welcome_step=9')).toBe(0);
    expect(manualStartStep('?welcome=1')).toBe(0);
  });

  it('узнаёт поисковых роботов и не путает их с обычными браузерами', () => {
    expect(isCrawlerUa('Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)')).toBe(true);
    expect(isCrawlerUa('Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)')).toBe(true);
    expect(isCrawlerUa('Mozilla/5.0 (compatible; bingbot/2.0)')).toBe(true);
    expect(isCrawlerUa('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1')).toBe(false);
    expect(isCrawlerUa('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 YaBrowser/24.10 Safari/537.36')).toBe(false);
  });

  it('движение: просьба человека выключает всё, слабое устройство оставляет короткие проходы', () => {
    expect(welcomeMotionLevel({ motion: true, lite: false, reason: [] })).toBe('full');
    expect(welcomeMotionLevel({ motion: false, lite: false, reason: ['low-cpu'] })).toBe('calm');
    expect(welcomeMotionLevel({ motion: false, lite: false, reason: ['reduced-motion'] })).toBe('off');
    expect(welcomeMotionLevel({ motion: false, lite: false, reason: ['low-cpu', 'reduced-motion'] })).toBe('off');
    expect(welcomeMotionLevel({ motion: false, lite: true, reason: ['save-data'] })).toBe('off');
    expect(welcomeMotionLevel({ motion: false, lite: true, reason: ['reduced-transparency'] })).toBe('off');
    expect(welcomeMotionLevel(null)).toBe('off');
  });

  it('четыре шага, аккаунт последним; ссылки Telegram ведут на бота и канал проекта', () => {
    expect(WELCOME_STEPS).toEqual(['find', 'fresh', 'telegram', 'account']);
    expect(clampStep(-1)).toBe(0);
    expect(clampStep(99)).toBe(3);
    expect(TELEGRAM_BOT_URL).toMatch(/^https:\/\/t\.me\/ForecastEconomyBot\?start=[a-z_]+$/);
    expect(TELEGRAM_CHANNEL_URL).toBe('https://t.me/forecasteconomy');
  });

  it('шаги по языку: английская версия вместо Telegram показывает сравнение стран', () => {
    expect(welcomeScreens('ru')).toEqual(['find', 'fresh', 'telegram', 'account']);
    expect(welcomeScreens('en')).toEqual(['find', 'fresh', 'compare', 'account']);
    expect(WELCOME_STEPS_EN).not.toContain('telegram');
    expect(WELCOME_STEPS_EN.at(-1)).toBe('account');
  });

  it('вопрос из поля ведёт на главную с открытым поиском; служебные параметры экрана в адрес не попадают', () => {
    expect(searchHref('курс доллара')).toBe('/?q=%D0%BA%D1%83%D1%80%D1%81+%D0%B4%D0%BE%D0%BB%D0%BB%D0%B0%D1%80%D0%B0');
    expect(searchHref('  gdp  ', '?preview_locale=en&welcome=1&welcome_step=2')).toBe('/?preview_locale=en&q=gdp');
    expect(searchHref('x'.repeat(200)).length).toBeLessThan(100);
  });
});
