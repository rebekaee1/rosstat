import { describe, it, expect } from 'vitest';
import {
  CPI_ACTIVE_MODES,
  CPI_TOP_GROUPS,
  defaultSubModeForGroup,
  expandedGroupForMode,
  highlightedTopGroup,
  topGroupForMode,
  visibleCpiViewModes,
} from './cpiViewModeGroups';
import {
  CPI_DISABLED_MODES,
  dataModeForUrlMode,
  isCpiModeDisabled,
  normalizeCpiViewMode,
} from './cpiViewModeResolve';

describe('cpiViewModeGroups', () => {
  it('три верхние группы (рост за период удалён)', () => {
    expect(CPI_TOP_GROUPS.map((g) => g.id)).toEqual([
      'inflation', 'step', 'index',
    ]);
  });

  it('index — порядок: по месяцам, по кварталам, по годам', () => {
    const index = CPI_TOP_GROUPS.find((g) => g.id === 'index');
    expect(index.modes.map((m) => m.mode)).toEqual([
      'index', 'index-quarterly', 'index-annual',
    ]);
  });

  it('step — квартальный шаг подписан «Кв/Кв»', () => {
    const step = CPI_TOP_GROUPS.find((g) => g.id === 'step');
    expect(step.modes.find((m) => m.mode === 'qoq').label).toBe('Кв/Кв');
  });

  it('index и step — все подрежимы активны', () => {
    const index = CPI_TOP_GROUPS.find((g) => g.id === 'index');
    const step = CPI_TOP_GROUPS.find((g) => g.id === 'step');
    for (const m of index.modes) {
      expect(m.disabled).toBeFalsy();
    }
    for (const m of step.modes) {
      expect(m.disabled).toBeFalsy();
    }
  });

  it('нет disabled url-режимов', () => {
    expect(CPI_DISABLED_MODES.size).toBe(0);
    expect(isCpiModeDisabled('yoy')).toBe(false);
    expect(normalizeCpiViewMode('qoq')).toBe('qoq');
  });

  it('dataMode для новых режимов', () => {
    // Г/г считается по годам — декабрь к декабрю (ряд *-annual).
    expect(dataModeForUrlMode('yoy')).toBe('annual');
    expect(dataModeForUrlMode('qoq')).toBe('qoq');
    expect(dataModeForUrlMode('period-monthly')).toBe('period-monthly');
    expect(dataModeForUrlMode('period-weekly')).toBe('period-weekly');
    expect(dataModeForUrlMode('step-weekly')).toBe('weekly');
    // legacy «Рост за период»: квартальная = кв/кв, годовая = г/г.
    expect(dataModeForUrlMode('quarterly')).toBe('qoq');
    expect(dataModeForUrlMode('annual')).toBe('annual');
    expect(dataModeForUrlMode('step-monthly')).toBe('cpi');
    expect(topGroupForMode('yoy')).toBe('step');
    expect(topGroupForMode('period-monthly')).toBe('period');
  });

  it('legacy ?mode=cpi|weekly → step-*', () => {
    expect(normalizeCpiViewMode('cpi')).toBe('step-monthly');
    expect(normalizeCpiViewMode('weekly')).toBe('step-weekly');
  });

  it('defaultSubModeForGroup index → по месяцам', () => {
    expect(defaultSubModeForGroup('index')).toBe('index');
    expect(defaultSubModeForGroup('step')).toBe('step-weekly');
  });

  it('CPI_ACTIVE_MODES включает индекс по периодам', () => {
    expect(CPI_ACTIVE_MODES).toContain('yoy');
    expect(CPI_ACTIVE_MODES).toContain('index-quarterly');
    expect(CPI_ACTIVE_MODES).toContain('index-annual');
  });

  it('visibleCpiViewModes — без «рост за период», с индексом по периодам', () => {
    const modes = visibleCpiViewModes('cpi').map((m) => m.mode);
    expect(modes).not.toContain('period-monthly');
    expect(modes).not.toContain('quarterly');
    expect(modes).toContain('qoq');
    expect(modes).toContain('index-quarterly');
  });

  it('highlightedTopGroup однозначен', () => {
    expect(highlightedTopGroup(null, 'yoy')).toBe('step');
    expect(highlightedTopGroup(null, 'index-quarterly')).toBe('index');
    // «К соотв. периоду пред. года» теперь раскрывающаяся группа (мес/кв/год)
    expect(expandedGroupForMode('inflation')).toBe('inflation');
    expect(expandedGroupForMode('inflation-quarter')).toBe('inflation');
    expect(expandedGroupForMode('index-annual')).toBe('index');
  });
});
