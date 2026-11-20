// Круг наблюдателей «Туризм», зона z4 (оболочка): стражи на CSS и оболочку index.html.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const shell = readFileSync(new URL('./shell.css', import.meta.url), 'utf8');
const indexHtml = readFileSync(new URL('../../index.html', import.meta.url), 'utf8');
const notFoundHtml = readFileSync(new URL('../../public/404.html', import.meta.url), 'utf8');

describe('z4: оболочка', () => {
  it('правка 44: «К основному содержанию» невидима и не нажимается без фокуса с клавиатуры', () => {
    expect(shell).toMatch(/\.fe-skip-link:not\(:focus-visible\),\s*html\[data-fe-pointer\] \.fe-skip-link\s*\{\s*opacity:\s*0;\s*pointer-events:\s*none/);
  });

  it('правка 32: «RU» в шапке над тёмным подвалом светлый', () => {
    expect(shell).toMatch(/nav\.fe-navbar\[data-tone='dark'\] \[aria-haspopup='menu'\] > \.fe-locale-flag\s*\{[^}]*color:\s*#F2F5FA/);
  });

  it('правка 36: каталог категорий в подвале телефона — закрытый <details>, стрелка анимируется только transform', () => {
    expect(shell).toMatch(/\.fe-foot-fold\[open\] \.fe-foot-fold__chevron\s*\{\s*transform:\s*rotate\(180deg\)/);
    expect(shell).toMatch(/\.fe-foot-fold__chevron\s*\{[^}]*transition:\s*transform/);
  });

  it('правка 16: заставка в оболочке не ставится при возврате назад и после смены языка', () => {
    expect(indexHtml).toMatch(/nav\.type==="back_forward"\)return/);
    expect(indexHtml).toMatch(/fe_lang_switch=\(\\d\+\)/);
    expect(indexHtml.indexOf('fe_lang_switch')).toBeLessThan(indexHtml.indexOf('h.classList.add("fe-boot")'));
  });

  it('правка 51: язык страницы выставляется в оболочке и на 404 с учётом выбранного языка (cookie fe_locale_pref)', () => {
    expect(indexHtml).toMatch(/h\.lang=en0\?"en":"ru"/);
    expect(indexHtml).toContain('fe_locale_pref');
    expect(notFoundHtml).toContain('fe_locale_pref');
  });
});
