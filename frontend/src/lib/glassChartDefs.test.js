/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { GLASS_DEFS_ID, ensureGlassDefs, glassDefsMarkup } from './glassChartDefs';

afterEach(() => { document.getElementById(GLASS_DEFS_ID)?.remove(); });

describe('glassChartDefs', () => {
  it('создаёт один скрытый SVG с градиентами ленты, сапфира и заливки', () => {
    expect(ensureGlassDefs()).toBe(true);
    expect(ensureGlassDefs()).toBe(true);
    expect(document.querySelectorAll(`#${GLASS_DEFS_ID}`)).toHaveLength(1);
    const svg = document.getElementById(GLASS_DEFS_ID);
    for (const id of ['fe-glass-ribbon', 'fe-glass-sapphire', 'fe-glass-area']) {
      expect(svg.querySelector(`[id="${id}"]`)).not.toBeNull();
    }
    // display:none ломает градиенты: скрываем нулевым размером.
    expect(svg.style.display).toBe('');
    expect(svg.getAttribute('width')).toBe('0');
  });

  it('разметка берёт цвета из темы: линия и заливка одного цвета, без светлого-тёмного градиента', () => {
    const markup = glassDefsMarkup();
    expect(markup).toContain('#2C4A8A');
    expect(markup).not.toContain('#9DB6DD');
    expect(markup).not.toContain('#1E3A6E');
  });
});
