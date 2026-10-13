import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Круг 13, зона R-CAB: стражи правил, найденных при проходе по кабинету вошедшим (читают исходники, как остальные styles/*.test.js).
const here = dirname(fileURLToPath(import.meta.url));
const strip = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '');
const css = (name) => strip(readFileSync(join(here, name), 'utf8'));

describe('вид кабинета (круг 13)', () => {
  it('звезда в ряду кнопок героя страны стоит рядом с ними, а не у правого края', () => {
    expect(css('z4-indicator.css')).toMatch(/\.z5-hero__actions > \.fe-cabinet-actions[^{]*\{\s*margin-left:\s*0;/);
  });

  it('кнопка слежения в карточке события не уезжает вправо', () => {
    expect(css('z4-indicator.css')).toMatch(/\.fe-cabinet-actions--flush[^{]*\{\s*margin-left:\s*0;/);
  });

  it('включённое состояние звезды и колокольчика не пропадает под курсором (вес выше общего чипа)', () => {
    expect(css('c11b-cabinet.css')).toMatch(/\.fe-chip\.c11b-act\.c11b-on:hover:not\(:disabled\)/);
  });

  it('меню «Скачать» плотное: сквозь него не читается шапка таблицы', () => {
    const menu = css('regions-w4.css').match(/\.fe-dl__menu \{[^}]*\}/)?.[0] || '';
    expect(menu).toMatch(/background:\s*var\(--color-surface\)/);
    expect(menu).not.toMatch(/glass/);
  });

  it('пояснение над настройками отделено от первого поля', () => {
    expect(css('c11b-cabinet.css')).toMatch(/\.c11b-prefs > \.c11b-hint:first-child\s*\{\s*margin:\s*0 0 16px;/);
  });
});
