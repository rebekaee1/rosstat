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
  it('три верхние группы как у ИПЦ (инфляция за год / к прошлому периоду / индекс)', () => {
    expect(PPI_TOP_GROUPS.map((g) => g.id)).toEqual(['inflation', 'step', 'index']);
    const index = PPI_TOP_GROUPS.find((g) => g.id === 'index');
    expect(index.modes.map((m) => m.mode)).toEqual(['index', 'index-quarterly', 'index-annual']);
  });

  it('дефолтный режим — инфляция за год (помесячный г/г)', () => {
    expect(normalizePpiViewMode(null)).toBe('yoy');
    expect(normalizePpiViewMode('level')).toBe('index');
    // старая годовая (дек-к-дек) редиректит на помесячную инфляцию за год
    expect(normalizePpiViewMode('annual')).toBe('yoy');
  });

  it('инфляция за год и к прошлому периоду — верхние leaf без раскрытия', () => {
    expect(topGroupForMode('yoy')).toBe('inflation');
    expect(topGroupForMode('mom')).toBe('step');
    expect(expandedGroupForMode('yoy')).toBe(null);
    expect(expandedGroupForMode('mom')).toBe(null);
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

  it('canonical redirect derived URL → инфляция за год помесячно', () => {
    expect(ppiCanonicalTarget('ppi-yoy')).toEqual({ parentCode: 'ppi', mode: 'yoy' });
    expect(ppiCanonicalTarget('ppi-annual')).toEqual({ parentCode: 'ppi', mode: 'yoy' });
  });

  it('контент инфляции за год про производителей, не про жильё', () => {
    const { description } = getPpiViewModeContent({ chartMode: 'yoy', indicator: { code: 'ppi' } });
    expect(description).toMatch(/производител/i);
    expect(description).not.toMatch(/новостро|первичн/i);
  });
});
