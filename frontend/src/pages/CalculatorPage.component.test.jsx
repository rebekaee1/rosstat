import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import CalculatorPage from './CalculatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';
import { MESSAGES } from '../i18n/messages';

vi.mock('gsap', () => ({
  default: {
    fromTo: () => ({ kill: () => {} }),
    to: () => ({ kill: () => {} }),
  },
}));

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

function monthlyCpi(fromYear, toYear, value) {
  const out = [];
  for (let y = fromYear; y <= toYear; y += 1) {
    for (let m = 1; m <= 12; m += 1) {
      out.push({ date: `${y}-${String(m).padStart(2, '0')}-01`, value });
    }
  }
  return out;
}

const CPI = { data: monthlyCpi(2020, 2021, 100) };

const CATALOG = {
  items: [
    {
      code: 'w:united-states:hicp-index',
      country_slug: 'united-states',
      country_name: 'США',
      concept_slug: 'hicp-index',
      indicator_code: 'us-cpi-all',
      frequency: 'monthly',
      unit: 'индекс 2015=100',
    },
    {
      code: 'w:germany:hicp-index',
      country_slug: 'germany',
      country_name: 'Германия',
      concept_slug: 'hicp-index',
      indicator_code: 'de-prc_hicp_midx-cp00',
      frequency: 'monthly',
      unit: 'индекс 2015=100',
    },
    {
      code: 'w:france:hicp-index',
      country_slug: 'france',
      country_name: 'Франция',
      concept_slug: 'hicp-index',
      indicator_code: 'fr-prc_hicp_midx-cp00',
      frequency: 'monthly',
      unit: 'индекс 2015=100',
    },
    {
      code: 'w:estonia:hicp-index',
      country_slug: 'estonia',
      country_name: 'Эстония',
      concept_slug: 'hicp-index',
      indicator_code: 'ee-prc_hicp_midx-cp00',
      frequency: 'monthly',
      unit: 'индекс 2015=100',
    },
    {
      code: 'w:germany:unemployment-rate',
      country_slug: 'germany',
      country_name: 'Германия',
      concept_slug: 'unemployment-rate',
      indicator_code: 'de-une',
      frequency: 'monthly',
      unit: '%',
    },
  ],
  total: 4,
};

const GERMANY_SERIES = {
  meta: {
    country_slug: 'germany',
    country_name: 'Германия',
    indicator_code: 'de-prc_hicp_midx-cp00',
    concept_slug: 'hicp-index',
  },
  data: [
    { date: '2018-12-01', value: 100 },
    { date: '2019-12-01', value: 102 },
    { date: '2020-12-01', value: 106.08 },
  ],
};

const ESTONIA_SERIES = {
  meta: {
    country_slug: 'estonia',
    country_name: 'Эстония',
    indicator_code: 'ee-prc_hicp_midx-cp00',
    concept_slug: 'hicp-index',
  },
  data: [
    { date: '2018-12-01', value: 100 },
    { date: '2019-12-01', value: 102 },
    { date: '2020-12-01', value: 106.08 },
  ],
};

const US_SERIES = {
  meta: {
    country_slug: 'united-states',
    country_name: 'США',
    indicator_code: 'us-cpi-all',
    concept_slug: 'hicp-index',
  },
  data: [
    { date: '2018-12-01', value: 100 },
    { date: '2019-12-01', value: 102 },
    { date: '2020-12-01', value: 106.08 },
  ],
};

function worldMeta(source) {
  return {
    indicator: { source, code: 'x', source_url: 'https://www.example.com/source' },
    country: { slug: 'germany', name: 'Германия' },
  };
}

function usWorldMeta(source) {
  return {
    indicator: { source, code: 'us-cpi-all', source_url: 'https://www.example.com/us-cpi' },
    country: { slug: 'united-states', name: 'США' },
  };
}

function mockCalcApis() {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/indicators/cpi/data', CPI],
    ['/indicators/cpi-food/data', CPI],
    ['/indicators/cpi-nonfood/data', CPI],
    ['/indicators/cpi-services/data', CPI],
    ['/world/compare/catalog', CATALOG],
    [/^\/world\/compare\/series\/germany\//, GERMANY_SERIES],
    [/^\/world\/compare\/series\/estonia\//, ESTONIA_SERIES],
    [/^\/world\/compare\/series\/united-states\//, US_SERIES],
    [/^\/world\/indicators\/germany\//, worldMeta('Евростат')],
    [/^\/world\/indicators\/estonia\//, worldMeta('Евростат')],
    [/^\/world\/indicators\/united-states\//, usWorldMeta('Бюро трудовой статистики США')],
  ]);
}

/** EN-локаль через официальный preview-механизм (jsdom-паттерн WorldMap.component). */
function setPreviewLocaleEn() {
  const url = new URL(window.location.href);
  url.searchParams.set('preview_locale', 'en');
  window.history.pushState({}, '', url.toString());
}

function resetPreviewLocale() {
  const url = new URL(window.location.href);
  url.searchParams.delete('preview_locale');
  window.history.pushState({}, '', url.toString());
}

function collapseWs(text) {
  return String(text || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
}

describe('CalculatorPage country select', () => {
  it('показывает Россию по умолчанию и страны с инфляционным рядом из API', async () => {
    mockCalcApis();
    renderPage(<CalculatorPage />, {
      path: '/calculator',
      route: '/calculator?amount=100000&from=2020&to=2021',
    });

    expect(await screen.findByRole('heading', { level: 1 })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Страна' }));
    expect(await screen.findByRole('option', { name: 'Германия' })).toBeTruthy();
    const list = screen.getByRole('listbox');
    expect(within(list).getByRole('option', { name: 'Россия' })).toBeTruthy();
    expect(within(list).getByRole('option', { name: 'Франция' })).toBeTruthy();
    expect(within(list).queryByRole('option', { name: /безработ/i })).toBeNull();
  });

  it('выбор страны меняет ряд и пересчитывает результат', async () => {
    mockCalcApis();
    renderPage(<CalculatorPage />, {
      path: '/calculator',
      route: '/calculator?amount=100000&from=2020&to=2021',
    });

    await waitFor(() => {
      expect(collapseWs(document.body.textContent)).toMatch(/100 000/);
    });
    expect(collapseWs(document.body.textContent)).toMatch(/Росстат/);

    fireEvent.click(screen.getByRole('button', { name: 'Страна' }));
    fireEvent.click(await screen.findByRole('option', { name: 'Германия' }));

    await waitFor(() => {
      const text = collapseWs(document.body.textContent);
      expect(text).toMatch(/104 000/);
      expect(text).toMatch(/Источник: Евростат/);
    });
    expect(collapseWs(document.body.textContent)).not.toMatch(/104 000 ₽/);
  });

  it('короткий ряд показывает оговорку и считает с первого доступного года', async () => {
    mockCalcApis();
    renderPage(<CalculatorPage />, {
      path: '/calculator',
      route: '/calculator?amount=100000&from=2010&to=2020&country=estonia',
    });

    await waitFor(() => {
      expect(collapseWs(document.body.textContent)).toMatch(/ряд есть с 2018/);
    });
    expect(collapseWs(document.body.textContent)).toMatch(/2019–2020|2019-2020/);
    expect(collapseWs(document.body.textContent)).toMatch(/106 080/);
  });
});

describe('EN copy for country calculator', () => {
  it('не содержит кириллицы в новых ключах', () => {
    const keys = Object.keys(MESSAGES.en).filter((key) => (
      key.startsWith('calc.country')
      || key.includes('.world')
      || key.includes('World')
      || key.includes('shortSeries')
      || key.includes('Plain')
      || key === 'calc.inflation.source'
    ));
    expect(keys.length).toBeGreaterThan(8);
    for (const key of keys) {
      expect(MESSAGES.en[key], key).not.toMatch(/[А-Яа-яЁё]/);
    }
  });
});

describe('calculator default country by locale (K1)', () => {
  it('EN-локаль без ?country показывает США', async () => {
    mockCalcApis();
    setPreviewLocaleEn();
    try {
      renderPage(<CalculatorPage />, {
        path: '/calculator',
        route: '/calculator?amount=100000&from=2019&to=2020',
      });

      await waitFor(() => {
        expect(collapseWs(document.body.textContent)).toMatch(/106 080/);
      });
      expect(collapseWs(document.body.textContent)).toMatch(/U\.S\. Bureau of Labor Statistics/);
      expect(screen.getByRole('button', { name: 'Country' }).textContent).toMatch(/США/);
    } finally {
      resetPreviewLocale();
    }
  });

  it('явный ?country=france перекрывает дефолт локали', async () => {
    mockCalcApis();
    setPreviewLocaleEn();
    try {
      renderPage(<CalculatorPage />, {
        path: '/calculator',
        route: '/calculator?amount=100000&from=2019&to=2020&country=france',
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Country' }).textContent).toMatch(/Франция/i);
      });
    } finally {
      resetPreviewLocale();
    }
  });

  it('неизвестный слаг откатывается к дефолту локали', async () => {
    mockCalcApis();
    setPreviewLocaleEn();
    try {
      renderPage(<CalculatorPage />, {
        path: '/calculator',
        route: '/calculator?amount=100000&from=2019&to=2020&country=atlantis',
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Country' }).textContent).toMatch(/США/);
        expect(collapseWs(document.body.textContent)).toMatch(/106 080/);
      });
    } finally {
      resetPreviewLocale();
    }
  });

  it('русская локаль без ?country по-прежнему показывает Россию', async () => {
    mockCalcApis();
    renderPage(<CalculatorPage />, {
      path: '/calculator',
      route: '/calculator?amount=100000&from=2020&to=2021',
    });

    await waitFor(() => {
      expect(collapseWs(document.body.textContent)).toMatch(/Росстат/);
    });
  });
});

describe('calculator source link (K4b)', () => {
  it('мировая ветка ведёт на source_url из meta в новой вкладке', async () => {
    mockCalcApis();
    renderPage(<CalculatorPage />, {
      path: '/calculator',
      route: '/calculator?amount=100000&from=2019&to=2020&country=germany',
    });

    const link = await screen.findByRole('link', { name: 'Евростат' });
    expect(link.getAttribute('href')).toBe('https://www.example.com/source');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toMatch(/noopener/);
  });

  it('русская ветка ведёт на карточку ИПЦ', async () => {
    mockCalcApis();
    renderPage(<CalculatorPage />, {
      path: '/calculator',
      route: '/calculator?amount=100000&from=2020&to=2021',
    });

    const link = await screen.findByRole('link', { name: 'Росстат' });
    expect(link.getAttribute('href')).toBe('/russia/indicator/cpi');
  });
});

describe('watch more links (K5)', () => {
  it('блок «Смотреть дальше» рендерит три ссылки', async () => {
    mockCalcApis();
    renderPage(<CalculatorPage />, {
      path: '/calculator',
      route: '/calculator?amount=100000&from=2020&to=2021',
    });

    await waitFor(() => {
      expect(collapseWs(document.body.textContent)).toMatch(/Смотреть дальше/);
    });
    expect(screen.getByRole('link', { name: 'Регионы России' }).getAttribute('href')).toBe('/russia/region');
    expect(screen.getByRole('link', { name: 'Демография' }).getAttribute('href')).toBe('/russia/demographics');
    expect(screen.getByRole('link', { name: 'Экономика России' }).getAttribute('href')).toBe('/russia');
  });
});
