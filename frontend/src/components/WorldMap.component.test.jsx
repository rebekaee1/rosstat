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

describe('WorldMap embedded in the planet stage', () => {
  const countries = [
    { code: 'DE', slug: 'germany', name: 'Германия' },
    { code: 'LU', slug: 'luxembourg', name: 'Люксембург' },
    { code: 'MT', slug: 'malta', name: 'Мальта' },
  ];
  const values = new Map([['DE', 3.2], ['LU', 1.1], ['MT', 2.4]]);
  const transform = (container) => container.querySelector('svg > g').getAttribute('transform');
  const embedded = (extra = {}) => (
    <WorldMap embedded countries={countries} valuesByCode={values} detailsByCode={new Map()} unit="%" {...extra} />
  );

  it('рисует только карту: без своей шапки, легенды, кнопок и подписи (их даёт PlanetView)', () => {
    const { container } = renderMap(embedded());
    expect(container.querySelector('[data-planet-map="true"] svg')).toBeTruthy();
    expect(container.querySelector('.k4-tube, .k4-map-plate, .fe-map-btn')).toBeNull();
    expect(screen.queryByText('Выберите страну на карте')).toBeNull();
    expect(container.querySelector('svg rect')).toBeNull();
    expect(screen.getByRole('button', { name: /Германия/ })).toBeTruthy();
  });

  it('красит страны переданной моделью цвета и сообщает о наведении и выборе', () => {
    const onHover = vi.fn();
    const onSelect = vi.fn();
    const colorModel = { colorFor: () => '#123456', isTop: () => false, bins: [], describe: () => null };
    renderMap(embedded({ colorModel, onHover, onSelect }));
    const germany = screen.getByRole('button', { name: /Германия/ });
    expect(germany.getAttribute('fill')).toBe('#123456');
    fireEvent.mouseEnter(germany);
    expect(onHover).toHaveBeenLastCalledWith('DE');
    fireEvent.mouseLeave(germany);
    expect(onHover).toHaveBeenLastCalledWith(null);
    fireEvent.click(germany);
    expect(onSelect).toHaveBeenCalledWith(countries[0], null);
  });

  it('обводит выбранную страну', () => {
    const { container, rerender } = renderMap(embedded());
    expect(container.querySelector('[data-selected-outline]')).toBeNull();
    rerender(<LocaleProvider>{embedded({ selectedCode: 'DE' })}</LocaleProvider>);
    expect(container.querySelector('[data-selected-outline]').getAttribute('d')).toBeTruthy();
  });

  it('выполняет команды камеры: приблизить, отдалить, показать страну и вся карта', () => {
    const { container, rerender } = renderMap(embedded());
    expect(transform(container)).toBe('translate(0 0) scale(1)');
    const withCommand = (command) => rerender(<LocaleProvider>{embedded({ command })}</LocaleProvider>);
    withCommand({ id: 1, type: 'zoomIn' });
    expect(transform(container)).toMatch(/scale\(1\.55\)/);
    withCommand({ id: 2, type: 'zoomOut' });
    expect(transform(container)).toBe('translate(0 0) scale(1)');
    withCommand({ id: 3, type: 'focus', countryCode: 'LU' });
    expect(transform(container)).toMatch(/scale\((7|[3-6](\.\d+)?)\)/);
    withCommand({ id: 4, type: 'reset' });
    expect(transform(container)).toBe('translate(0 0) scale(1)');
  });

  it('не повторяет уже выполненную команду при обычной перерисовке', () => {
    const { container, rerender } = renderMap(embedded({ command: { id: 1, type: 'zoomIn' } }));
    expect(transform(container)).toMatch(/scale\(1\.55\)/);
    rerender(<LocaleProvider>{embedded({ command: { id: 1, type: 'zoomIn' }, unit: '%' })}</LocaleProvider>);
    expect(transform(container)).toMatch(/scale\(1\.55\)/);
  });

  it('щипок двумя пальцами приближает карту, а палец потом не выбирает страну под собой', () => {
    const onSelect = vi.fn();
    const { container } = renderMap(embedded({ onSelect }));
    const svg = container.querySelector('svg');
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 960, height: 480, right: 960, bottom: 480 });
    svg.setPointerCapture = () => {};
    fireEvent.pointerDown(svg, { pointerId: 1, clientX: 450, clientY: 240 });
    fireEvent.pointerDown(svg, { pointerId: 2, clientX: 510, clientY: 240 });
    fireEvent.pointerMove(svg, { pointerId: 2, clientX: 630, clientY: 240 });
    // Пальцы разошлись втрое (60 → 180 px): масштаб ×3, точка под серединой щипка (480; 240) переехала вместе с серединой (540; 240).
    expect(transform(container)).toBe('translate(-900 -480) scale(3)');
    fireEvent.pointerUp(svg, { pointerId: 2 });
    fireEvent.pointerUp(svg, { pointerId: 1 });
    fireEvent.click(screen.getByRole('button', { name: /Германия/ }));
    expect(onSelect).not.toHaveBeenCalled();
    // Сведение пальцев возвращает вид целиком.
    fireEvent.pointerDown(svg, { pointerId: 3, clientX: 300, clientY: 240 });
    fireEvent.pointerDown(svg, { pointerId: 4, clientX: 700, clientY: 240 });
    fireEvent.pointerMove(svg, { pointerId: 4, clientX: 300.5, clientY: 240 });
    expect(transform(container)).toBe('translate(0 0) scale(1)');
  });

  it('одним пальцем двигает приближенную карту и не двигает карту целиком', () => {
    const { container, rerender } = renderMap(embedded());
    const svg = container.querySelector('svg');
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 960, height: 480, right: 960, bottom: 480 });
    svg.setPointerCapture = () => {};
    fireEvent.pointerDown(svg, { pointerId: 1, clientX: 400, clientY: 200 });
    fireEvent.pointerMove(svg, { pointerId: 1, clientX: 300, clientY: 150 });
    expect(transform(container)).toBe('translate(0 0) scale(1)');
    fireEvent.pointerUp(svg, { pointerId: 1 });
    rerender(<LocaleProvider>{embedded({ command: { id: 7, type: 'zoomIn' } })}</LocaleProvider>);
    fireEvent.pointerDown(svg, { pointerId: 1, clientX: 400, clientY: 200 });
    fireEvent.pointerMove(svg, { pointerId: 1, clientX: 380, clientY: 190 });
    expect(transform(container)).not.toBe('translate(0 0) scale(1.55)');
  });

  it('государства-крохи получают точку с широкой зоной нажатия; точка выбирает страну', async () => {
    const onSelect = vi.fn();
    const { container } = renderMap(embedded({ onSelect }));
    const marker = await waitFor(() => {
      const found = container.querySelector('[data-country-marker="LU"]');
      expect(found).toBeTruthy();
      return found;
    });
    const [hit, dot] = marker.querySelectorAll('circle');
    expect(Number(hit.getAttribute('r'))).toBeGreaterThan(Number(dot.getAttribute('r')));
    expect(marker.getAttribute('aria-hidden')).toBe('true');
    fireEvent.click(marker);
    expect(onSelect).toHaveBeenCalledWith(countries[1], null);
    // Крупную страну точкой не дублируем.
    expect(container.querySelector('[data-country-marker="DE"]')).toBeNull();
  });

  it('Мальта получает точку, когда догрузился подробный атлас, и команда «показать» подводит к ней карту', async () => {
    const { container, rerender } = renderMap(embedded());
    await waitFor(() => expect(container.querySelector('[data-country-marker="MT"]')).toBeTruthy(), { timeout: 20000 });
    rerender(<LocaleProvider>{embedded({ command: { id: 1, type: 'focus', countryCode: 'MT' } })}</LocaleProvider>);
    expect(Number(transform(container).match(/scale\(([\d.]+)\)/)[1])).toBeGreaterThanOrEqual(3);
  }, 30000);

  it('показывает страну, контура которой ещё не было, когда он появится', async () => {
    const { container } = renderMap(embedded({ command: { id: 1, type: 'focus', countryCode: 'MT' } }));
    // Подробный атлас ещё не догружен: сначала вид общий, затем карта сама подводится к стране.
    await waitFor(() => expect(Number(transform(container).match(/scale\(([\d.]+)\)/)[1])).toBeGreaterThanOrEqual(3), { timeout: 20000 });
  }, 30000);
});
