/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Chip from './Chip';
import { ChipLink } from './ChipGroup';
import DeltaBadge from './DeltaBadge';
import Sparkline from './Sparkline';
import { ChartSkeleton } from './Skeleton';
import { chipTitleFor } from '../lib/chipLabel';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('DS9: чип', () => {
  it('короткая подпись остаётся в span-подписи без title', () => {
    render(<Chip>Значения</Chip>);
    const chip = screen.getByRole('button', { name: 'Значения' });
    expect(chip.querySelector('.fe-chip__label').textContent).toBe('Значения');
    expect(chip.hasAttribute('title')).toBe(false);
  });

  it('длинная подпись получает title с полным именем: на экране она в две строки, а не обрезана', () => {
    const full = 'Баланс бюджета сектора государственного управления';
    render(<Chip>{full}</Chip>);
    const chip = screen.getByRole('button', { name: full });
    expect(chip.getAttribute('title')).toBe(full);
    expect(chip.querySelector('.fe-chip__label')).toBeTruthy();
  });

  it('явный title побеждает, а нестроковое содержимое (иконка + текст) не оборачивается', () => {
    render(<Chip title="Своя подсказка"><svg data-testid="icon" /> Скачать</Chip>);
    const chip = screen.getByRole('button');
    expect(chip.getAttribute('title')).toBe('Своя подсказка');
    expect(chip.querySelector('.fe-chip__label')).toBeNull();
    expect(screen.getByTestId('icon')).toBeTruthy();
  });

  it('ссылка-чип ведёт себя так же и помечает текущую страницу', () => {
    const full = 'Государственный долг сектора государственного управления';
    render(<MemoryRouter><ChipLink to="/x" active>{full}</ChipLink></MemoryRouter>);
    const link = screen.getByRole('link');
    expect(link.getAttribute('aria-current')).toBe('page');
    expect(link.getAttribute('title')).toBe(full);
    expect(link.className).toContain('is-active');
  });

  it('chipTitleFor: порог 22 знака, пробелы по краям не считаются', () => {
    expect(chipTitleFor('Короткий', undefined)).toBeUndefined();
    expect(chipTitleFor(`  ${'а'.repeat(22)}  `, undefined)).toBe('а'.repeat(22));
    expect(chipTitleFor(['a', 'b'], undefined)).toBeUndefined();
    expect(chipTitleFor('x', '')).toBe('');
  });
});

describe('DS9: плашка изменения', () => {
  it('рост рисуется ▲, падение ▼, отсутствие изменения тире, смысл задаёт класс тона', () => {
    const { container, rerender } = render(<DeltaBadge delta={3} polarity="up-good">+3,0</DeltaBadge>);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('▲');
    expect(container.firstChild.className).toContain('fe-tone--good');
    rerender(<DeltaBadge delta={-3} polarity="up-good">−3,0</DeltaBadge>);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('▼');
    expect(container.firstChild.className).toContain('fe-tone--bad');
    rerender(<DeltaBadge delta={0}>без изменений</DeltaBadge>);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('–');
    expect(container.firstChild.className).toContain('fe-tone--flat');
  });

  it('plain убирает плашку для плотных таблиц', () => {
    const { container } = render(<DeltaBadge delta={1} plain>+1</DeltaBadge>);
    expect(container.firstChild.className).toContain('fe-delta-badge--plain');
  });
});

describe('DS9: спарклайн', () => {
  function stubBrowser(observe) {
    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb, options) { this.options = options; observe(options); }
      observe() {}
      disconnect() {}
    });
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  }

  it('начинает рисовать за 160 px до экрана, чтобы при быстрой прокрутке не было пустой карточки', () => {
    const seen = [];
    stubBrowser((options) => seen.push(options));
    render(<Sparkline points={[1, 2, 3, 2]} trend="up" />);
    expect(seen[0].rootMargin).toBe('160px 0px');
    expect(seen[0].threshold).toBeLessThan(0.1);
  });

  it('с одной точкой по-прежнему ничего не рисует', () => {
    stubBrowser(() => {});
    const { container } = render(<Sparkline points={[1]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe('DS6: каркас графика', () => {
  it('по умолчанию 280 / 390 / 480 тем же шагом, что у настоящего графика', () => {
    const { container } = render(<ChartSkeleton />);
    const plot = container.querySelector('.rounded-xl');
    expect(plot.className).toContain('h-[280px]');
    expect(plot.className).toContain('sm:h-[390px]');
    expect(plot.className).toContain('lg:h-[480px]');
  });
});
