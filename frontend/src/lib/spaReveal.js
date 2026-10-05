/**
 * Handoff SSR → SPA: клип SEO-тела (html.fe-js) только после первого commit.
 * Inline-скрипт SSR объявляет window.__feRevealSpa и НЕ вызывает его.
 */

export function revealSpaNow() {
  if (typeof window !== 'undefined' && typeof window.__feRevealSpa === 'function') {
    window.__feRevealSpa();
    return;
  }
  if (typeof document !== 'undefined') {
    // Оболочка без SSR (index.html): заставка fe-boot снимается здесь же.
    document.documentElement.classList.remove('fe-boot');
    document.documentElement.classList.add('fe-js');
  }
}

// Не дольше запасного таймера заставки (12 с в SSR и оболочке): после него заставка снимается в любом случае.
const STYLES_MAX_WAIT_MS = 10000;

/**
 * Заставку нельзя снимать, пока полный CSS не загрузился: на медленной сети приложение монтируется по таймеру
 * (mountWhenCssReady, 2,5 с) без стилей, и человек вместо заставки видел бы пустой серый экран.
 * Стили ещё едут: ждём их загрузки (или ошибки, или предела) и только потом открываем приложение.
 */
function revealWhenStylesReady() {
  if (typeof document === 'undefined') { revealSpaNow(); return; }
  const pending = Array.from(document.querySelectorAll('link[data-fe-css]'))
    .filter((link) => !(link.sheet || link.media === 'all'));
  if (!pending.length) { revealSpaNow(); return; }
  let remaining = pending.length;
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    revealSpaNow();
  };
  for (const link of pending) {
    let settled = false;
    const settle = () => {
      if (settled) return;
      settled = true;
      remaining -= 1;
      if (remaining === 0) finish();
    };
    link.addEventListener('load', settle, { once: true });
    link.addEventListener('error', settle, { once: true });
    if (link.sheet || link.media === 'all') settle();
  }
  setTimeout(finish, STYLES_MAX_WAIT_MS);
}

/** После createRoot commit: один rAF, чтобы кадр SPA успел попасть в пайплайн; заставка ждёт стили. */
export function scheduleSpaReveal() {
  if (typeof requestAnimationFrame !== 'function') {
    revealWhenStylesReady();
    return null;
  }
  return requestAnimationFrame(revealWhenStylesReady);
}
