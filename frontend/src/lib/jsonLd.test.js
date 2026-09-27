// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { mountJsonLd } from './jsonLd';

afterEach(() => {
  document.head.querySelectorAll('script[type="application/ld+json"]').forEach((node) => node.remove());
});

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
});
