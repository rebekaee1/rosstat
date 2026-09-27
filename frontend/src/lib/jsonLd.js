/** Reuse a matching SSR JSON-LD block on hydration to avoid duplicate entities. */
export function mountJsonLd(data) {
  if (!data || typeof document === 'undefined') return () => {};
  let script;
  for (const candidate of document.head.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      if (JSON.parse(candidate.textContent || '')?.['@type'] === data['@type']) {
        script = candidate;
        break;
      }
    } catch {
      // A malformed unrelated script must not stop the page's own JSON-LD.
    }
  }
  if (!script) {
    script = document.createElement('script');
    script.type = 'application/ld+json';
    document.head.appendChild(script);
  }
  script.textContent = JSON.stringify(data);
  return () => script.remove();
}
