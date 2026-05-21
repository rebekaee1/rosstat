import { describe, it, expect } from 'vitest';
import { VARIANT_GROUPS, findVariantGroup, allVariantMemberCodes } from './indicatorVariants';

describe('indicatorVariants', () => {
  it('each code appears in at most one group', () => {
    const seen = new Set();
    for (const code of allVariantMemberCodes()) {
      expect(seen.has(code), `duplicate variant member: ${code}`).toBe(false);
      seen.add(code);
    }
  });

  it('findVariantGroup resolves primary and derived members', () => {
    expect(findVariantGroup('ipi-yoy')?.label).toBe('Индекс промышленного производства');
    expect(findVariantGroup('exports-qoq')?.label).toBe('Экспорт товаров');
    expect(findVariantGroup('current-account-yoy')?.label).toBe('Сальдо текущего счёта');
    expect(findVariantGroup('unknown-code')).toBeUndefined();
  });

  it('new consolidation groups from 2026-05-17 backlog exist', () => {
    const labels = VARIANT_GROUPS.map((g) => g.label);
    expect(labels).toContain('Индекс промышленного производства');
    expect(labels).toContain('Уровень безработицы');
    expect(labels).toContain('Экспорт товаров');
    expect(labels).toContain('Сальдо текущего счёта');
  });
});
