// Keep the rich server Dataset through effect reruns, but never across pages.
let datasetSnapshot = null;

function normalizedUrl(value, base) {
  if (!value) return null;
  try {
    const url = new URL(value, base);
    url.hash = '';
    return url.href;
  } catch {
    return null;
  }
}

function currentPageUrl() {
  const canonical = document.head.querySelector('link[rel="canonical"]')?.href;
  return normalizedUrl(canonical || document.location.href, document.location.href);
}

/** Reuse a matching SSR JSON-LD block on hydration to avoid duplicate entities. */
export function mountJsonLd(data) {
  if (!data || typeof document === 'undefined') return () => {};
  const isDataset = data['@type'] === 'Dataset';
  const pageUrl = isDataset ? normalizedUrl(data.url, currentPageUrl()) || currentPageUrl() : null;
  if (isDataset && datasetSnapshot?.pageUrl !== pageUrl) datasetSnapshot = null;
  let script;
  let serverData;
  for (const candidate of document.head.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const parsed = JSON.parse(candidate.textContent || '');
      if (parsed?.['@type'] !== data['@type']) continue;
      if (isDataset && normalizedUrl(parsed.url, pageUrl) !== pageUrl) {
        // An SSR Dataset left by a previous SPA route describes another page.
        candidate.remove();
        continue;
      }
      if (!script) {
        script = candidate;
        serverData = parsed;
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
  if (isDataset && serverData) datasetSnapshot = { pageUrl, data: serverData };
  script.textContent = JSON.stringify(isDataset
    ? { ...(datasetSnapshot?.data || {}), ...data }
    : data);
  return () => script.remove();
}
