import { describe, it, expect } from 'vitest';
import { getViewModeContentEn } from './viewModeContent.en';
import {
  resolveViewModeContent,
  resolveChartTitle,
  resolveTableTitle,
} from './resolveViewModeCopy';

const CPI_ARGS = {
  chartMode: 'inflation',
  safeViewMode: 'inflation',
  isPriceCategory: true,
  isHousingFamily: false,
  isPpiFamily: false,
  isCbrTermSliceFamily: false,
  isUnemploymentFamily: false,
  indicator: { code: 'cpi', name: 'Consumer price index', description: 'EN from API' },
};

describe('getViewModeContentEn', () => {
  it('CPI inflation description is English (not «Инфляция»)', () => {
    const out = getViewModeContentEn(CPI_ARGS);
    expect(out.description).toMatch(/Inflation/i);
    expect(out.description).not.toMatch(/Инфляция/);
    expect(out.methodology).not.toMatch(/Инфляц/);
  });
});

const HOUSING_ARGS = {
  chartMode: 'yoy',
  safeViewMode: 'yoy',
  isPriceCategory: false,
  isHousingFamily: true,
  isPpiFamily: false,
  isCbrTermSliceFamily: false,
  isUnemploymentFamily: false,
  indicator: {
    code: 'housing-price-primary',
    name: 'Primary housing price index',
  },
};

const PPI_ARGS = {
  chartMode: 'yoy',
  safeViewMode: 'yoy',
  isPriceCategory: false,
  isHousingFamily: false,
  isPpiFamily: true,
  isCbrTermSliceFamily: false,
  isUnemploymentFamily: false,
  indicator: { code: 'ppi', name: 'Producer price index' },
};

describe('resolveViewModeContent locale branch', () => {
  it('locale=en routes to EN CPI copy', () => {
    const out = resolveViewModeContent('en', CPI_ARGS);
    expect(out.description).toMatch(/Inflation/i);
    expect(out.description).not.toMatch(/Инфляция/);
  });

  it('locale=ru keeps Russian CPI copy', () => {
    const out = resolveViewModeContent('ru', CPI_ARGS);
    expect(String(out.description)).toMatch(/Инфляц|инфляц|цен/i);
  });

  it('EN chart / table titles for CPI inflation', () => {
    expect(resolveChartTitle('en', CPI_ARGS)).toMatch(/Inflation/i);
    expect(resolveChartTitle('en', CPI_ARGS)).not.toMatch(/Инфляц/);
    expect(resolveTableTitle('en', CPI_ARGS)).toMatch(/Historical|history|Inflation/i);
    expect(resolveTableTitle('en', CPI_ARGS)).not.toMatch(/Инфляц|Исторические/);
  });

  it('EN housing yoy chart title and methodology (no Cyrillic)', () => {
    const out = resolveViewModeContent('en', HOUSING_ARGS);
    const chart = resolveChartTitle('en', HOUSING_ARGS);
    expect(chart).toMatch(/primary housing|same period/i);
    expect(chart).not.toMatch(/[А-Яа-яЁё]/);
    expect(String(out.description)).toMatch(/new-build|primary|quarter/i);
    expect(String(out.description)).not.toMatch(/[А-Яа-яЁё]/);
    expect(String(out.methodology)).not.toMatch(/[А-Яа-яЁё]/);
    expect(resolveTableTitle('en', HOUSING_ARGS)).toMatch(/Historical/i);
  });

  it('EN PPI yoy chart title and methodology (no Cyrillic)', () => {
    const out = resolveViewModeContent('en', PPI_ARGS);
    const chart = resolveChartTitle('en', PPI_ARGS);
    expect(chart).toMatch(/producer|Inflation/i);
    expect(chart).not.toMatch(/[А-Яа-яЁё]/);
    expect(String(out.description)).toMatch(/producer|wholesale|industrial/i);
    expect(String(out.description)).not.toMatch(/[А-Яа-яЁё]/);
    expect(String(out.methodology)).not.toMatch(/[А-Яа-яЁё]/);
  });
});
