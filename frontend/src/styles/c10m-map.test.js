// Круг 10, зона «карта и главная»: стражи раскладки по звонку «На правки 23» (К3, К4, К5, К6).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (...parts) => readFileSync(resolve(import.meta.dirname, ...parts), 'utf8');
const hero = read('planet-hero.css');
const regions = read('regions-w4.css');
const z5 = read('z5-country.css');
const c10m = read('c10m-map.css');

describe('К3: пустота рядом с картой на главной', () => {
  const block = hero.slice(hero.indexOf('Круг 10, зона «карта и главная»'));

  it('с 1280 px «Мир сейчас» лежит полосой во всю ширину под текстом и картой, а не в левой колонке', () => {
    expect(block).toMatch(/@media \(min-width: 1280px\)\s*\{[\s\S]*grid-template-areas: "text planet" "today today" "scope scope"/);
    expect(block).toMatch(/\.fe-today__grid\s*\{\s*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  });

  it('карточка планеты тянется по высоте текста и больше не липнет', () => {
    expect(block).toMatch(/\.fe-dashboard \.fe-hero-planet\s*\{[^}]*align-self: stretch/);
    expect(block).toMatch(/\.fe-dashboard \.fe-hero-planet\s*\{[^}]*position: relative/);
    expect(block).not.toMatch(/position: sticky/);
  });
});

describe('К4: профиль страны', () => {
  it('на компьютере карта идёт полосой во всю карточку, факты ниже двумя колонками, карта выше прежних 170 px', () => {
    expect(z5).toMatch(/@media \(min-width: 1024px\)\s*\{[\s\S]*grid-template-areas: 'head' 'map' 'facts' 'source'/);
    expect(z5).toMatch(/\.z5-profile \.w2-profile-map\s*\{[^}]*max-height: 230px/);
    expect(z5).toMatch(/\.z5-hero__profile\s*\{\s*flex: 0 0 min\(520px, 44%\)/);
  });

  it('на планшете и телефоне карта крупнее прежнего (220 и 190 px вместо 170 и 150)', () => {
    expect(z5).toMatch(/max-height: 220px; margin: 0;/);
    expect(z5).toMatch(/@media \(max-width: 639px\)\s*\{[\s\S]*\.w2-profile-map\s*\{\s*max-height: 190px/);
  });
});

describe('К5, К6: карты регионов и штатов помещаются в один экран', () => {
  it('высота карты не больше ~46 % экрана (было 54 %), с 768 px, не ниже 300 px', () => {
    expect(regions).toMatch(/@media \(min-width: 768px\)\s*\{\s*\.fe-map-frame > \.fe-map-svg\s*\{\s*max-width: calc\(max\(46svh, 300px\) \* var\(--fe-map-aspect, 1\.9\)\)/);
    expect(regions).not.toMatch(/54svh \* var/);
  });

  it('карта штатов в профиле США не выше трети экрана и 250 px и без рамок', () => {
    expect(c10m).toMatch(/\.c10m-states-map svg\s*\{[^}]*max-height: min\(250px, 34svh\)/);
    expect(c10m).not.toMatch(/(^|[\s;{])border(-(top|right|bottom|left|width|color|style))?\s*:|outline|box-shadow/);
  });
});
