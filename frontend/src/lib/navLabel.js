/** Подпись для плашки «Открываем: …»: явная `data-nav-label`, иначе текст ссылки (коротко, без переносов). */
export function navLabelFor(anchor) {
  const explicit = anchor.getAttribute('data-nav-label');
  const raw = (explicit || anchor.getAttribute('aria-label') || anchor.textContent || '').replace(/\s+/g, ' ').trim();
  if (!raw || raw.length > 90) return '';
  return raw.length > 44 ? `${raw.slice(0, 43).trimEnd()}…` : raw;
}
