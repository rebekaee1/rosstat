import { describe, it, expect } from 'vitest';
import { createBlockClock, createScrollProgress, inpEvidence, interactionTarget, unobscuredRatio } from './behaviorEvidence';

const rect = (left, top, right, bottom) => ({ left, top, right, bottom });
const viewport = rect(0, 0, 100, 100);

describe('sanitized INP attribution', () => {
  it('keeps original interaction timing and causal durations separately from report time', () => {
    const result = inpEvidence({ attribution: {
      interactionTarget: 'div#root > button[data-fe-interaction-action=accept]',
      interactionType: 'pointer', interactionTime: 78000.4,
      inputDelay: 3700.3, processingDuration: 20.4, presentationDelay: 24.1, loadState: 'complete',
      processedEventEntries: [{ target: { value: 'secret' } }],
    } }, 1_800_000_000_000);
    expect(result).toEqual({
      inp_target: 'div#root > button[data-fe-interaction-action=accept]', inp_type: 'pointer', inp_start_ms: 78000,
      input_delay_ms: 3700, processing_ms: 20, presentation_ms: 24, load_state: 'complete',
      time_origin_ms: 1_800_000_000_000, interaction_epoch_ms: 1_800_000_078_000, evidence_version: 3,
    });
    expect(JSON.stringify(result)).not.toContain('secret');
  });

  it('rejects arbitrary ids, text, invalid durations and unknown targets', () => {
    const result = inpEvidence({ attribution: {
      interactionTarget: 'input#person-email[value=user@example.com]', interactionType: 'touch',
      interactionTime: NaN, inputDelay: -1, processingDuration: Infinity, presentationDelay: 1e12, loadState: 'unknown',
    } }, Infinity);
    expect(Object.values(result).filter((value) => value !== null)).toEqual([3]);
    expect(inpEvidence({}, 123).inp_target).toBeNull();
  });

  it('locator only reads structural attributes, never input value or accessible text', () => {
    const button = { nodeType: 1, tagName: 'BUTTON', id: 'private-email', value: 'secret',
      textContent: 'secret', getAttribute: (key) => key === 'data-fe-interaction-action' ? 'accept' : 'secret' };
    expect(interactionTarget(button)).toBe('button[data-fe-interaction-action=accept]');
  });
});

describe('overlay-aware block exposure', () => {
  it('subtracts overlapping/nested opaque panels once', () => {
    expect(unobscuredRatio(viewport, viewport, [rect(0, 60, 100, 100), rect(20, 70, 80, 90)])) .toBeCloseTo(0.6);
    expect(unobscuredRatio(viewport, viewport, [rect(0, 40, 100, 100)])) .toBeCloseTo(0.4);
    expect(unobscuredRatio(viewport, viewport, [rect(0, 50, 100, 100)])) .toBe(0.5);
  });

  it('uses complete element area rather than a tiny viewport sliver', () => {
    expect(unobscuredRatio(rect(0, -200, 100, 100), viewport)).toBeCloseTo(1 / 3);
    expect(unobscuredRatio(rect(0, 0, 0, 100), viewport)).toBe(0);
  });

  it('counts one semantic block once, caps input-backed time and closes on focus loss', () => {
    const clock = createBlockClock(0);
    clock.update(0, true, 15000);
    // Repeated observations of duplicate/nested DOM nodes cannot add wall time.
    clock.update(1000, true, 15000);
    clock.update(1000, true, 15000);
    clock.update(2000, false, null);
    clock.update(30000, true, null);
    expect(clock.snapshot(31000)).toEqual({ visible_ms: 3000, active_ms: 2000 });
    expect(clock.snapshot(31000)).toEqual({ visible_ms: 0, active_ms: 0 });
    clock.update(31000, true, 46000);
    expect(clock.snapshot(61000)).toEqual({ visible_ms: 30000, active_ms: 15000 });
  });
});

describe('settled scroll progress', () => {
  const observe = (tracker, height, y, time, input = false, visible = true) => tracker.observe({ height, viewport: 500, y, time, input, visible });

  it('never turns a short skeleton into 100% and requires real progress on a tall page', () => {
    const tracker = createScrollProgress();
    expect(observe(tracker, 500, 0, 0, true).pct).toBe(0);
    expect(observe(tracker, 2000, 0, 1000).valid).toBe(false);
    expect(observe(tracker, 2000, 1500, 1300).pct).toBe(0); // script scroll alone
    expect(observe(tracker, 2000, 300, 1400, true).pct).toBe(20);
  });

  it('retains valid distance, recomputes it after growth and discards unsettled input', () => {
    const tracker = createScrollProgress();
    observe(tracker, 1000, 0, 0);
    expect(observe(tracker, 1000, 500, 300, true).pct).toBe(100);
    expect(observe(tracker, 2000, 500, 400).valid).toBe(false);
    expect(observe(tracker, 2000, 500, 700).pct).toBe(33);
    observe(tracker, 3000, 1000, 800, true);
    expect(observe(tracker, 4000, 1000, 900).valid).toBe(false);
    expect(observe(tracker, 4000, 1000, 1200).max_y).toBe(500);
  });

  it('records the observed input distance rather than a later script position', () => {
    const tracker = createScrollProgress();
    observe(tracker, 2000, 200, 0, true);
    expect(observe(tracker, 2000, 1500, 300).max_y).toBe(200);
    expect(observe(tracker, 2000, 800, 400, true, false).valid).toBe(false);
    expect(observe(tracker, 2000, 800, 500).max_y).toBe(200);
  });
});
