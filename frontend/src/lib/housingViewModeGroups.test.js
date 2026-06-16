import { describe, it, expect } from 'vitest';
import {
  HOUSING_TOP_GROUPS,
  normalizeHousingViewMode,
  topGroupForMode,
  expandedGroupForMode,
} from './housingViewModeGroups';
import { housingCanonicalTarget, housingIndexGranularity, dataModeForHousingUrlMode } from './housingViewModeResolve';
import { getHousingViewModeContent } from './housingViewModeContent';

describe('housingViewModeGroups', () => {
  it('три верхние группы как у ИПЦ: к соотв. периоду + к прошлому периоду + индекс', () => {
    expect(HOUSING_TOP_GROUPS.map((g) => g.id)).toEqual(['inflation', 'step', 'index']);
    const inflation = HOUSING_TOP_GROUPS.find((g) => g.id === 'inflation');
    expect(inflation.leafMode).toBe('yoy');
    expect(inflation.label).toBe('К соотв. периоду пред. года');
    const step = HOUSING_TOP_GROUPS.find((g) => g.id === 'step');
    expect(step.modes.map((m) => m.mode)).toEqual(['qoq', 'yoy-annual']);
    const index = HOUSING_TOP_GROUPS.find((g) => g.id === 'index');
    expect(index.modes.map((m) => m.mode)).toEqual(['index', 'index-annual']);
  });

  it('индекс — раскрывающаяся группа: по кварталам (база) + по годам', () => {
    expect(topGroupForMode('index')).toBe('index');
    expect(topGroupForMode('index-annual')).toBe('index');
    expect(expandedGroupForMode('index-annual')).toBe('index');
    expect(housingIndexGranularity('index-annual')).toBe('year');
    expect(housingIndexGranularity('index')).toBe(null);
    expect(dataModeForHousingUrlMode('index-annual')).toBe('index');
  });

  it('дефолтный режим — к соотв. периоду пред. года (квартальная YoY)', () => {
    expect(normalizeHousingViewMode(null)).toBe('yoy');
    expect(normalizeHousingViewMode('level')).toBe('index');
    expect(topGroupForMode('yoy')).toBe('inflation');
    // yoy — лист дефолтной группы, не раскрываем подрежимы
    expect(expandedGroupForMode('yoy')).toBe(null);
    expect(dataModeForHousingUrlMode('yoy')).toBe('yoy');
  });

  it('Г/г «по годам» (yoy-annual) — годовой ряд в группе «К прошлому периоду»', () => {
    expect(topGroupForMode('qoq')).toBe('step');
    expect(topGroupForMode('yoy-annual')).toBe('step');
    expect(expandedGroupForMode('yoy-annual')).toBe('step');
    expect(dataModeForHousingUrlMode('yoy-annual')).toBe('annual');
  });

  it('лейбл «к прошлому периоду» унифицирован: Кв/Кв (не К/к)', () => {
    const step = HOUSING_TOP_GROUPS.find((g) => g.id === 'step');
    const qoq = step.modes.find((m) => m.mode === 'qoq');
    expect(qoq.label).toBe('Кв/Кв');
  });

  it('canonical redirect derived URL', () => {
    expect(housingCanonicalTarget('housing-qoq-primary')).toEqual({
      parentCode: 'housing-price-primary',
      mode: 'qoq',
    });
  });

  it('контент к соотв. периоду — не про ИПЦ, годовой Г/г — отдельный', () => {
    const yoy = getHousingViewModeContent({
      chartMode: 'yoy',
      indicator: { code: 'housing-price-primary' },
    });
    expect(yoy.description).toMatch(/новостро|первичн/i);
    expect(yoy.description).not.toMatch(/потребительск/i);
    const annual = getHousingViewModeContent({
      chartMode: 'annual',
      indicator: { code: 'housing-price-primary' },
    });
    expect(annual.description).toMatch(/год к году|на конец года/i);
  });
});
