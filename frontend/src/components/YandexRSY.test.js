import { describe, expect, it } from 'vitest';
import { isFloorAdShellEmpty, __RSY_TEST } from '../lib/rsyFloorAd';

/** Минимальный DOM-like шелл без jsdom (vitest environment: node). */
function shell({ media = [], slots = [], text = '' } = {}) {
  return {
    querySelector(sel) {
      if (/iframe|img|video|canvas|object|embed|source|yanetag|data-videoname/i.test(sel)) {
        return media[0] || null;
      }
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '.needsclick') return slots;
      if (/iframe|img|video|canvas|object|embed|source|yanetag|data-videoname/i.test(sel)) {
        return media;
      }
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

  it('не пустой при video', () => {
    expect(isFloorAdShellEmpty(shell({ media: [{ tagName: 'VIDEO' }] }))).toBe(false);
  });

  it('не пустой при canvas', () => {
    expect(isFloorAdShellEmpty(shell({ media: [{ tagName: 'CANVAS' }] }))).toBe(false);
  });

  it('не пустой при тексте объявления в needsclick', () => {
    expect(
      isFloorAdShellEmpty(
        shell({ slots: [{ children: [], innerText: 'Купить сталь оптом' }] })
      )
    ).toBe(false);
  });

  it('не пустой при тексте объявления вне needsclick', () => {
    expect(
      isFloorAdShellEmpty(shell({ text: 'Скидка на ипотеку до конца месяца' }))
    ).toBe(false);
  });

  it('игнорирует метку РЕКЛАМА как единственный текст', () => {
    expect(isFloorAdShellEmpty(shell({ text: 'РЕКЛАМА' }))).toBe(true);
  });

  it('игнорирует chrome РЕКЛАМА + Закрыть без креатива', () => {
    expect(isFloorAdShellEmpty(shell({ text: 'РЕКЛАМА Закрыть' }))).toBe(true);
  });

  it('пустой needsclick + текст снаружи = fill (не early-empty по слоту)', () => {
    expect(
      isFloorAdShellEmpty(
        shell({
          slots: [{ children: [], innerText: '' }],
          text: 'Специальное предложение банка',
        })
      )
    ).toBe(false);
  });
});

describe('empty-shell watchdog policy', () => {
  it('timer auto-destroy отключён — снос только через onError', () => {
    expect(__RSY_TEST.AUTO_DESTROY_DISABLED).toBe(true);
  });

  it('EMPTY_CHECK_MS не в опасном окне ~5–8 с (регрессия к kill-live-ads)', () => {
    expect(__RSY_TEST.EMPTY_CHECK_MS).toBeGreaterThan(60_000);
  });
});
