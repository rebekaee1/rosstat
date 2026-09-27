// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { mountJsonLd } from './jsonLd';

afterEach(() => {
  document.head.querySelectorAll('script[type="application/ld+json"]').forEach((node) => node.remove());
  document.head.querySelectorAll('link[rel="canonical"]').forEach((node) => node.remove());
});

function setCanonical(href) {
  const link = document.createElement('link');
  link.rel = 'canonical';
  link.href = href;
  document.head.appendChild(link);
  return link;
}

describe('mountJsonLd', () => {
  it('updates one matching SSR entity and removes it on route exit', () => {
    const ssr = document.createElement('script');
    ssr.type = 'application/ld+json';
    ssr.textContent = JSON.stringify({ '@type': 'BreadcrumbList', itemListElement: [] });
    document.head.appendChild(ssr);
    const remove = mountJsonLd({ '@type': 'BreadcrumbList', itemListElement: [{ name: 'Russia' }] });
    expect(document.head.querySelectorAll('script[type="application/ld+json"]')).toHaveLength(1);
    expect(JSON.parse(ssr.textContent).itemListElement[0].name).toBe('Russia');
    remove();
    expect(ssr.isConnected).toBe(false);
  });

  it('ignores malformed unrelated metadata', () => {
    const broken = document.createElement('script');
    broken.type = 'application/ld+json';
    broken.textContent = '{';
    document.head.appendChild(broken);
    const remove = mountJsonLd({ '@type': 'FAQPage', mainEntity: [] });
    expect(document.head.querySelectorAll('script[type="application/ld+json"]')).toHaveLength(2);
    remove();
    expect(broken.isConnected).toBe(true);
  });

  it('preserves rich server Dataset fields through hydration and effect reruns', () => {
    const url = 'https://forecasteconomy.com/germany/indicator/gdp';
    setCanonical(url);
    const ssr = document.createElement('script');
    ssr.type = 'application/ld+json';
    ssr.textContent = JSON.stringify({
      '@type': 'Dataset', url, name: 'GDP',
      temporalCoverage: '1990-01-01/2025-01-01',
      spatialCoverage: 'Germany', image: 'https://forecasteconomy.com/og/germany/gdp.png',
    });
    document.head.appendChild(ssr);

    const removeFirst = mountJsonLd({ '@type': 'Dataset', name: 'GDP', description: 'Updated' });
    expect(document.head.querySelectorAll('script[type="application/ld+json"]')).toHaveLength(1);
    expect(JSON.parse(ssr.textContent)).toMatchObject({
      url, description: 'Updated', temporalCoverage: '1990-01-01/2025-01-01',
      spatialCoverage: 'Germany', image: 'https://forecasteconomy.com/og/germany/gdp.png',
    });
    removeFirst();

    const removeSecond = mountJsonLd({ '@type': 'Dataset', name: 'GDP', description: 'Refreshed' });
    expect(JSON.parse(document.head.querySelector('script[type="application/ld+json"]').textContent))
      .toMatchObject({ url, description: 'Refreshed', temporalCoverage: '1990-01-01/2025-01-01' });
    removeSecond();
  });

  it('does not copy Dataset metadata from a previous page', () => {
    const oldUrl = 'https://forecasteconomy.com/germany/indicator/gdp';
    const newUrl = 'https://forecasteconomy.com/france/indicator/gdp';
    const canonical = setCanonical(oldUrl);
    const old = document.createElement('script');
    old.type = 'application/ld+json';
    old.textContent = JSON.stringify({ '@type': 'Dataset', url: oldUrl, image: '/og/germany/gdp.png' });
    document.head.appendChild(old);
    mountJsonLd({ '@type': 'Dataset', name: 'German GDP' })();

    // A stale SSR block can survive client navigation; the new page must not adopt it.
    canonical.href = newUrl;
    document.head.appendChild(old);
    const removeNew = mountJsonLd({ '@type': 'Dataset', name: 'French GDP' });
    const datasets = document.head.querySelectorAll('script[type="application/ld+json"]');
    expect(datasets).toHaveLength(1);
    expect(JSON.parse(datasets[0].textContent)).toEqual({ '@type': 'Dataset', name: 'French GDP' });
    expect(old.isConnected).toBe(false);
    removeNew();
  });
});
