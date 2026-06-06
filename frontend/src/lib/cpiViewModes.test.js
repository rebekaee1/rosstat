import { describe, it, expect } from 'vitest';
import { visibleCpiViewModes, CPI_VIEW_MODES } from './cpiViewModes';

describe('visibleCpiViewModes', () => {
  it('includes step and index modes for all CPI cluster codes', () => {
    for (const code of ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services']) {
      const modes = visibleCpiViewModes(code).map((m) => m.mode);
      expect(modes).toContain('step-weekly');
      expect(modes).toContain('step-monthly');
      expect(modes).toContain('index-quarterly');
      expect(modes).toContain('index-annual');
      expect(modes).not.toContain('quarterly');
    }
  });

  it('exposes the same mode count for each CPI code', () => {
    const base = visibleCpiViewModes('cpi').length;
    expect(visibleCpiViewModes('cpi-food').length).toBe(base);
    expect(CPI_VIEW_MODES.filter((m) => !m.generalOnly).length).toBe(base);
  });
});
