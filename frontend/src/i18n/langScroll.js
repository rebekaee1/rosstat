/**
 * Смена языка = переход на другой адрес (хост или ?preview_locale), страница перезагружается и встаёт вверх.
 * Чтобы не терять место, перед переходом кладём позицию в короткоживущую cookie (она общая для ru. и apex),
 * а новая страница возвращает прокрутку, как только у неё хватает высоты.
 */
const COOKIE = 'fe_lang_scroll';
const MAX_AGE_S = 30;
const FRESH_MS = 20_000;
const MIN_Y = 80;

function cookieAttrs() {
  const host = String(window.location.hostname || '').toLowerCase();
  const domain = /(^|\.)forecasteconomy\.com$/.test(host) ? '; Domain=.forecasteconomy.com' : '';
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  return `; Path=/; SameSite=Lax${domain}${secure}`;
}

/** Вызывается прямо перед сменой языка. Возвращает true, если позиция сохранена. */
export function rememberScrollForLanguageSwitch() {
  try {
    const y = Math.round(window.scrollY || 0);
    if (y < MIN_Y) return false;
    const value = `${encodeURIComponent(window.location.pathname)}|${y}|${Date.now()}`;
    document.cookie = `${COOKIE}=${value}; Max-Age=${MAX_AGE_S}${cookieAttrs()}`;
    return true;
  } catch {
    return false;
  }
}

/** Читает и сразу стирает cookie. Возвращает целевую позицию или null. */
export function takeRememberedScroll() {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]*)`));
    if (!match) return null;
    document.cookie = `${COOKIE}=; Max-Age=0${cookieAttrs()}`;
    const [path, rawY, rawTs] = match[1].split('|');
    const y = Number(rawY);
    const ts = Number(rawTs);
    if (!Number.isFinite(y) || !Number.isFinite(ts) || y < MIN_Y) return null;
    if (Date.now() - ts > FRESH_MS) return null;
    if (decodeURIComponent(path || '') !== window.location.pathname) return null;
    if (window.location.hash) return null;
    return y;
  } catch {
    return null;
  }
}

/**
 * После загрузки новой страницы: ждём, пока у документа появится высота (данные приходят позже скелета),
 * и возвращаем прокрутку. Любое касание, колесо или клавиша отменяют возврат — человек уже сам ведёт страницу.
 */
export function restoreScrollAfterLanguageSwitch() {
  const y = takeRememberedScroll();
  if (y == null) return () => {};
  let tries = 0;
  let timer = 0;
  let cancelled = false;
  const stop = () => {
    cancelled = true;
    window.clearTimeout(timer);
    window.removeEventListener('wheel', stop);
    window.removeEventListener('touchstart', stop);
    window.removeEventListener('keydown', stop);
  };
  window.addEventListener('wheel', stop, { passive: true, once: true });
  window.addEventListener('touchstart', stop, { passive: true, once: true });
  window.addEventListener('keydown', stop, { once: true });
  const tick = () => {
    if (cancelled) return;
    const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    if (max >= y - 4 || tries >= 40) {
      window.scrollTo({ top: Math.min(y, max), left: 0, behavior: 'instant' });
      stop();
      return;
    }
    tries += 1;
    timer = window.setTimeout(tick, 150);
  };
  tick();
  return stop;
}
