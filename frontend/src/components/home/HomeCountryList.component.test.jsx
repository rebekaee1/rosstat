import { describe, expect, it, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import HomeCountryList from './HomeCountryList';
import { renderPage, mockApiGet } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const COUNTRIES = [
  { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа', indicators_count: 12 },
  { code: 'JP', slug: 'japan', name: 'Япония', name_en: 'Japan', region: 'Азия', indicators_count: 9 },
  { code: 'ZA', slug: 'south-africa', name: 'ЮАР', name_en: 'South Africa', region: 'Африка', indicators_count: 5 },
  { code: 'AT', slug: 'austria', name: 'Австрия', name_en: 'Austria', region: 'Европа', indicators_count: 8205 },
];

function renderCatalog(countries = COUNTRIES, locale) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries', { countries, total: countries.length }],
  ]);
  return renderPage(<HomeCountryList russiaSeriesCount={8} />, { path: '/', route: '/', locale });
}

const manyCountries = (n) => Array.from({ length: n }, (_, i) => ({
  code: `E${i}`, slug: `eu-${i}`, name: `Страна ${String(i).padStart(2, '0')}`, name_en: `Country ${i}`, region: 'Европа', indicators_count: 3,
}));

describe('HomeCountryList — каталог стран', () => {
  it('пока ответ стран грузится, показывает поиск и каркас строк, а не пустое место', () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries', () => new Promise(() => {})],
    ]);
    renderPage(<HomeCountryList />, { path: '/', route: '/' });

    expect(screen.getByRole('heading', { name: 'Все страны А–Я' })).toBeTruthy();
    expect(screen.getByRole('searchbox', { name: 'Найти страну' })).toBeTruthy();
    expect(document.querySelectorAll('.fe-country-grid .skeleton').length).toBeGreaterThan(0);
  });

  it('один список по алфавиту, без заголовков регионов и без «1 страна»', async () => {
    renderCatalog();

    const catalog = screen.getByRole('heading', { name: 'Все страны А–Я' }).closest('section');
    const links = await within(catalog).findAllByRole('link');
    const names = links.map((a) => a.querySelector('.fe-country-row__name').textContent);
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, 'ru')));
    expect(names).toContain('Россия');
    // Счётчиков по регионам нет: ни «Африка — 1 страна», ни «Азия — 5 стран».
    expect(catalog.textContent).not.toMatch(/\d+\s+(страна|страны|стран)\b(?! с официальными)/);
    expect(within(catalog).queryByRole('button', { expanded: false })).toBeNull();
  });

  it('строка страны: флаг вместо кода, регион подписью, без английского названия, слов «ряд» и счётчика показателей', async () => {
    renderCatalog();

    const card = await screen.findByRole('link', { name: /Германия/ });
    expect(card.textContent).toContain('\u{1F1E9}\u{1F1EA}');
    expect(card.textContent).toContain('Европа');
    expect(card.textContent).not.toMatch(/Germany|\bDE\b|ряд|показател/);
    expect(card.className).toContain('fe-country-row');
  });

  it('поиск по названию (и по-английски) оставляет подходящие страны, пустой результат даёт «Сбросить»', async () => {
    renderCatalog();
    const search = screen.getByRole('searchbox', { name: 'Найти страну' });
    await screen.findByRole('link', { name: /Германия/ });

    fireEvent.change(search, { target: { value: 'япон' } });
    expect(screen.getByRole('link', { name: /Япония/ })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Германия/ })).toBeNull();

    fireEvent.change(search, { target: { value: 'germ' } });
    expect(screen.getByRole('link', { name: /Германия/ })).toBeTruthy();

    fireEvent.change(search, { target: { value: 'zzz' } });
    expect(screen.getByText(/Такой страны в каталоге нет/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Сбросить' }));
    expect(screen.getByRole('link', { name: /Япония/ })).toBeTruthy();
  });

  it('регион — фильтр-пилюля без счётчика; малый регион показывает свою единственную страну', async () => {
    renderCatalog();
    await screen.findByRole('link', { name: /Германия/ });

    const africa = screen.getByRole('button', { name: 'Африка' });
    expect(africa.textContent).toBe('Африка');
    fireEvent.click(africa);
    expect(africa.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('link', { name: /ЮАР/ })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Германия/ })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Все' }));
    expect(screen.getByRole('link', { name: /Германия/ })).toBeTruthy();
  });

  it('круг 9 (H9): набранное название ищется среди всех стран, фильтр региона его не скрывает', async () => {
    renderCatalog();
    await screen.findByRole('link', { name: /Германия/ });
    // Выбран регион «Африка», а человек ищет Австрию: она в «Европе», но находится.
    fireEvent.click(screen.getByRole('button', { name: 'Африка' }));
    expect(screen.queryByRole('link', { name: /Австрия/ })).toBeNull();
    fireEvent.change(screen.getByRole('searchbox', { name: 'Найти страну' }), { target: { value: 'австр' } });
    expect(screen.getByRole('link', { name: /Австрия/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Африка' }).getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByRole('button', { name: 'Все' }).getAttribute('aria-pressed')).toBe('true');
    // Очистили поиск: прежний фильтр региона снова действует.
    fireEvent.change(screen.getByRole('searchbox', { name: 'Найти страну' }), { target: { value: '' } });
    expect(screen.queryByRole('link', { name: /Австрия/ })).toBeNull();
    expect(screen.getByRole('link', { name: /ЮАР/ })).toBeTruthy();
  });

  it('длинный список свёрнут до первых строк и раскрывается кнопкой «Показать все страны»', async () => {
    renderCatalog(manyCountries(30));
    await screen.findAllByRole('link');
    // 30 стран + Россия, добавленная каркасом, — по алфавиту видно 24 (делится на 2, 3 и 4 колонки: в последнем ряду нет «дыры»).
    expect(document.querySelectorAll('.fe-country-row')).toHaveLength(24);

    const more = screen.getByRole('button', { name: /Показать все страны \(31\)/ });
    fireEvent.click(more);
    expect(document.querySelectorAll('.fe-country-row')).toHaveLength(31);
    fireEvent.click(screen.getByRole('button', { name: 'Свернуть список' }));
    expect(document.querySelectorAll('.fe-country-row')).toHaveLength(24);
  });

  it('EN: заголовок и поле по-английски, названия стран по-английски', async () => {
    renderCatalog(COUNTRIES, 'en');
    expect(screen.getByRole('heading', { name: 'All countries A–Z' })).toBeTruthy();
    expect(await screen.findByRole('link', { name: /Germany/ })).toBeTruthy();
    expect(screen.getByRole('searchbox', { name: 'Find a country' })).toBeTruthy();
  });

  describe('цифры в карточке и сортировка', () => {
    function renderWithFacts() {
      mockApiGet([
        ['/auth/me', { user: null }],
        ['/world/countries', { countries: COUNTRIES, total: COUNTRIES.length }],
        ['/world/compare/snapshot/gdp-usd', { items: [
          { country_code: 'DE', value: 4500, unit: 'млрд $' },
          { country_code: 'JP', value: 4200, unit: 'млрд $' },
          { country_code: 'AT', value: 520, unit: 'млрд $' },
        ] }],
        ['/world/compare/snapshot/hicp-index', { items: [{ country_code: 'DE', value: 2.3 }] }],
        ['/world/compare/snapshot/unemployment-rate', { items: [{ country_code: 'DE', value: 4 }] }],
        ['/world/compare/map-series/gdp-usd', { years: [2023, 2024], values_by_year: {
          2023: { DE: { value: 4.1 } }, 2024: { DE: { value: 4.5 } },
        } }],
      ]);
      return renderPage(<HomeCountryList russiaSeriesCount={8} />, { path: '/', route: '/' });
    }

    it('в карточке страны: размер экономики, инфляция, безработица и линия истории', async () => {
      renderWithFacts();
      const card = await screen.findByRole('link', { name: /Германия/ });
      await waitFor(() => expect(card.querySelector('.fe-country-row__facts')).toBeTruthy());
      const facts = card.querySelector('.fe-country-row__facts').textContent.replace(/\u00a0/g, ' ');
      expect(facts).toContain('ВВП4,5 трлн $');
      expect(facts).toContain('Инфляция2,3 %');
      expect(facts).toContain('Безработица4,0 %');
      expect(card.querySelector('.fe-country-row__spark')).toBeTruthy();
      // Карточка ведёт на обзор страны, а не на отдельный показатель.
      expect(card.getAttribute('href')).toBe('/germany');
    });

    it('сортировка «По размеру экономики»: крупные сверху, страны без значения в конце', async () => {
      renderWithFacts();
      const card = await screen.findByRole('link', { name: /Германия/ });
      await waitFor(() => expect(card.querySelector('.fe-country-row__facts')).toBeTruthy());
      fireEvent.click(screen.getByRole('button', { name: 'По размеру экономики' }));
      expect(screen.getByRole('heading', { name: 'Все страны по размеру экономики' })).toBeTruthy();
      const names = screen.getAllByRole('link').map((a) => a.querySelector('.fe-country-row__name')?.textContent).filter(Boolean);
      expect(names.slice(0, 3)).toEqual(['Германия', 'Япония', 'Австрия']);
      expect(names).toContain('Россия');
    });
  });

  describe('по умолчанию по размеру экономики', () => {
    function renderSized(countries = COUNTRIES) {
      mockApiGet([
        ['/auth/me', { user: null }],
        ['/world/countries', { countries, total: countries.length }],
        ['/world/compare/snapshot/gdp-usd', { items: [
          { country_code: 'DE', value: 4500, unit: 'млрд $' },
          { country_code: 'JP', value: 4200, unit: 'млрд $' },
          { country_code: 'AT', value: 520, unit: 'млрд $' },
        ] }],
        ['/world/compare/snapshot/hicp-index', { items: [{ country_code: 'DE', value: 2.3 }, { country_code: 'AT', value: 7 }] }],
        ['/world/compare/snapshot/unemployment-rate', { items: [{ country_code: 'DE', value: 4 }, { country_code: 'AT', value: 6.5 }] }],
        ['/world/compare/map-series/gdp-usd', { years: [2023, 2024], values_by_year: {
          2019: { DE: { value: 3 } }, 2020: { DE: { value: 3.2 } }, 2021: { DE: { value: 3.5 } }, 2022: { DE: { value: 3.9 } },
          2023: { DE: { value: 4.1 } }, 2024: { DE: { value: 4.5 } },
        } }],
      ]);
      return renderPage(<HomeCountryList russiaSeriesCount={8} />, { path: '/', route: '/' });
    }

    it('без нажатий крупные экономики сверху, заголовок про размер экономики, три крупные карточки и золотая полоска у десятки', async () => {
      renderSized();
      expect(await screen.findByRole('heading', { name: 'Все страны по размеру экономики' })).toBeTruthy();
      const names = screen.getAllByRole('link').map((a) => a.querySelector('.fe-country-row__name')?.textContent).filter(Boolean);
      expect(names.slice(0, 3)).toEqual(['Германия', 'Япония', 'Австрия']);
      expect(screen.getByRole('button', { name: 'По размеру экономики' }).getAttribute('aria-pressed')).toBe('true');
      expect(document.querySelector('.fe-country-grid').getAttribute('data-featured')).toBe('true');
      expect(document.querySelectorAll('.fe-country-row.is-top').length).toBeGreaterThanOrEqual(3);
      // Медали-грани (золото, серебро, бронза) только у трёх первых карточек; в сетке без размера их нет.
      expect([...document.querySelectorAll('.fe-country-row__medal')].map((medal) => medal.getAttribute('data-rank'))).toEqual(['1', '2', '3']);
      // Поиск и фильтр возвращают обычную сетку: крупных карточек нет.
      fireEvent.change(screen.getByRole('searchbox', { name: 'Найти страну' }), { target: { value: 'япон' } });
      expect(document.querySelector('.fe-country-grid').getAttribute('data-featured')).toBeNull();
      expect(document.querySelectorAll('.fe-country-row__medal')).toHaveLength(0);
    });

    it('инфляция и безработица с цветным маркером и словом для скринридера, регион у карточки в data-атрибуте', async () => {
      renderSized();
      const germany = await screen.findByRole('link', { name: /Германия/ });
      const metrics = [...germany.querySelectorAll('.fe-country-row__metric')];
      expect(metrics.map((node) => node.getAttribute('data-tone'))).toEqual(['good', 'good']);
      expect(germany.getAttribute('data-region')).toBe('europe');
      const austria = screen.getByRole('link', { name: /Австрия/ });
      expect(austria.querySelector('.fe-country-row__metric').getAttribute('data-tone')).toBe('warn');
      expect(austria.querySelector('.fe-country-row__metric .sr-only').textContent).toBe('стоит присмотреться');
      expect(germany.querySelector('.fe-country-row__spark')).toBeTruthy();
    });

    it('свёрнутый список при сортировке по размеру: три крупные и 12 обычных, то есть 15 карточек', async () => {
      const many = Array.from({ length: 30 }, (_, i) => ({
        code: `E${i}`, slug: `eu-${i}`, name: `Страна ${String(i).padStart(2, '0')}`, name_en: `Country ${i}`, region: 'Европа', indicators_count: 3,
      }));
      mockApiGet([
        ['/auth/me', { user: null }],
        ['/world/countries', { countries: many, total: many.length }],
        ['/world/compare/snapshot/gdp-usd', { items: many.map((c, i) => ({ country_code: c.code, value: 1000 - i, unit: 'млрд $' })) }],
        ['/world/compare/snapshot/hicp-index', { items: [] }],
        ['/world/compare/snapshot/unemployment-rate', { items: [] }],
        ['/world/compare/map-series/gdp-usd', { years: [], values_by_year: {} }],
      ]);
      renderPage(<HomeCountryList russiaSeriesCount={8} />, { path: '/', route: '/' });
      await screen.findByRole('heading', { name: 'Все страны по размеру экономики' });
      expect(document.querySelectorAll('.fe-country-row')).toHaveLength(15);
    });
  });

  it('Азербайджан и Армения стоят в Азии, а не в Европе', async () => {
    renderCatalog([
      { code: 'AZ', slug: 'azerbaijan', name: 'Азербайджан', name_en: 'Azerbaijan', region: 'Европа', indicators_count: 5 },
      { code: 'AM', slug: 'armenia', name: 'Армения', name_en: 'Armenia', region: 'Европа', indicators_count: 5 },
      { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа', indicators_count: 5 },
    ]);
    const card = await screen.findByRole('link', { name: /Азербайджан/ });
    expect(card.querySelector('.fe-country-row__meta').textContent).toBe('Азия');
    expect((await screen.findByRole('link', { name: /Германия/ })).querySelector('.fe-country-row__meta').textContent).toBe('Европа');
  });
});
