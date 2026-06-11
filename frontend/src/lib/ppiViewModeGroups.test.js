import { describe, it, expect } from 'vitest';
import {
  PPI_TOP_GROUPS,
  normalizePpiViewMode,
  topGroupForMode,
  expandedGroupForMode,
} from './ppiViewModeGroups';
import { ppiCanonicalTarget, ppiIndexGranularity, dataModeForPpiUrlMode } from './ppiViewModeResolve';
import { getPpiViewModeContent } from './ppiViewModeContent';

describe('ppiViewModeGroups', () => {
  it('три верхние группы как у ИПЦ (к соотв. периоду пред. года / к прошлому периоду / индекс)', () => {
    expect(PPI_TOP_GROUPS.map((g) => g.id)).toEqual(['inflation', 'step', 'index']);
    const inflation = PPI_TOP_GROUPS.find((g) => g.id === 'inflation');
    expect(inflation.label).toBe('К соотв. периоду пред. года');
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

  it('инфляция за год — leaf; «к прошлому периоду» раскрывается в м/м и кв/кв', () => {
    expect(topGroupForMode('yoy')).toBe('inflation');
    expect(topGroupForMode('mom')).toBe('step');
    expect(topGroupForMode('qoq')).toBe('step');
    expect(expandedGroupForMode('yoy')).toBe(null);
    expect(expandedGroupForMode('mom')).toBe('step');
    expect(expandedGroupForMode('qoq')).toBe('step');
    expect(dataModeForPpiUrlMode('qoq')).toBe('qoq');
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
