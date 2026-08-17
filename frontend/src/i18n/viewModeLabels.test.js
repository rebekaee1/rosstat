import { describe, expect, it } from 'vitest';
import { localizeSource, localizeViewModeLabel } from './viewModeLabels.js';

describe('localizeViewModeLabel', () => {
  it('keeps Russian on ru', () => {
    expect(localizeViewModeLabel('Год к году', 'ru')).toBe('Год к году');
  });

  it('translates picker labels on en', () => {
    expect(localizeViewModeLabel('Год к году', 'en')).toBe('Year on year');
    expect(localizeViewModeLabel('К прошлому периоду', 'en')).toBe('Vs previous period');
    expect(localizeViewModeLabel('Режим динамики цен', 'en')).toBe('Режим динамики цен');
  });
});

describe('localizeSource', () => {
  it('maps Rosstat on en', () => {
    expect(localizeSource('Росстат', 'en')).toBe('Rosstat');
    expect(localizeSource('Банк России', 'en')).toBe('Bank of Russia');
    expect(localizeSource('Минфин', 'en')).toBe('Ministry of Finance');
    expect(localizeSource('Евростат', 'en')).toBe('Eurostat');
    expect(localizeSource('Банк Японии', 'en')).toBe('Bank of Japan');
  });

  it('keeps Russian on ru', () => {
    expect(localizeSource('Росстат', 'ru')).toBe('Росстат');
    expect(localizeSource('Евростат', 'ru')).toBe('Евростат');
  });
});
