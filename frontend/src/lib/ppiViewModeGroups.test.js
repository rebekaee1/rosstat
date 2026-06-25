import { describe, it, expect } from 'vitest';
import {
  PPI_TOP_GROUPS,
  normalizePpiViewMode,
  topGroupForMode,
  expandedGroupForMode,
} from './ppiViewModeGroups';
import {
  ppiCanonicalTarget, ppiIndexGranularity, ppiYoyGranularity, dataModeForPpiUrlMode,
} from './ppiViewModeResolve';
import { getPpiViewModeContent } from './ppiViewModeContent';

describe('ppiViewModeGroups', () => {
  it('три верхние группы как у ИПЦ (к соотв. периоду пред. года / к прошлому периоду / индекс)', () => {
    expect(PPI_TOP_GROUPS.map((g) => g.id)).toEqual(['inflation', 'step', 'index']);
    const inflation = PPI_TOP_GROUPS.find((g) => g.id === 'inflation');
    expect(inflation.label).toBe('К соотв. периоду пред. года');
    expect(inflation.modes.map((m) => m.mode)).toEqual(['yoy', 'yoy-quarter', 'yoy-year']);
    const index = PPI_TOP_GROUPS.find((g) => g.id === 'index');
    expect(index.modes.map((m) => m.mode)).toEqual(['index', 'index-quarterly', 'index-annual']);
    const step = PPI_TOP_GROUPS.find((g) => g.id === 'step');
    expect(step.modes.map((m) => m.mode)).toEqual(['mom', 'qoq', 'annual']);
  });

  it('дефолтный режим — к соотв. периоду пред. года (помесячный г/г)', () => {
    expect(normalizePpiViewMode(null)).toBe('yoy');
    expect(normalizePpiViewMode('level')).toBe('index');
    // годовая «декабрь к декабрю» — собственный режим Г/г в «К прошлому периоду»
    expect(normalizePpiViewMode('annual')).toBe('annual');
    expect(expandedGroupForMode('annual')).toBe('step');
  });

  it('«к соотв. периоду пред. года» — многоуровневая (мес/кв/год); «к прошлому периоду» — м/м·кв/кв·г/г', () => {
    expect(topGroupForMode('yoy')).toBe('inflation');
    expect(topGroupForMode('yoy-quarter')).toBe('inflation');
    expect(topGroupForMode('yoy-year')).toBe('inflation');
    expect(topGroupForMode('mom')).toBe('step');
    expect(topGroupForMode('qoq')).toBe('step');
    expect(expandedGroupForMode('yoy')).toBe('inflation');
    expect(expandedGroupForMode('yoy-quarter')).toBe('inflation');
    expect(expandedGroupForMode('mom')).toBe('step');
    expect(expandedGroupForMode('qoq')).toBe('step');
    expect(dataModeForPpiUrlMode('qoq')).toBe('qoq');
    // подрежимы г/г грузят тот же помесячный ряд, прорежённый по периоду
    expect(dataModeForPpiUrlMode('yoy-quarter')).toBe('yoy');
    expect(dataModeForPpiUrlMode('yoy-year')).toBe('yoy');
    expect(ppiYoyGranularity('yoy-quarter')).toBe('quarter');
    expect(ppiYoyGranularity('yoy-year')).toBe('year');
    expect(ppiYoyGranularity('yoy')).toBe(null);
  });

  it('индекс — раскрывающаяся группа с гранулярностью', () => {
    expect(topGroupForMode('index')).toBe('index');
    expect(topGroupForMode('index-quarterly')).toBe('index');
    expect(expandedGroupForMode('index-annual')).toBe('index');
    expect(ppiIndexGranularity('index-quarterly')).toBe('quarter');
    expect(ppiIndexGranularity('index-annual')).toBe('year');
    expect(ppiIndexGranularity('index')).toBe(null);
    // оба подрежима грузят тот же ряд индекса
    expect(dataModeForPpiUrlMode('index-quarterly')).toBe('index');
    expect(dataModeForPpiUrlMode('index-annual')).toBe('index');
  });

  it('canonical redirect derived URL → карточка ppi с режимом', () => {
    expect(ppiCanonicalTarget('ppi-yoy')).toEqual({ parentCode: 'ppi', mode: 'yoy' });
    expect(ppiCanonicalTarget('ppi-annual')).toEqual({ parentCode: 'ppi', mode: 'annual' });
  });

  it('контент инфляции за год про производителей, не про жильё', () => {
    const { description } = getPpiViewModeContent({ chartMode: 'yoy', indicator: { code: 'ppi' } });
    expect(description).toMatch(/производител/i);
    expect(description).not.toMatch(/новостро|первичн/i);
  });
});
