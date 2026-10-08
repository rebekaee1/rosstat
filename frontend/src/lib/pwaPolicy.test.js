import { describe, expect, it } from 'vitest';
import {
  AFTER_ACTION_DELAY_MS, DATA_PAGE_DWELL_MS, DAY_MS, MIN_PAGE_DWELL_MS, SECOND_VISIT_MIN_GAP_MS,
  afterDismiss, afterIosAck, detectPlatform, emptyState, eligibleAt, isDataPath, isHiddenPath,
  shouldShowInstallCard, snoozeDaysFor, triggerFor,
} from './pwaPolicy';

const T0 = 1_800_000_000_000;
const base = {
  state: emptyState(), now: T0, platform: 'android', hasNativePrompt: true, flagEnabled: true,
  standalone: false, inIframe: false, pathname: '/russia/indicator/cpi', blocked: false,
  trigger: 'action', pageLoadedAt: T0 - DATA_PAGE_DWELL_MS - 1,
};

describe('интервалы «Не сейчас»', () => {
  it('3 → 7 → 14 → 30, дальше всегда 30 без верхнего предела', () => {
    expect([1, 2, 3, 4, 5, 6, 50].map(snoozeDaysFor)).toEqual([3, 7, 14, 30, 30, 30, 30]);
    expect(snoozeDaysFor(0)).toBe(3);
    expect(snoozeDaysFor(undefined)).toBe(3);
  });

  it('afterDismiss наращивает счётчик и ставит следующий показ', () => {
    let s = emptyState();
    const seen = [];
    let now = T0;
    for (let i = 0; i < 6; i += 1) {
      s = afterDismiss(s, now);
      seen.push((s.nextAt - now) / DAY_MS);
      now = s.nextAt; // следующий отказ — ровно в момент следующего показа
    }
    expect(seen).toEqual([3, 7, 14, 30, 30, 30]);
    expect(s.dismissCount).toBe(6);
  });

  it('iOS «Понятно» — тихая пауза 30 дней, счётчик отказов не растёт', () => {
    const s = afterIosAck({ ...emptyState(), dismissCount: 1 }, T0);
    expect(s.nextAt - T0).toBe(30 * DAY_MS);
    expect(s.dismissCount).toBe(1);
  });
});

describe('платформа по UA', () => {
  const ua = {
    iosSafari: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    iosChrome: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0 Mobile/15E148 Safari/604.1',
    iosTelegram: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Telegram-iOS',
    ipadOs: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    android: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36',
    yandexAndroid: 'Mozilla/5.0 (Linux; arm_64; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 YaBrowser/24.6 Mobile Safari/537.36',
    mac: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
  };
  it('распознаёт Safari iPhone/iPad, Android и десктоп', () => {
    expect(detectPlatform({ userAgent: ua.iosSafari })).toBe('ios-safari');
    expect(detectPlatform({ userAgent: ua.ipadOs, maxTouchPoints: 5 })).toBe('ios-safari');
    expect(detectPlatform({ userAgent: ua.android })).toBe('android');
    expect(detectPlatform({ userAgent: ua.yandexAndroid })).toBe('android');
    expect(detectPlatform({ userAgent: ua.mac, maxTouchPoints: 0 })).toBe('desktop');
    expect(detectPlatform({})).toBe('desktop');
  });
  it('iOS-браузеры без нужного меню и встроенные просмотрщики — не Safari', () => {
    expect(detectPlatform({ userAgent: ua.iosChrome })).toBe('ios-other');
    expect(detectPlatform({ userAgent: ua.iosTelegram })).toBe('ios-other');
  });
});

describe('что открывает дверь', () => {
  it('на первом визите без действия — ничего', () => {
    expect(triggerFor({ state: { ...emptyState(), visits: 1, firstSeen: T0 }, now: T0, sessionUsefulAt: 0 })).toBeNull();
  });
  it('второй заход — только после паузы с первого, а не вторая вкладка сразу', () => {
    const s = { ...emptyState(), visits: 2, firstSeen: T0 };
    expect(triggerFor({ state: s, now: T0 + SECOND_VISIT_MIN_GAP_MS - 1, sessionUsefulAt: 0 })).toBeNull();
    expect(triggerFor({ state: s, now: T0 + SECOND_VISIT_MIN_GAP_MS, sessionUsefulAt: 0 })).toBe('visit');
  });
  it('полезное действие открывает дверь даже на первом визите', () => {
    expect(triggerFor({ state: emptyState(), now: T0, sessionUsefulAt: T0 })).toBe('action');
    expect(triggerFor({ state: { ...emptyState(), usefulAt: T0 - 1 }, now: T0, sessionUsefulAt: 0 })).toBe('action');
  });
});

describe('когда можно показать', () => {
  it('не сразу: после загрузки страницы и после полезного действия есть задержки', () => {
    const state = { ...emptyState(), usefulAt: T0 };
    expect(eligibleAt({ state, now: T0, pageLoadedAt: T0 - 60_000, trigger: 'action' })).toBe(T0 + AFTER_ACTION_DELAY_MS);
    expect(eligibleAt({ state: emptyState(), now: T0, pageLoadedAt: T0, trigger: 'visit' })).toBe(T0 + MIN_PAGE_DWELL_MS);
    expect(eligibleAt({ state: emptyState(), now: T0, pageLoadedAt: T0, trigger: null })).toBeNull();
  });

  it('круг 9, S2: на странице с данными окно не раньше чем через 30 с, на главной и в текстовых страницах через 15 с', () => {
    const args = { state: emptyState(), now: T0, pageLoadedAt: T0, trigger: 'visit' };
    expect(eligibleAt({ ...args, pathname: '/world/rating/gdp-usd' })).toBe(T0 + DATA_PAGE_DWELL_MS);
    expect(eligibleAt({ ...args, pathname: '/' })).toBe(T0 + MIN_PAGE_DWELL_MS);
    expect(eligibleAt({ ...args, pathname: '/about' })).toBe(T0 + MIN_PAGE_DWELL_MS);
    expect(isDataPath('/calculator/mortgage')).toBe(true);
    expect(isDataPath('/privacy')).toBe(false);
    expect(shouldShowInstallCard({ ...base, pageLoadedAt: T0 - MIN_PAGE_DWELL_MS - 1 })).toBe(false);
  });

  it('показывает Android с системным окном и iPhone Safari', () => {
    expect(shouldShowInstallCard(base)).toBe(true);
    expect(shouldShowInstallCard({ ...base, platform: 'ios-safari', hasNativePrompt: false })).toBe(true);
  });

  it.each([
    ['флаг выключен', { flagEnabled: false }],
    ['запущено как приложение', { standalone: true }],
    ['внутри iframe', { inIframe: true }],
    ['закрыто другим окном', { blocked: true }],
    ['десктоп', { platform: 'desktop' }],
    ['iOS не Safari', { platform: 'ios-other' }],
    ['Android без beforeinstallprompt', { hasNativePrompt: false }],
    ['нет триггера', { trigger: null }],
    ['рано после загрузки', { pageLoadedAt: T0 - 1000 }],
    ['установлено', { state: { ...emptyState(), installed: true, usefulAt: T0 - 99999 } }],
    ['отложено', { state: { ...emptyState(), nextAt: T0 + 1, usefulAt: T0 - 99999 } }],
  ])('не показывает: %s', (_name, patch) => {
    expect(shouldShowInstallCard({ ...base, ...patch })).toBe(false);
  });

  it('установившим не показывает никогда, сколько бы ни прошло времени', () => {
    const state = { ...emptyState(), installed: true, usefulAt: 1, visits: 99, firstSeen: 1 };
    for (const years of [0, 1, 5]) {
      expect(shouldShowInstallCard({ ...base, state, now: T0 + years * 365 * DAY_MS, pageLoadedAt: 0 })).toBe(false);
    }
  });

  it('после «Не сейчас» возвращается ровно в срок', () => {
    const state = afterDismiss({ ...emptyState(), usefulAt: T0 - 1 }, T0);
    const due = T0 + 3 * DAY_MS;
    expect(shouldShowInstallCard({ ...base, state, now: due - 1, pageLoadedAt: due - 99999 })).toBe(false);
    expect(shouldShowInstallCard({ ...base, state, now: due, pageLoadedAt: due - 99999 })).toBe(true);
  });
});

describe('скрытые маршруты', () => {
  it('виджеты, админка, вход, регистрация, кабинет', () => {
    for (const p of ['/embed/chart/cpi', '/admin/bi', '/login', '/register', '/account']) expect(isHiddenPath(p)).toBe(true);
    for (const p of ['/', '/russia', '/world/rating', '/administrator-x', '/embedded']) expect(isHiddenPath(p)).toBe(false);
  });
});
