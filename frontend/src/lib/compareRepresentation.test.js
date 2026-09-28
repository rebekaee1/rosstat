import { describe, it, expect } from 'vitest';
import {
  REP_LEVEL, REP_POP, REP_YOY,
  compareRepresentationsFor, resolveCompareSeries, applyCompareTransform,
  isIndexableBase, commonIndexBase, rebaseToHundred, requiresRebasedPriceIndex, resolveStepOverride,
  worldCompareRepresentationsFor, worldCompareTransformFor,
} from './compareRepresentation';

describe('compareRepresentation — resolver', () => {
  it('CPI: level→cumulative, pop→sub100, yoy→derived code', () => {
    const ind = { code: 'cpi', unit: '%' };
    expect(resolveCompareSeries(ind, REP_LEVEL)).toMatchObject({
      code: 'cpi', transform: 'cpiCumulative', unit: 'индекс',
    });
    expect(resolveCompareSeries(ind, REP_POP)).toMatchObject({
      code: 'cpi', transform: 'sub100', unit: '%',
    });
    expect(resolveCompareSeries(ind, REP_YOY)).toMatchObject({
      code: 'cpi-yoy', transform: null, unit: '%',
    });
  });

  it('CPI-food yoy maps to cpi-food-yoy', () => {
    expect(resolveCompareSeries({ code: 'cpi-food' }, REP_YOY).code).toBe('cpi-food-yoy');
  });

  it('PPI: pop is client m/m transform on index; yoy is derived', () => {
    expect(resolveCompareSeries({ code: 'ppi' }, REP_POP)).toMatchObject({
      code: 'ppi', transform: 'mom', unit: '%',
    });
    expect(resolveCompareSeries({ code: 'ppi' }, REP_YOY).code).toBe('ppi-yoy');
    expect(resolveCompareSeries({ code: 'ppi' }, REP_LEVEL)).toMatchObject({
      code: 'ppi', transform: null, unit: 'индекс',
    });
  });

  it('housing: pop→qoq_adjacent derived, yoy→yoy derived, per slice', () => {
    expect(resolveCompareSeries({ code: 'housing-price-primary' }, REP_POP).code)
      .toBe('housing-qoq-primary');
    expect(resolveCompareSeries({ code: 'housing-price-secondary' }, REP_YOY).code)
      .toBe('housing-yoy-secondary');
  });

  it('generic family: level→native, pop→first pop mode, yoy→first yoy mode', () => {
    const spec = resolveCompareSeries({ code: 'auto-loan-rate' }, REP_POP);
    expect(spec.code).toBe('auto-loan-rate-mom');
    expect(resolveCompareSeries({ code: 'auto-loan-rate' }, REP_YOY).code)
      .toBe('auto-loan-rate-yoy');
    expect(resolveCompareSeries({ code: 'auto-loan-rate' }, REP_LEVEL).code)
      .toBe('auto-loan-rate');
  });

  it('unknown code falls back to level-only', () => {
    const ind = { code: 'made-up-xyz', unit: 'млн руб' };
    const reps = compareRepresentationsFor(ind);
    expect(reps.map((r) => r.id)).toEqual([REP_LEVEL]);
    expect(resolveCompareSeries(ind, REP_YOY).repId).toBe(REP_LEVEL);
  });

  it('representation options are in canonical order and only available ones', () => {
    const reps = compareRepresentationsFor({ code: 'cpi' });
    expect(reps.map((r) => r.id)).toEqual([REP_LEVEL, REP_POP, REP_YOY]);
  });
});

describe('compareRepresentation — transforms', () => {
  it('sub100 subtracts 100', () => {
    const out = applyCompareTransform([{ date: '2020-01-01', value: 100.5 }], 'sub100');
    expect(out[0].value).toBeCloseTo(0.5);
  });

  it('null transform is identity', () => {
    const pts = [{ date: '2020-01-01', value: 5 }];
    expect(applyCompareTransform(pts, null)).toBe(pts);
  });

  it('mom computes month-over-month percent from index level', () => {
    const out = applyCompareTransform([
      { date: '2020-01-01', value: 100 },
      { date: '2020-02-01', value: 101 },
    ], 'mom');
    expect(out).toHaveLength(1);
    expect(out[0].value).toBeCloseTo(1.0);
  });

  it('cpiCumulative builds a base-100 index at 2000-01', () => {
    const out = applyCompareTransform([
      { date: '2000-01-01', value: 100 },
      { date: '2000-02-01', value: 101 },
    ], 'cpiCumulative');
    const base = out.find((p) => p.date === '2000-01-01');
    const feb = out.find((p) => p.date === '2000-02-01');
    expect(base.value).toBe(100);
    expect(feb.value).toBeCloseTo(101);
  });

  it('empty input yields empty output', () => {
    expect(applyCompareTransform([], 'mom')).toEqual([]);
  });

  it('world monthly series supports adjacent and year-over-year comparisons', () => {
    expect(worldCompareRepresentationsFor({
      frequency: 'monthly',
      conceptSlug: 'hicp-index',
    }).map((item) => item.id)).toEqual([REP_LEVEL, REP_POP, REP_YOY]);
    const points = [
      { date: '2024-01-01', value: 100 },
      { date: '2024-02-01', value: 101 },
      { date: '2025-01-01', value: 110 },
    ];
    expect(applyCompareTransform(
      points,
      worldCompareTransformFor(REP_POP, 'monthly'),
    )).toEqual([{ date: '2024-02-01', value: 1 }]);
    expect(applyCompareTransform(
      points,
      worldCompareTransformFor(REP_YOY, 'monthly'),
    )).toEqual([{ date: '2025-01-01', value: 10 }]);
  });

  it('signed budget concept remains level-only', () => {
    expect(worldCompareRepresentationsFor({
      frequency: 'annual',
      conceptSlug: 'budget-balance-gdp',
    }).map((item) => item.id)).toEqual([REP_LEVEL]);
  });
});

describe('compareRepresentation — index base guard', () => {
  it('только положительная конечная база индексируется', () => {
    expect(isIndexableBase(120)).toBe(true);
    expect(isIndexableBase(0.5)).toBe(true);
    expect(isIndexableBase(0)).toBe(false); // деление на ноль
    expect(isIndexableBase(-3005)).toBe(false); // сальдо/счёт → переворот знака
    expect(isIndexableBase(null)).toBe(false);
    expect(isIndexableBase(undefined)).toBe(false);
    expect(isIndexableBase(NaN)).toBe(false);
    expect(isIndexableBase(Infinity)).toBe(false);
  });

  it('знакопеременный ряд не индексируется даже при плюсовой базе', () => {
    // Дефицит бюджета: база в профицитном квартале, дальше минус — деление
    // переворачивает знак и рисует «минус 230 пунктов от старта».
    expect(isIndexableBase(701.3, {
      unit: 'млрд руб.', repId: REP_LEVEL, values: [701.3, 210.5, -1616.4],
    })).toBe(false);
    // Ряд одного знака индексируется как прежде.
    expect(isIndexableBase(701.3, {
      unit: 'млрд руб.', repId: REP_LEVEL, values: [701.3, 210.5, 980.1],
    })).toBe(true);
  });

  it('В-12: %-ряды и темповые представления не индексируются к базе-100', () => {
    // Инфляция 5% — темп, а не уровень: «= 100 пунктов» смыслово неверно.
    expect(isIndexableBase(5, { unit: '%', repId: REP_LEVEL })).toBe(false);
    expect(isIndexableBase(8.6, { unit: '‰' })).toBe(false);
    expect(isIndexableBase(17.2, { unit: '% ВВП', repId: REP_LEVEL })).toBe(false);
    expect(isIndexableBase(6.34, { unit: 'изменение за год, %', repId: REP_LEVEL })).toBe(false);
    // Представления «к прошлому периоду» / «к году» — тоже темпы.
    expect(isIndexableBase(120, { unit: 'млрд руб.', repId: REP_POP })).toBe(false);
    expect(isIndexableBase(120, { unit: 'млрд руб.', repId: REP_YOY })).toBe(false);
    // Обычный уровень остаётся индексируемым.
    expect(isIndexableBase(120, { unit: 'млрд руб.', repId: REP_LEVEL })).toBe(true);
    expect(isIndexableBase(2100, { unit: 'bn $', repId: REP_LEVEL })).toBe(true);
    expect(isIndexableBase(120, { unit: 'индекс' })).toBe(true);
  });

  it('forces a shared base for price indices with different base years', () => {
    const germany = { isWorld: true, ind: { conceptSlug: 'hicp-index' }, unit: 'индекс 2015=100' };
    const unitedStates = { isWorld: true, ind: { conceptSlug: 'hicp-index' }, unit: 'индекс 1982–84=100' };
    const france = { isWorld: true, ind: { conceptSlug: 'hicp-index' }, unit: 'индекс 2015=100' };
    expect(requiresRebasedPriceIndex([germany, unitedStates])).toBe(true);
    expect(requiresRebasedPriceIndex([germany, france])).toBe(false);
    expect(requiresRebasedPriceIndex([germany])).toBe(false);
  });

  it('rebaseToHundred приводит к базе-100 без выбросов на валидной базе', () => {
    expect(rebaseToHundred(120, 100)).toBeCloseTo(120);
    expect(rebaseToHundred(50, 200)).toBeCloseTo(25);
    // на невалидной базе не вызывается — но математически guard выше её отсекает
    expect(isIndexableBase(0)).toBe(false);
  });

  it('uses the first shared actual date, even when one history starts earlier', () => {
    const dates = ['2020-01-01', '2021-01-01', '2022-01-01'];
    const maps = [
      new Map([['2020-01-01', 100], ['2021-01-01', 120], ['2022-01-01', 130]]),
      new Map([['2021-01-01', 200], ['2022-01-01', 240]]),
      new Map([['2022-01-01', 5]]),
    ];
    const series = [
      { unit: 'bn $', rep: REP_LEVEL },
      { unit: 'bn $', rep: REP_LEVEL },
      { unit: '%', rep: REP_LEVEL },
    ];
    const base = commonIndexBase(maps, series, dates);
    expect(base.date).toBe('2021-01-01');
    expect(base.candidates).toEqual([0, 1]);
    expect(base.bases).toEqual([120, 200, null]);
    expect(rebaseToHundred(maps[0].get(base.date), base.bases[0])).toBe(100);
    expect(rebaseToHundred(maps[1].get(base.date), base.bases[1])).toBe(100);
  });

  it('does not invent a shared base when observation dates do not overlap', () => {
    const dates = ['2020-01-01', '2021-01-01'];
    const maps = [
      new Map([['2020-01-01', 100]]),
      new Map([['2021-01-01', 200]]),
    ];
    const base = commonIndexBase(maps, [
      { unit: 'bn $', rep: REP_LEVEL },
      { unit: 'bn $', rep: REP_LEVEL },
    ], dates);
    expect(base.date).toBeNull();
    expect(base.candidates).toEqual([0, 1]);
  });
});

describe('compareRepresentation — resolveStepOverride (третий слой)', () => {
  const wages = { code: 'wages-nominal', alternate_frequencies: { annual: 'wages-nominal-annual' } };

  it('подключает реальный годовой ряд вместо клиентского усреднения на level', () => {
    expect(resolveStepOverride(wages, REP_LEVEL, 'year')).toBe('wages-nominal-annual');
  });

  it('не применяется на pop/yoy представлениях — там уже generic-семья своей глубины', () => {
    expect(resolveStepOverride(wages, REP_POP, 'year')).toBeNull();
    expect(resolveStepOverride(wages, REP_YOY, 'year')).toBeNull();
  });

  it('не применяется при step=auto или отсутствующем шаге', () => {
    expect(resolveStepOverride(wages, REP_LEVEL, 'auto')).toBeNull();
    expect(resolveStepOverride(wages, REP_LEVEL, null)).toBeNull();
  });

  it('нет alternate_frequencies на нужную частоту → null (клиентское усреднение как раньше)', () => {
    expect(resolveStepOverride(wages, REP_LEVEL, 'month')).toBeNull();
    expect(resolveStepOverride(wages, REP_LEVEL, 'quarter')).toBeNull();
    expect(resolveStepOverride({ code: 'foo' }, REP_LEVEL, 'year')).toBeNull();
  });

  it('индикатор без alternate_frequencies вообще — null', () => {
    expect(resolveStepOverride({ code: 'cpi' }, REP_LEVEL, 'year')).toBeNull();
    expect(resolveStepOverride(null, REP_LEVEL, 'year')).toBeNull();
  });

  it('квартальный первичный ряд с alternate monthly (exports) — Шаг=Месяц берёт настоящий месячный ряд', () => {
    const exports = { code: 'exports', alternate_frequencies: { monthly: 'exports-monthly' } };
    expect(resolveStepOverride(exports, REP_LEVEL, 'month')).toBe('exports-monthly');
  });
});
