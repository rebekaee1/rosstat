import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorldMap, { CountrySilhouette } from './WorldMap';

const pathLength = (label) => screen.getByRole('img', { name: label })
  .querySelector('path')
  .getAttribute('d')
  .length;

describe('CountrySilhouette', () => {
  it('показывает контур сразу и уточняет его после подгрузки', async () => {
    render(<CountrySilhouette code="AT" name="Австрия" />);
    const initial = pathLength('Карта страны: Австрия');
    expect(initial).toBeGreaterThan(0);
    await waitFor(() => {
      expect(pathLength('Карта страны: Австрия')).toBeGreaterThan(initial * 3);
    });
  });

  it('дотягивает контур государства-крохи до читаемого', async () => {
    render(<CountrySilhouette code="MT" name="Мальта" />);
    await waitFor(() => {
      expect(pathLength('Карта страны: Мальта')).toBeGreaterThan(400);
    }, { timeout: 15000 });
  });

  it('понимает и UK, и GB', async () => {
    render(<CountrySilhouette code="GB" name="Великобритания" />);
    await waitFor(() => {
      expect(pathLength('Карта страны: Великобритания')).toBeGreaterThan(0);
    });
  });

  it('ничего не рисует для неизвестного кода', () => {
    const { container } = render(<CountrySilhouette code="ZZ" name="Нигде" />);
    expect(container.innerHTML).toBe('');
  });

  it('подписывает частоты по-русски', () => {
    render(
      <CountrySilhouette
        code="AT"
        name="Австрия"
        historyStart="1996-01-01"
        historyEnd="2026-06-01"
        frequencies={['monthly', 'annual']}
      />,
    );
    expect(screen.getByText('мес., год')).toBeTruthy();
    expect(screen.getByText('1996–2026')).toBeTruthy();
  });

  it('показывает площадь и население с русской типографикой', () => {
    render(
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
    expect(normalized).toContain('9 197 213 человек');
    expect(normalized).toContain('2026');
    expect(normalized).toContain('2025');
    const source = screen.getByRole('link', { name: 'Евростат' });
    expect(source.getAttribute('href')).toContain('reg_area3');
  });

  it('без площади и населения не ломается и не рисует пустые строки', () => {
    render(<CountrySilhouette code="AT" name="Австрия" region="Европа" />);
    expect(screen.getByText('Профиль территории')).toBeTruthy();
    expect(screen.queryByText('Площадь')).toBeNull();
    expect(screen.queryByText('Население')).toBeNull();
    expect(screen.queryByText(/Источник:/)).toBeNull();
  });
});

describe('WorldMap tooltip', () => {
  const countries = [{ code: 'DE', slug: 'germany', name: 'Германия' }];

  it('показывает дату наблюдения по-русски', async () => {
    render(
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
    const { container } = render(
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
      const overlay = container.querySelector('path[pointer-events="none"][aria-hidden="true"]');
      // graticule тоже pointer-events none; ищем залитый champagne-оверлей
      const highlights = [...container.querySelectorAll('path[aria-hidden="true"]')]
        .filter((node) => (node.getAttribute('fill') || '').includes('181,141,39'));
      expect(highlights.length).toBeGreaterThan(0);
      expect(highlights[0].getAttribute('d')).toBeTruthy();
      expect(overlay || highlights[0]).toBeTruthy();
    });
  });
});
