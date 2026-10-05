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

/** После createRoot commit: один rAF, чтобы кадр SPA успел попасть в пайплайн. */
export function scheduleSpaReveal() {
  if (typeof requestAnimationFrame !== 'function') {
    revealSpaNow();
    return null;
  }
  return requestAnimationFrame(revealSpaNow);
}
