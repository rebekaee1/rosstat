/**
 * Подпись для плашки «Открываем: …»: явная `data-nav-label`, затем заголовок пункта меню (`.fe-mnav-label`, `[data-nav-title]`,
 * заголовок h1–h6 внутри ссылки), иначе текст ссылки. Круг 8, S6: раньше брался весь `textContent`, и в меню заголовок слипался
 * с описанием («Рейтинг странКто впереди…»), потому что лежат в соседних элементах без пробела. Теперь куски текста соединяются
 * пробелом, а если ссылка состоит из нескольких текстовых блоков и целиком не умещается в подпись, берётся первый (заголовок).
 */
const MAX_LEN = 44;

function clean(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}

function textChunks(node) {
  const chunks = [];
  const walk = (n) => {
    n.childNodes.forEach((child) => {
      if (child.nodeType === 3) {
        const t = clean(child.nodeValue);
        if (t) chunks.push(t);
      } else if (child.nodeType === 1 && !child.matches('svg, [aria-hidden="true"], .sr-only')) {
        walk(child);
      }
    });
  };
  walk(node);
  return chunks;
}

export function navLabelFor(anchor) {
  const explicit = clean(anchor.getAttribute('data-nav-label'));
  let raw = explicit;
  if (!raw) {
    const title = anchor.querySelector('.fe-mnav-label, [data-nav-title], h1, h2, h3, h4, h5, h6');
    raw = clean(title && title.textContent);
  }
  if (!raw) raw = clean(anchor.getAttribute('aria-label'));
  if (!raw) {
    const chunks = textChunks(anchor);
    const joined = chunks.join(' ');
    raw = chunks.length > 1 && joined.length > MAX_LEN ? chunks[0] : joined;
  }
  if (!raw || raw.length > 90) return '';
  return raw.length > MAX_LEN ? `${raw.slice(0, MAX_LEN - 1).trimEnd()}…` : raw;
}
