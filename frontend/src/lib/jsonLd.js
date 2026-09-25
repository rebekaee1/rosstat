/** Подменяет уже лежащий в head JSON-LD того же @type или добавляет один script.

SSR отдаёт BreadcrumbList и FAQPage в первом HTML. Второй script того же типа
после гидратации — дубль. При уходе со страницы узел снимается, чтобы старая
тропа не оставалась на следующем маршруте.
*/
export function mountJsonLd(data) {
  if (!data || typeof document === 'undefined') return () => {};
  const type = data['@type'];
  let script = null;
  if (type) {
    for (const node of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const parsed = JSON.parse(node.textContent || '');
        if (parsed && parsed['@type'] === type) {
          script = node;
          break;
        }
      } catch {
        /* соседний блок может быть не-JSON */
      }
    }
  }
  if (!script) {
    script = document.createElement('script');
    script.type = 'application/ld+json';
    document.head.appendChild(script);
  }
  script.textContent = JSON.stringify(data);
  return () => {
    script.remove();
  };
}
