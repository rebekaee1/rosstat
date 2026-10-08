import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (...parts) => readFileSync(resolve(import.meta.dirname, ...parts), 'utf8');
const css = read('..', 'components', 'PlanetView.css');
const hero = read('planet-hero.css');

describe('карта по умолчанию: раскладка окна сцены', () => {
  it('карта стоит в том же окне, что и шар: у неё нет своей высоты, а сцена не «схлопывается»', () => {
    expect(css).not.toMatch(/\.planet-stage--map\s*\{[^}]*height:\s*auto/);
    expect(css).not.toMatch(/\.planet-stage--map\s*\{[^}]*min-height/);
    expect(css).toMatch(/\.planet-stage\s*\{[^}]*height:\s*var\(--planet-scene-height\)/);
    expect(css).toMatch(/\.planet-map-stage\s*\{[^}]*position:\s*absolute;\s*inset:\s*0/);
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
