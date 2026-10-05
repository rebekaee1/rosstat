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

  it('длинный список свёрнут до первых строк и раскрывается кнопкой «Показать все страны»', async () => {
    renderCatalog(manyCountries(30));
    await screen.findAllByRole('link');
    // 30 стран + Россия, добавленная каркасом, — видно 12.
    expect(document.querySelectorAll('.fe-country-row')).toHaveLength(12);

    const more = screen.getByRole('button', { name: /Показать все страны \(31\)/ });
    fireEvent.click(more);
    expect(document.querySelectorAll('.fe-country-row')).toHaveLength(31);
    fireEvent.click(screen.getByRole('button', { name: 'Свернуть список' }));
    expect(document.querySelectorAll('.fe-country-row')).toHaveLength(12);
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
