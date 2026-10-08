import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (...parts) => readFileSync(resolve(import.meta.dirname, ...parts), 'utf8');
const css = read('..', 'components', 'PlanetView.css');
const hero = read('planet-hero.css');

describe('карта по умолчанию: раскладка окна сцены', () => {
  it('карта стоит в окне с собственными пропорциями: высоту задаёт ширина, пустых полос сверху и снизу нет', () => {
    // Окно карты повторяет viewBox 960 × 424 (Антарктида не рисуется); число сверено с WorldMap (тест WorldMap.component.test.jsx).
    expect(css).toMatch(/\.planet-map-plate\s*\{[^}]*aspect-ratio:\s*960 \/ 424/);
    expect(css).toMatch(/\.planet-stage--map\s*\{[^}]*height:\s*auto/);
    expect(css).toMatch(/\.planet-map-svg\s*\{[^}]*position:\s*absolute;\s*inset:\s*0/);
    // Шар по-прежнему живёт в окне высоты --planet-scene-height.
    expect(css).toMatch(/\.planet-stage\s*\{[^}]*height:\s*var\(--planet-scene-height\)/);
  });

  it('кнопки масштаба и действия стоят одной строкой под картой, карточка страны ниже и не закрывает карту', () => {
    expect(css).toMatch(/\.planet-map-tools\s*\{[^}]*display:\s*flex/);
    expect(css).toMatch(/\.planet-map-tools \.planet-camera-controls\s*\{[^}]*position:\s*static/);
    expect(css).toMatch(/\.planet-shell--map \.planet-stage-bottom\s*\{[^}]*position:\s*static/);
  });

  it('колонка списка на карте по высоте левой колонки, а не круглого шара', () => {
    expect(css).toMatch(/\.planet-shell--map \.planet-info\s*\{[^}]*contain:\s*size/);
  });

  it('подложка карты не голая и без рамок: океан со светом сверху, тень-блик вместо линии', () => {
    const block = css.match(/\.planet-map-stage\s*\{[^}]*\}/)[0];
    expect(block).toMatch(/radial-gradient/);
    expect(block).toMatch(/var\(--planet-ocean\)/);
    expect(block).not.toMatch(/(^|[\s;{])border(-(top|right|bottom|left|width|color|style))?\s*:|outline/);
  });

  it('переключатель «Карта | Шар» оформлен как сегмент по образцу переключателя слоёв', () => {
    expect(css).toMatch(/\.planet-layer-switch,\s*\.planet-view-switch\s*\{/);
    expect(css).toMatch(/\.planet-view-switch button\[aria-pressed="true"\]/);
    expect(css).toMatch(/\.planet-viewbar\s*\{[^}]*grid-column:\s*2;[^}]*grid-row:\s*1/);
    expect(css).toMatch(/\.planet-toolbar\s*\{[^}]*grid-column:\s*1;[^}]*grid-row:\s*1/);
  });

  it('на узкой карточке и телефоне переключатель стоит отдельной строкой над сценой', () => {
    const narrow = css.slice(css.indexOf('@container planet (max-width: 700px)'));
    expect(narrow).toMatch(/\.planet-viewbar\s*\{[^}]*order:\s*0;[^}]*width:\s*100%/);
    expect(narrow).toMatch(/\.planet-stage\s*\{\s*order:\s*1/);
  });

  it('на главной подложка скруглена как плита, а переключатель повторяет «колодец» полей', () => {
    expect(hero).toMatch(/\.planet-view\s*\{\s*--planet-map-radius:\s*22px/);
    expect(hero).toMatch(/\.planet-view-switch button\[aria-pressed='true'\]/);
  });
});
