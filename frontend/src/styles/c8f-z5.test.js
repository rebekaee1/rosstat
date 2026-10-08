// Круг 8, зона Z5 (прогнозы, формы, 404, калькуляторы): страж видимых решений. Рамок и колец нет, диапазона нет,
// поля и согласие различимы светлотой и тенью, разделитель «или» — чёткая линия, а не размытое пятно.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => readFileSync(join(here, name), 'utf8');
const k8 = read('k8-tools.css');
const zb = read('zb-forecasts.css');
const w6f = read('w6f-pages.css');

function block(css, marker) {
  const at = css.indexOf(marker);
  expect(at, `нет блока «${marker}»`).toBeGreaterThan(-1);
  return css.slice(at);
}

describe('круг 8 Z5: формы', () => {
  const z5 = block(k8, 'Круг 8, зона Z5');

  it('поле и согласие — углубление: тёмная внутренняя тень, без рамки и кольца', () => {
    expect(z5).toMatch(/\.fe-auth-card \.fe-input\s*\{[^}]*inset 0 3px 9px rgba\(30, 38, 56, 0\.18\)/);
    expect(z5).toMatch(/input\[type='checkbox'\]\s*\{[^}]*width: 24px/);
    expect(z5).toMatch(/input\[type='checkbox'\]:checked[^{]*\{[^}]*var\(--fe-glass-active\)/);
    expect(z5).not.toMatch(/\bborder\s*:/);
    expect(z5).not.toMatch(/0 0 0 \d+px/);
    expect(z5).not.toMatch(/\boutline\b/);
  });

  it('разделитель «или» — линия 2 px с затуханием, не пятно на 8 px', () => {
    expect(z5).toMatch(/\.fe-k8-seam\s*\{[^}]*height: 2px/);
    expect(z5).not.toMatch(/\.fe-k8-seam\s*\{[^}]*radial-gradient/);
  });

  it('«было / стало»: жёлоб почти невидим, высота не анимируется', () => {
    expect(z5).toMatch(/\.fe-w6g-ba__bar\s*\{\s*transition: none/);
    expect(z5).toMatch(/\.fe-w6g-ba__track\s*\{[^}]*rgba\(30, 58, 110, 0\.05\)/);
  });
});

describe('круг 8 Z5: прогнозы', () => {
  it('нет диапазона и бусины: ни полосы, ни блика на точке', () => {
    expect(zb).not.toMatch(/zb-fc__band|zb-fc__key--range|lower_bound|upper_bound|dot-spark/);
  });

  it('подписи графика — текст с ореолом, значения и даты не анимируются', () => {
    const tag = /\.zb-fc__tag\s*\{[^}]*\}/.exec(zb)[0];
    expect(tag).toMatch(/text-shadow/);
    expect(tag).not.toMatch(/transition|animation|border/);
  });

  it('торец карточки холодный, без бежевого', () => {
    expect(zb).not.toMatch(/233, 205, 142/);
  });
});

describe('круг 8 Z5: 404', () => {
  it('подсказка не бежевая, у глобуса есть подложка до загрузки картинки', () => {
    expect(w6f).not.toMatch(/w6f-nf-chip--strong \{ background: rgba\(173, 138, 72/);
    expect(w6f).toMatch(/\.z2-nf \.fe-nf-globe\s*\{[^}]*radial-gradient/);
  });
});
