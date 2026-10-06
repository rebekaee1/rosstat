import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorldMap, { CountrySilhouette } from './WorldMap';
import { LocaleProvider } from '../i18n';

function renderMap(ui) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

const pathLength = (label) => screen.getByRole('img', { name: label })
  .querySelector('path')
  .getAttribute('d')
  .length;

describe('CountrySilhouette', () => {
  it('показывает контур сразу и уточняет его после подгрузки', async () => {
    renderMap(<CountrySilhouette code="AT" name="Австрия" />);
    const initial = pathLength('Карта страны: Австрия');
    expect(initial).toBeGreaterThan(0);
    await waitFor(() => {
      expect(pathLength('Карта страны: Австрия')).toBeGreaterThan(initial * 3);
    });
  });

  it('дотягивает контур государства-крохи до читаемого', async () => {
    renderMap(<CountrySilhouette code="MT" name="Мальта" />);
    await waitFor(() => {
      expect(pathLength('Карта страны: Мальта')).toBeGreaterThan(400);
    }, { timeout: 15000 });
  });

  it('понимает и UK, и GB', async () => {
    renderMap(<CountrySilhouette code="GB" name="Великобритания" />);
    await waitFor(() => {
      expect(pathLength('Карта страны: Великобритания')).toBeGreaterThan(0);
    });
  });

  it('ничего не рисует для неизвестного кода', () => {
    const { container } = renderMap(<CountrySilhouette code="ZZ" name="Нигде" />);
    expect(container.innerHTML).toBe('');
  });

  it('не показывает человеку технику: код страны, диапазон лет и частоту', () => {
    renderMap(
      <CountrySilhouette
        code="AT"
        name="Австрия"
        region="Европа"
        historyStart="1996-01-01"
        historyEnd="2026-06-01"
        frequencies={['monthly', 'annual']}
      />,
    );
    const panel = screen.getByLabelText('Контур территории: Австрия');
    expect(panel.textContent).not.toMatch(/AT\b/);
    expect(panel.textContent).not.toContain('1996');
    expect(screen.queryByText('месяц')).toBeNull();
    expect(screen.getByText('Европа')).toBeTruthy();
  });

  it('показывает площадь и население с русской типографикой', () => {
    renderMap(
      <CountrySilhouette
        code="AT"
        name="Австрия"
        area={{
          value: 83882,
          unit: 'км²',
          year: 2026,
          source: 'Евростат',
          source_url: 'https://ec.europa.eu/eurostat/databrowser/view/reg_area3',
        }}
        population={{
          value: 9197213,
          unit: 'человек',
          date: '2025-01-01',
          year: 2025,
          source: 'Евростат',
          source_url: 'https://ec.europa.eu/eurostat/databrowser/view/demo_pjan',
        }}
      />,
    );
    expect(screen.getByText('Площадь')).toBeTruthy();
    expect(screen.getByText('Население')).toBeTruthy();
    const panel = screen.getByLabelText('Контур территории: Австрия');
    const normalized = panel.textContent.replace(/\u00A0/g, ' ');
    expect(normalized).toContain('83 882 км²');
    expect(normalized).toContain('9,2 млн человек');
    // Год площади не показываем (она почти не меняется); год населения — словами: «на 2025 г.».
    expect(normalized).not.toContain('2026');
    expect(normalized).toContain('на 2025 г.');
    const source = screen.getByRole('link', { name: 'Евростат' });
    expect(source.getAttribute('href')).toBe('https://ec.europa.eu/eurostat/databrowser/view/reg_area3');
    expect(source.getAttribute('target')).toBe('_blank');
    expect(source.getAttribute('rel')).toMatch(/noopener/);
  });

  it('на EN показывает Eurostat и km²', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('preview_locale', 'en');
    window.history.pushState({}, '', url.toString());
    try {
      renderMap(
        <CountrySilhouette
          code="SE"
          name="Sweden"
          area={{
            value: 447424,
            unit: 'км²',
            year: 2026,
            source: 'Евростат',
            source_url: 'https://ec.europa.eu/eurostat/databrowser/view/reg_area3',
          }}
          population={{
            value: 10500000,
            unit: 'человек',
            year: 2025,
            source: 'Евростат',
            source_url: 'https://ec.europa.eu/eurostat/databrowser/view/demo_pjan',
          }}
        />,
      );
      const panel = screen.getByLabelText('Territory outline: Sweden');
      const normalized = panel.textContent.replace(/\u00A0/g, ' ').replace(/,/g, ' ');
      expect(normalized).toMatch(/447[\s]?424 km²/);
      expect(screen.getByRole('link', { name: 'Eurostat' })).toBeTruthy();
      expect(screen.queryByText('Евростат')).toBeNull();
      expect(screen.queryByText(/км²/)).toBeNull();
    } finally {
      const reset = new URL(window.location.href);
      reset.searchParams.delete('preview_locale');
      window.history.pushState({}, '', reset.toString());
    }
  });

  it('профиль страны заполнен: население без вылезания за край, столица и валюта', () => {
    renderMap(
      <CountrySilhouette
        code="US"
        name="США"
        population={{ value: 342000000, unit: 'человек', year: 2025 }}
        area={{ value: 9833517, unit: 'км²' }}
      />,
    );
    expect(screen.getByText('Столица')).toBeTruthy();
    expect(screen.getByText('Вашингтон')).toBeTruthy();
    expect(screen.getByText('Валюта')).toBeTruthy();
    expect(screen.getByText('Доллар США')).toBeTruthy();
    // «342 млн человек»: неразрывный пробел только внутри «342 млн», дальше обычный: строка может перенестись, а не вылезти.
    const pop = screen.getByText(/342/);
    expect(pop.textContent).toContain('342\u00a0млн человек');
  });

  it('без площади и населения не ломается и не рисует пустые строки', () => {
    renderMap(<CountrySilhouette code="AT" name="Австрия" region="Европа" />);
    expect(screen.getByText('Профиль страны')).toBeTruthy();
    expect(screen.queryByText('Площадь')).toBeNull();
    expect(screen.queryByText('Население')).toBeNull();
    expect(screen.queryByText(/Источник:/)).toBeNull();
  });
});

describe('WorldMap tooltip', () => {
  const countries = [{ code: 'DE', slug: 'germany', name: 'Германия' }];

  it('показывает дату наблюдения по-русски', async () => {
    renderMap(
      <WorldMap
        countries={countries}
        valuesByCode={new Map([['DE', 3.2]])}
        detailsByCode={new Map([['DE', { date: '2026-06-01', value: 3.2 }]])}
        unit="%"
        periodLabel="2026"
      />,
    );
    fireEvent.mouseOver(screen.getByRole('button', { name: /Германия/ }));
    await waitFor(() => expect(screen.getByText('июнь 2026')).toBeTruthy());
  });

  it('подсвечивает страну контуром геометрии без прямоугольной рамки', async () => {
    const { container } = renderMap(
      <WorldMap
        countries={countries}
        valuesByCode={new Map([['DE', 3.2]])}
        detailsByCode={new Map([['DE', { date: '2026-06-01', value: 3.2 }]])}
        unit="%"
      />,
    );
    const countryPath = screen.getByRole('button', { name: /Германия/ });
    expect(countryPath.getAttribute('class') || '').toMatch(/outline-none/);
    fireEvent.mouseOver(countryPath);
    await waitFor(() => {
      const highlights = [...container.querySelectorAll('path[aria-hidden="true"]')]
        .filter((node) => (node.getAttribute('fill') || '').includes('44,74,138'));
      expect(highlights.length).toBeGreaterThan(0);
      expect(highlights[0].getAttribute('d')).toBeTruthy();
    });
  });

  it('кликает страну из map-series, даже если её нет в каталоге', () => {
    const onSelect = vi.fn();
    renderMap(
      <WorldMap
        countries={[]}
        valuesByCode={new Map([['US', 28]])}
        detailsByCode={new Map([['US', {
          country_code: 'US',
          country_slug: 'united-states',
          country_name: 'США',
          indicator_code: 'us-ngdpd',
          value: 28,
        }]])}
        onSelect={onSelect}
      />,
    );
    const btn = screen.getByRole('button', { name: /США/ });
    expect(btn.getAttribute('fill')).toBeTruthy();
    expect(btn.getAttribute('fill')).not.toMatch(/^url\(/);
    fireEvent.click(btn);
    expect(onSelect).toHaveBeenCalled();
    expect(onSelect.mock.calls[0][0].slug).toBe('united-states');
    expect(onSelect.mock.calls[0][1].indicator_code).toBe('us-ngdpd');
  });
});
