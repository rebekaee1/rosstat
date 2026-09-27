import { describe, expect, it } from 'vitest';
import { completeDataset } from './datasetJsonLd';

describe('completeDataset', () => {
  it('extends a short description while keeping the source and unknown rights untouched', () => {
    const raw = { '@type': 'Dataset', name: 'ИПЦ', description: 'Цены.',
      creator: { '@type': 'Organization', name: 'Росстат' } };
    const result = completeDataset(raw);
    expect(result.description.length).toBeGreaterThanOrEqual(50);
    expect(result.description).toContain('Росстат');
    expect(result.creator).toEqual(raw.creator);
    expect(result).not.toHaveProperty('license');
    expect(raw.description).toBe('Цены.');
  });

  it('does not invent a creator or overwrite a source-specific license', () => {
    const license = 'https://source.example/data-license';
    const result = completeDataset({ name: 'GDP', license }, 'en');
    expect(result.description.length).toBeGreaterThanOrEqual(50);
    expect(result).not.toHaveProperty('creator');
    expect(result.license).toBe(license);
  });

  it('caps descriptions at 5000 characters', () => {
    expect(completeDataset({ name: 'Long', description: 'A'.repeat(6000) }, 'en')
      .description).toHaveLength(5000);
  });
});
