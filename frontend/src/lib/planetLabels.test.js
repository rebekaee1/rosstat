import { describe, expect, it } from 'vitest';
import { bindPlanetCountries, loadPlanetFeatures } from './planetGeometry';
import { WORLD_FEATURES } from './worldTopology';
import { buildPlanetLabels, layoutPlanetLabels, packPlanetLabelAtlas, wrapPlanetLabel } from './planetLabels';

const candidate = (code, overrides = {}) => ({
  id: code, code, area: 0.01, x: 200, y: 180, depth: 0.5, facing: 1,
  width: 70, height: 20, ...overrides,
});
const viewport = { width: 500, height: 350 };
const metricEntries = bindPlanetCountries([
  { code: 'UK', name: 'Великобритания', name_en: 'United Kingdom' },
], WORLD_FEATURES);
const metricLabel = (code, valuesByCode, options = {}) => buildPlanetLabels(metricEntries, {
  valuesByCode, ...options,
}).find((label) => label.code === code);

describe('planet metric values', () => {
  it('retains zero and negative observations with existing RU/EN units and formatting', () => {
    const zero = metricLabel('DE', new Map([['DE', 0]]), { unit: '%' });
    expect(zero).toMatchObject({ value: 0, hasValue: true, valueText: '0,00\u00a0%' });
    expect(metricLabel('DE', { DE: -12.34 }, { unit: '%' }).valueText).toBe('-12,34\u00a0%');
    const russian = metricLabel('DE', { DE: 1234567 }, { unit: 'млрд $' });
    const english = metricLabel('DE', { DE: 1234567 }, { locale: 'en', unit: 'млрд $' });
    expect(russian.valueText.replace(/\s/g, ' ')).toBe('1 234 567 млрд $');
    expect(english.valueText.replace(/\s/g, ' ')).toBe('1 234 567 billion $');
    expect(metricLabel('DE', { DE: -12.34 }, { locale: 'en', unit: '%' }).valueText).toBe('-12.34\u00a0%');
  });

  it.each([null, undefined, '', ' ', NaN, Infinity, -Infinity, true, [], {}])('keeps missing or invalid value %s out of the metric line', (value) => {
    expect(metricLabel('DE', { DE: value }, { unit: '%' })).toMatchObject({
      text: 'Германия', value: null, hasValue: false, valueText: '',
    });
  });

  it('reads the original UK key before GB and only falls back when that key is absent', () => {
    expect(metricLabel('GB', new Map([['UK', 0], ['GB', 999]])).value).toBe(0);
    expect(metricLabel('GB', { UK: -5, GB: 999 }).value).toBe(-5);
    expect(metricLabel('GB', { GB: 25 }).value).toBe(25);
    expect(metricLabel('GB', { UK: null, GB: 999 })).toMatchObject({ value: null, hasValue: false });
    const geographicEntries = bindPlanetCountries([], WORLD_FEATURES);
    const british = buildPlanetLabels(geographicEntries, { valuesByCode: { UK: 12 } }).find((label) => label.code === 'GB');
    expect(british.value).toBe(12);
  });

  it('rebuilds a metric line when the current observation or unit changes', () => {
    const first = metricLabel('DE', { DE: 12.34 }, { unit: '%' });
    const next = metricLabel('DE', { DE: 56.78 }, { unit: 'млрд $' });
    expect(first.valueText).toBe('12,34\u00a0%');
    expect(next.valueText).toBe('56,78\u00a0млрд $');
    expect(metricLabel('DE', null, { unit: '%' }).valueText).toBe('');
  });
});

describe('geographic planet names', () => {
  it('labels countries outside the API catalogue in Russian and English', () => {
    const entries = bindPlanetCountries([], WORLD_FEATURES);
    const russian = buildPlanetLabels(entries, { locale: 'ru' });
    const english = buildPlanetLabels(entries, { locale: 'en' });
    expect(russian.find((label) => label.code === 'RU').text).toBe('Россия');
    expect(english.find((label) => label.code === 'RU').text).toBe('Russia');
    expect(russian.length).toBeGreaterThan(150);
  });

  it('keeps one main-land name for a country with remote duplicate features', () => {
    const entries = bindPlanetCountries([{ code: 'UK', name: 'Великобритания', name_en: 'United Kingdom' }], WORLD_FEATURES);
    const british = entries.find((entry) => entry.code === 'GB');
    const labels = buildPlanetLabels([...entries, { ...british, feature: null, focus: [100, 0] }]);
    expect(labels.filter((label) => label.code === 'GB')).toHaveLength(1);
    expect(labels.find((label) => label.code === 'GB').text).toBe('Великобритания');
  });

  it('wraps Russian words without dropping letters or splitting Unicode characters', () => {
    const text = 'Демократическая Республика Конго';
    const lines = wrapPlanetLabel(text, (value) => Array.from(value).length, 14);
    expect(lines.join(' ').replaceAll(' ', '')).toBe(text.replaceAll(' ', ''));
    expect(lines.every((line) => Array.from(line).length <= 14)).toBe(true);
    expect(wrapPlanetLabel('A🌍B', (value) => Array.from(value).length, 2)).toEqual(['A🌍', 'B']);
  });

  it('fits the fine atlas names in a bounded texture, including microstates', async () => {
    const entries = bindPlanetCountries([], await loadPlanetFeatures('fine'));
    const labels = buildPlanetLabels(entries, { locale: 'ru' });
    const packed = packPlanetLabelAtlas(labels, (text) => Array.from(text).length * 11);
    expect(packed).toHaveLength(labels.length);
    expect(packed.some((label) => label.code === 'MT')).toBe(true);
    expect(packed.every((label) => label.x + label.width <= 2048 && label.y + label.height <= 1024)).toBe(true);
    expect(packPlanetLabelAtlas(labels, (text) => text.length * 11, { height: 10 })).toBeNull();
  });

  it.each(['ru', 'en'])('fits complete geography plus 55 metric lines with a bounded font-fit contract in %s', async (locale) => {
    const entries = bindPlanetCountries([], await loadPlanetFeatures('fine'));
    const geography = buildPlanetLabels(entries, { locale });
    const valuesByCode = new Map(geography.slice(0, 55).map((label, index) => [label.code, 1000 + index]));
    const labels = buildPlanetLabels(entries, { locale, valuesByCode, unit: '% экономически активного населения' });
    let packed = null;
    for (const valueFont of [24, 22, 20, 18]) {
      const nameFont = valueFont * 5 / 6;
      packed = packPlanetLabelAtlas(labels, (text) => Array.from(text).length * nameFont * 0.55, {
        lineHeight: nameFont + 4,
        measureValue: (text) => Array.from(text).length * valueFont * 0.55,
        valueLineHeight: valueFont + 4,
      });
      if (packed) break;
    }
    expect(packed).toHaveLength(labels.length);
    expect(packed.filter((label) => label.valueLine)).toHaveLength(55);
    expect(packed.find((label) => label.code === 'MT')).toBeDefined();
    expect(packed.every((label) => label.x + label.width <= 2048 && label.y + label.height <= 1024)).toBe(true);
    const overlap = packed.some((a, index) => packed.slice(index + 1).some((b) =>
      a.x < b.x + b.width && a.x + a.width > b.x
      && a.y < b.y + b.height && a.y + a.height > b.y));
    expect(overlap).toBe(false);
  });

  it('allocates a separate primary value line and enough chip padding without truncating units', () => {
    const valueText = '12 345,6 млрд долларов США (цены 2017)';
    const [packed] = packPlanetLabelAtlas([{ text: 'Германия', hasValue: true, valueText }], (text) => text.length * 5, {
      lineHeight: 20, measureValue: (text) => text.length * 10,
      valueLineHeight: 28, paddingX: 12, paddingY: 8, lineGap: 4,
    });
    expect(packed.nameLines).toEqual(['Германия']);
    expect(packed.valueLine).toBe(valueText);
    expect(packed.width).toBe(valueText.length * 10 + 24);
    expect(packed.height).toBe(20 + 4 + 28 + 16);
    expect(packPlanetLabelAtlas([{ text: 'Германия', hasValue: true, valueText }], (text) => text.length * 5, {
      width: 100, measureValue: (text) => text.length * 10,
    })).toBeNull();
  });

  it('wraps a full long unit without splitting the atomic grouped number', () => {
    const numberText = '12\u00a0345,6';
    const unitText = 'млрд долларов США (цены 2017)';
    const valueText = `${numberText}\u00a0${unitText}`;
    const [packed] = packPlanetLabelAtlas([{
      text: 'Германия', hasValue: true, numberText, unitText, valueText,
    }], (text) => text.length * 5, {
      maxTextWidth: 160, lineHeight: 20, measureValue: (text) => text.length * 10,
      valueLineHeight: 28,
    });
    expect(packed.valueLine).toBe(valueText);
    expect(packed.valueLines[0]).toBe(numberText);
    expect(packed.valueLines.slice(1).join(' ')).toBe(unitText);
    expect(packed.valueLines.every((line) => line.length * 10 <= 160)).toBe(true);
    expect(packed.height).toBe(20 + 4 + packed.valueLines.length * 28 + 16);
  });
});

describe('planet label visibility and placement', () => {
  it('hides the far hemisphere and horizon even for a selected country', () => {
    const labels = layoutPlanetLabels([
      candidate('RU', { facing: -1 }), candidate('DE', { facing: 0.1 }), candidate('FR'),
    ], { ...viewport, selectedCode: 'RU' });
    expect(labels.map((label) => label.code)).toEqual(['FR']);
  });

  it('gives the selected country and then the hovered country collision priority', () => {
    const input = [candidate('RU', { area: 1 }), candidate('DE', { area: 0.001 }), candidate('FR', { area: 0.1 })];
    expect(layoutPlanetLabels(input, { ...viewport, selectedCode: 'DE', hoverCode: 'FR' }).map((label) => label.code)).toEqual(['DE']);
    expect(layoutPlanetLabels(input, { ...viewport, hoverCode: 'FR' }).map((label) => label.code)).toEqual(['FR']);
  });

  it('prefers observed metric values over larger no-data countries while preserving selection priority', () => {
    const input = [candidate('RU', { area: 1, hasValue: false }), candidate('DE', { area: 0.01, hasValue: true })];
    expect(layoutPlanetLabels(input, viewport).map((label) => label.code)).toEqual(['DE']);
    expect(layoutPlanetLabels(input, { ...viewport, selectedCode: 'RU' }).map((label) => label.code)).toEqual(['RU']);
    expect(layoutPlanetLabels(input, { ...viewport, hoverCode: 'RU' }).map((label) => label.code)).toEqual(['RU']);
  });

  it('shows observed values including zero, with selected no-data names allowed explicitly', () => {
    const input = [
      candidate('RU', { x: 100, area: 1, hasValue: false }),
      candidate('DE', { x: 250, area: 0.01, hasValue: true, value: 0, valueText: '0,00\u00a0%' }),
      candidate('FR', { x: 400, area: 0.1, hasValue: false }),
    ];
    expect(layoutPlanetLabels(input, { ...viewport, valuesOnly: true }).map((label) => label.code)).toEqual(['DE']);
    expect(layoutPlanetLabels(input, { ...viewport, valuesOnly: true, selectedCode: 'RU' }).map((label) => label.code)).toEqual(['RU', 'DE']);
    expect(layoutPlanetLabels(input, { ...viewport, valuesOnly: true, hoverCode: 'FR' }).map((label) => label.code)).toEqual(['FR', 'DE']);
    expect(layoutPlanetLabels(input, viewport)).toHaveLength(3);
  });

  it('shows small countries after zooming or explicit selection', () => {
    const small = candidate('MT', { area: 0.000007 });
    expect(layoutPlanetLabels([small], { ...viewport, cameraDistance: 3.35 })).toEqual([]);
    expect(layoutPlanetLabels([small], { ...viewport, cameraDistance: 1.8 })).toHaveLength(1);
    expect(layoutPlanetLabels([small], { ...viewport, selectedCode: 'MT' })).toHaveLength(1);
  });

  it('leaves a 12px gap above a selected-country marker and respects viewport bounds', () => {
    const [label] = layoutPlanetLabels([candidate('DE')], { ...viewport, selectedCode: 'DE' });
    expect(label.box.bottom).toBe(label.y - 12);
    expect(label.labelY).toBe(label.y - 12 - label.height / 2);
    expect(layoutPlanetLabels([candidate('DE', { x: 5 })], viewport)).toEqual([]);
  });

  it('keeps complete text inside the globe silhouette, including its corners', () => {
    const globe = { x: 250, y: 175, radius: 120 };
    const labels = layoutPlanetLabels([
      candidate('DE', { x: 250, y: 175 }),
      candidate('TR', { x: 350, y: 180 }),
      candidate('RU', { x: 250, y: 65 }),
    ], { ...viewport, globe });
    expect(labels.map((label) => label.code)).toEqual(['DE']);
    expect(layoutPlanetLabels([candidate('DE')], { ...viewport, globe: { ...globe, radius: 600 } })).toHaveLength(1);
  });

  it('bounds the number of non-overlapping labels independently of input order', () => {
    const input = Array.from({ length: 30 }, (_, index) => candidate(String(index).padStart(2, '0'), {
      x: 40 + (index % 6) * 80, y: 60 + Math.floor(index / 6) * 55,
    }));
    const forward = layoutPlanetLabels(input, { ...viewport, maxVisible: 12 });
    const reversed = layoutPlanetLabels([...input].reverse(), { ...viewport, maxVisible: 12 });
    expect(forward).toHaveLength(12);
    expect(reversed.map((label) => label.code)).toEqual(forward.map((label) => label.code));
  });
});
