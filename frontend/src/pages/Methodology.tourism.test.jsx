import { describe, expect, it } from 'vitest';
import { translate } from '../i18n/messages';

const KEYS = ['trip', 'arrival', 'guest', 'night'];

describe('Как мы считаем: блок про туризм (правка 42)', () => {
  it('четыре определения и пять источников есть на двух языках', () => {
    for (const locale of ['ru', 'en']) {
      for (const id of KEYS) {
        expect(translate(`kt6_meth_def_${id}_term`, undefined, locale)).not.toBe(`kt6_meth_def_${id}_term`);
        expect(translate(`kt6_meth_def_${id}`, undefined, locale).length).toBeGreaterThan(40);
      }
      for (let n = 1; n <= 5; n += 1) {
        expect(translate(`kt6_meth_src_${n}_name`, undefined, locale)).not.toMatch(/^kt6_/);
        expect(translate(`kt6_meth_src_${n}_desc`, undefined, locale)).not.toMatch(/^kt6_/);
      }
    }
  });

  it('в источниках названы Росстат, пограничная служба, Банк России, ФНС и UN Tourism', () => {
    const names = [1, 2, 3, 4, 5].map((n) => translate(`kt6_meth_src_${n}_name`, undefined, 'ru')).join(' | ');
    expect(names).toMatch(/Росстат/);
    expect(names).toMatch(/Пограничная служба/);
    expect(names).toMatch(/Банк России/);
    expect(names).toMatch(/ФНС/);
    expect(names).toMatch(/UN Tourism/);
  });
});
