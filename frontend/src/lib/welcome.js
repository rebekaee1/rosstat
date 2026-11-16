/**
 * Приветственный экран для новых посетителей (16.11.2026): кому и когда его показывать.
 *
 * Здесь только правила и память браузера, без React: их проверяет `welcome.test.js`.
 * Сам экран — `components/welcome/WelcomeScreen.jsx` (отдельный чанк), ворота — `components/welcome/WelcomeGate.jsx`.
 *
 * Правила (почему так — docs/design-system.md, раздел «Приветственный экран»):
 *  - флаг сервера `welcome_enabled` (GET /api/v1/pwa/config, по умолчанию false) обязателен для всего, включая ручной показ;
 *  - сам экран открывается ТОЛЬКО на главной: человек, который пришёл из поиска за одной цифрой, получает цифру, а не заставку
 *    (и поисковик не видит полноэкранного окна поверх ответа);
 *  - только новому гостю: не вошедшему, в первые `NEW_VISITOR_MAX_VISITS` заходов, один раз (исход записан в `localStorage`);
 *  - не роботам, не автоматике, не в установленном приложении, не во встроенных страницах;
 *  - если память браузера недоступна (частное окно с запретом), экран не открывается: иначе он возвращался бы на каждом заходе;
 *  - вручную: пункт «Знакомство с сайтом» в подвале и адрес `?welcome=1` (нужен для проверки и для возвращения к экрану).
 */
export const WELCOME_KEY = 'fe:welcome:v1';
export const WELCOME_OPEN_EVENT = 'fe:welcome-open';
export const WELCOME_QUERY = 'welcome';
/** Сколько первых заходов человек считается новым (счёт заходов ведёт lib/pwa.js, ключ `fe:pwa:v1`). */
export const NEW_VISITOR_MAX_VISITS = 3;
/** Пауза перед появлением: главная успевает нарисовать первый экран, заставка не мигает поверх пустой страницы. */
export const WELCOME_OPEN_DELAY_MS = 700;

export const WELCOME_STEPS = Object.freeze(['find', 'fresh', 'telegram', 'account']);

export const TELEGRAM_BOT_URL = 'https://t.me/ForecastEconomyBot?start=site_welcome';
export const TELEGRAM_CHANNEL_URL = 'https://t.me/forecasteconomy';

const CRAWLER_RE = /bot\b|crawl|spider|slurp|bingpreview|facebookexternalhit|lighthouse|pagespeed|headless|yandex(?!browser)|googleother|google-inspectiontool|petalbot|duckduck|baiduspider|applebot|ahrefs|semrush|mj12/i;

export function isCrawlerUa(ua) {
  return CRAWLER_RE.test(String(ua || ''));
}

/** Исход прошлого показа или null. Любая ошибка хранилища читается как «не видел». */
export function readWelcomeSeen(storage = safeStorage()) {
  try {
    const raw = JSON.parse(storage?.getItem(WELCOME_KEY) || 'null');
    return raw && typeof raw.at === 'number' ? raw : null;
  } catch {
    return null;
  }
}

/** Записывает исход: 'done' (дошёл до конца), 'skip', 'register', 'bot', 'channel'. Возвращает, удалось ли записать. */
export function markWelcomeSeen(outcome, step = 0, storage = safeStorage()) {
  try {
    storage.setItem(WELCOME_KEY, JSON.stringify({ at: Date.now(), outcome: String(outcome || 'skip'), step: Number(step) || 0 }));
    return true;
  } catch {
    return false;
  }
}

/** Можно ли будет запомнить, что экран уже показан. */
export function canRemember(storage = safeStorage()) {
  try {
    const probe = `${WELCOME_KEY}:probe`;
    storage.setItem(probe, '1');
    storage.removeItem(probe);
    return true;
  } catch {
    return false;
  }
}

function safeStorage() {
  try { return typeof window !== 'undefined' ? window.localStorage : null; } catch { return null; }
}

/** Адрес просит показать экран вручную: `?welcome=1`. */
export function isManualRequest(search) {
  try {
    return new URLSearchParams(search || '').get(WELCOME_QUERY) === '1';
  } catch {
    return false;
  }
}

/** Шаг, с которого открыть экран вручную: `?welcome=1&welcome_step=3` (нужно при проверке на устройствах). По умолчанию первый. */
export function manualStartStep(search) {
  try {
    const n = Number(new URLSearchParams(search || '').get('welcome_step'));
    return Number.isInteger(n) && n >= 1 && n <= WELCOME_STEPS.length ? n - 1 : 0;
  } catch {
    return 0;
  }
}

/**
 * Открывать ли экран самому. Чистая функция: все обстоятельства приходят аргументами.
 * @returns {boolean}
 */
export function shouldAutoOpenWelcome({
  enabled, pathname, authLoading, isAuthed, seen, visits, canStore, automation, crawler, standalone, embedded,
}) {
  if (enabled !== true) return false;
  if (pathname !== '/') return false;
  if (authLoading || isAuthed) return false;
  if (seen) return false;
  if (!canStore) return false;
  if (automation || crawler || standalone || embedded) return false;
  return Number(visits || 0) <= NEW_VISITOR_MAX_VISITS;
}

/**
 * Насколько экрану можно двигаться:
 *  'off'  — человек просил меньше движения или прозрачности, либо экономит трафик: всё стоит в итоговом виде;
 *  'calm' — слабое устройство (мало ядер): короткие проходы остаются, фонового плавания нет;
 *  'full' — всё.
 * `mode` — результат `readSceneMode()` из lib/sceneBudget.js.
 */
export function welcomeMotionLevel(mode) {
  if (!mode) return 'off';
  const reason = Array.isArray(mode.reason) ? mode.reason : [];
  if (reason.some((r) => r === 'reduced-motion' || r === 'reduced-transparency' || r === 'save-data' || r === 'no-window')) return 'off';
  if (reason.includes('low-cpu')) return 'calm';
  return 'full';
}

/** Следующий шаг в пределах списка. */
export function clampStep(index, total = WELCOME_STEPS.length) {
  return Math.max(0, Math.min(total - 1, Number(index) || 0));
}
