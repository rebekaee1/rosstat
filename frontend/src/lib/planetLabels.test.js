import { describe, expect, it } from 'vitest';
import { bindPlanetCountries, loadPlanetFeatures } from './planetGeometry';
import { WORLD_FEATURES } from './worldTopology';
import { buildPlanetLabels, layoutPlanetLabels, packPlanetLabelAtlas, wrapPlanetLabel } from './planetLabels';

const candidate = (code, overrides = {}) => ({
  id: code, code, area: 0.01, x: 200, y: 180, depth: 0.5, facing: 1,
  width: 70, height: 20, ...overrides,
});
const viewport = { width: 500, height: 350 };

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
