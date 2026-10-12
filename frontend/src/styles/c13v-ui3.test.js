// Круг 13, зона UI3: охранные проверки правил, которые закрывают находки симулятора-2 (рейтинг, шапка на планшете, мелкие цели, плашка установки, С1).
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const read = (name) => readFileSync(new URL(`./${name}`, import.meta.url), 'utf8');
const rating = read('z6-rating.css');
const z4 = read('z4-indicator.css');
const tokens = read('z1-tokens.css');
const tools = read('z8-tools.css');

describe('круг 13 UI3', () => {
  it('рейтинг: название и значение в строку с переносом, название не рвётся по буквам', () => {
    expect(rating).toMatch(/\.z6-ribbon \.w2-fact \{[^}]*display: flex; flex-flow: row wrap;/);
    expect(rating).toMatch(/\.z6-ribbon \.w2-fact-name \{[^}]*min-width: min\(100%, 9rem\);[^}]*overflow-wrap: break-word;[^}]*word-break: normal;/);
    expect(rating).not.toMatch(/\.z6-ribbon \.w2-fact-name[^}]*anywhere/);
    expect(rating).toMatch(/\.z6-ribbon \.w2-fact-value \{[^}]*flex: 0 1 auto;/);
  });

  it('страница показателя: на 744–1023 главное число стоит вставкой под названием, строка-дублёр скрыта', () => {
    expect(z4).toMatch(/@media \(min-width: 744px\) and \(max-width: 1023px\) \{[^@]*\.z4-hero\[data-has-value='true'\] \.z4-hero__line \{ display: none; \}[^@]*\.z4-hero__aside \{\s*display: block;/);
  });

  it('поле поиска валют не ниже 40 px, ссылка календаря 36 px при прежней плотности', () => {
    expect(tools).toMatch(/\.fe-z8-search__input \{[^}]*min-height: 40px;/);
    const cal = readFileSync(new URL('../components/calendar/CalendarEventCard.jsx', import.meta.url), 'utf8');
    expect(cal).toMatch(/-m-\[11px\] inline-flex h-9 w-9/);
  });

  it('плашка установки: от 744 px нижняя полоса во весь экран с запасом под страницу', () => {
    expect(tokens).toMatch(/@media \(min-width: 744px\) \{\s*\.fe-pwa-card\[data-slim='true'\],\s*\.fe-pwa-card\[data-platform='android'\] \{\s*left: 0; right: 0; max-width: none;/);
    expect(tokens).toMatch(/html\[data-fe-pwa-bar\] body \{ padding-bottom: var\(--fe-pwa-h, 0px\); \}/);
  });

  it('С1: карточка прогноза тянется на высоту ряда и не липнет', () => {
    expect(z4).toMatch(/Круг 13, зона UI3: С1/);
    expect(z4).not.toMatch(/Круг 12, зона UI2: С1 карточка прогноза не растягивается/);
    expect(z4).toMatch(/\.fe-fc-table \{ height: 100%; \}/);
  });
});
