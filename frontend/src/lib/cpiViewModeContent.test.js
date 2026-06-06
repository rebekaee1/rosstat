import { describe, it, expect } from 'vitest';
import { getViewModeContent } from './cpiViewModeContent.jsx';

describe('getViewModeContent', () => {
  // ============================================================
  // Anti-leak: для не-CPI индикаторов (isPriceCategory=false) функция
  // НЕ должна возвращать CPI-specific блоки (ANNUAL/QUARTERLY/WEEKLY).
  // Регрессия после Phase 2 (wages-nominal-annual): без guard'а на
  // wages-nominal?mode=annual подтекал текст «Годовая инфляция декабрь
  // к декабрю» из CPI-семейства. См. ADR-0006 «Subsequent additions».
  // ============================================================

  const wagesIndicator = {
    description: 'Среднемесячная номинальная зарплата работников.',
    methodology: 'Источник — Росстат, форма П-4.',
  };

  it('annual mode на не-CPI индикаторе → fallback на indicator.{description, methodology}', () => {
    const out = getViewModeContent({
      chartMode: 'cpi',
      safeViewMode: 'annual',
      isPriceCategory: false,
      indicator: wagesIndicator,
    });
    expect(out.description).toBe(wagesIndicator.description);
    expect(out.methodology).toBe(wagesIndicator.methodology);
  });

  it('quarterly mode на не-CPI индикаторе → fallback на indicator', () => {
    const out = getViewModeContent({
      chartMode: 'cpi',
      safeViewMode: 'quarterly',
      isPriceCategory: false,
      indicator: wagesIndicator,
    });
    expect(out.description).toBe(wagesIndicator.description);
    expect(out.methodology).toBe(wagesIndicator.methodology);
  });

  it('weekly mode на не-CPI индикаторе → fallback на indicator', () => {
    const out = getViewModeContent({
      chartMode: 'cpi',
      safeViewMode: 'weekly',
      isPriceCategory: false,
      indicator: wagesIndicator,
    });
    expect(out.description).toBe(wagesIndicator.description);
    expect(out.methodology).toBe(wagesIndicator.methodology);
  });

  it('index mode на не-CPI индикаторе → fallback на indicator', () => {
    const out = getViewModeContent({
      chartMode: 'cpi',
      safeViewMode: 'index',
      isPriceCategory: false,
      indicator: wagesIndicator,
    });
    expect(out.description).toBe(wagesIndicator.description);
    expect(out.methodology).toBe(wagesIndicator.methodology);
  });

  it('inflation chartMode на не-CPI индикаторе → fallback (не CPI-блок)', () => {
    const out = getViewModeContent({
      chartMode: 'inflation',
      safeViewMode: 'inflation',
      isPriceCategory: false,
      indicator: wagesIndicator,
    });
    expect(out.description).toBe(wagesIndicator.description);
    expect(out.methodology).toBe(wagesIndicator.methodology);
  });

  // ============================================================
  // CPI-индикаторы (isPriceCategory=true) — продолжают получать
  // mode-specific контент, как и раньше.
  // ============================================================

  const cpiIndicator = {
    description: 'fallback description',
    methodology: 'fallback methodology',
  };

  it('annual mode на CPI → CPI ANNUAL block, не fallback', () => {
    const out = getViewModeContent({
      chartMode: 'cpi',
      safeViewMode: 'annual',
      isPriceCategory: true,
      indicator: cpiIndicator,
    });
    expect(out.description).toMatch(/Годовая инфляция/);
    expect(out.description).not.toBe(cpiIndicator.description);
  });

  it('inflation chartMode на CPI → INFLATION block', () => {
    const out = getViewModeContent({
      chartMode: 'inflation',
      safeViewMode: 'inflation',
      isPriceCategory: true,
      indicator: cpiIndicator,
    });
    expect(out.description).toMatch(/Накопленная инфляция/);
  });

  it('step-weekly на CPI → недельный блок', () => {
    const out = getViewModeContent({
      chartMode: 'weekly',
      safeViewMode: 'step-weekly',
      isPriceCategory: true,
      indicator: { ...cpiIndicator, code: 'cpi' },
    });
    expect(out.description).toMatch(/неделя к неделе/);
  });

  it('step-monthly на CPI → м/м блок', () => {
    const out = getViewModeContent({
      chartMode: 'cpi',
      safeViewMode: 'step-monthly',
      isPriceCategory: true,
      indicator: cpiIndicator,
    });
    expect(out.description).toMatch(/предыдущим месяцем/);
  });

  it('step-weekly на cpi-food → food-specific block', () => {
    const out = getViewModeContent({
      chartMode: 'weekly',
      safeViewMode: 'step-weekly',
      isPriceCategory: true,
      indicator: { ...cpiIndicator, code: 'cpi-food' },
    });
    expect(out.description).toMatch(/продовольственные/);
  });

  it('inflation на cpi-food → текст про продовольствие, не общую корзину', () => {
    const out = getViewModeContent({
      chartMode: 'inflation',
      safeViewMode: 'inflation',
      isPriceCategory: true,
      indicator: { ...cpiIndicator, code: 'cpi-food' },
    });
    expect(out.description).toMatch(/продовольственные товары/);
    expect(out.description).toMatch(/скользящие 12 месяцев/);
    expect(out.description).not.toMatch(/потребительские цены за последний год/);
  });

  // ============================================================
  // Безопасный fallback: пустые поля indicator не ломают функцию.
  // ============================================================

  it('пустой indicator → пустые строки в fallback', () => {
    const out = getViewModeContent({
      chartMode: 'cpi',
      safeViewMode: 'level',
      isPriceCategory: false,
      indicator: undefined,
    });
    expect(out.description).toBe('');
    expect(out.methodology).toBe('');
  });
});
