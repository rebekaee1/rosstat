import { describe, it, expect } from 'vitest';
import { visibleCpiViewModes, CPI_VIEW_MODES } from './cpiViewModes';

describe('visibleCpiViewModes', () => {
  it('includes step and index modes for all CPI cluster codes', () => {
    for (const code of ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services']) {
      const modes = visibleCpiViewModes(code).map((m) => m.mode);
      expect(modes).toContain('step-monthly');
      expect(modes).toContain('index-quarterly');
      expect(modes).toContain('index-annual');
      expect(modes).not.toContain('quarterly');
    }
  });

  it('недельный шаг — только на общем ИПЦ, по срезам корзины его нет', () => {
    expect(visibleCpiViewModes('cpi').map((m) => m.mode)).toContain('step-weekly');
    for (const code of ['cpi-food', 'cpi-nonfood', 'cpi-services']) {
      expect(visibleCpiViewModes(code).map((m) => m.mode)).not.toContain('step-weekly');
    }
  });

  it('exposes the same mode count for each CPI slice code', () => {
    const base = visibleCpiViewModes('cpi-food').length;
    expect(visibleCpiViewModes('cpi-nonfood').length).toBe(base);
    expect(visibleCpiViewModes('cpi-services').length).toBe(base);
    expect(CPI_VIEW_MODES.filter((m) => !m.cpiOnly).length).toBe(base);
    // Общий ИПЦ шире срезов ровно на недельный шаг.
    expect(visibleCpiViewModes('cpi').length).toBe(base + 1);
  });
});
