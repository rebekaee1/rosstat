import { describe, expect, it } from 'vitest';
import { isFloorAdShellEmpty } from '../components/YandexRSY';

/** Минимальный DOM-like шелл без jsdom (vitest environment: node). */
function shell({ media = [], slots = [], text = '' } = {}) {
  return {
    querySelector(sel) {
      if (/iframe|img|video|canvas|object|embed/.test(sel)) return media[0] || null;
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '.needsclick') return slots;
      return [];
    },
    innerText: text,
  };
}

describe('isFloorAdShellEmpty', () => {
  it('считает пустым шелл без media и с пустым needsclick', () => {
    expect(
      isFloorAdShellEmpty(shell({ slots: [{ children: [], innerText: '' }] }))
    ).toBe(true);
  });

  it('не пустой при живом img', () => {
    expect(
      isFloorAdShellEmpty(
        shell({ media: [{ tagName: 'IMG', naturalWidth: 120, complete: true }] })
      )
    ).toBe(false);
  });

  it('пустой при битом img и пустом слоте', () => {
    expect(
      isFloorAdShellEmpty(
        shell({
          media: [{ tagName: 'IMG', naturalWidth: 0, complete: true }],
          slots: [{ children: [], innerText: '' }],
        })
      )
    ).toBe(true);
  });

  it('не пустой при iframe', () => {
    expect(isFloorAdShellEmpty(shell({ media: [{ tagName: 'IFRAME' }] }))).toBe(false);
  });

  it('не пустой при тексте объявления в needsclick', () => {
    expect(
      isFloorAdShellEmpty(
        shell({ slots: [{ children: [], innerText: 'Купить сталь оптом' }] })
      )
    ).toBe(false);
  });

  it('игнорирует метку РЕКЛАМА как единственный текст', () => {
    expect(isFloorAdShellEmpty(shell({ text: 'РЕКЛАМА' }))).toBe(true);
  });
});
