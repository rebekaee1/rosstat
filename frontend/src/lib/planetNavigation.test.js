import { describe, expect, it } from 'vitest';
import {
  beginPlanetPointer, createPlanetPointerState, endPlanetPointer,
  movePlanetPointer, planetFitDistance,
} from './planetNavigation';

const pointer = (overrides = {}) => ({
  pointerId: 1, clientX: 100, clientY: 100, button: 0, isPrimary: true, ...overrides,
});

describe('planet camera framing', () => {
  it.each([0.45, 0.82, 1, 1.6])('fits the globe at viewport aspect %s', (aspect) => {
    const distance = planetFitDistance({ fov: 40, aspect });
    const globeAngle = Math.asin(1 / distance);
    const verticalAngle = 20 * Math.PI / 180;
    const horizontalAngle = Math.atan(Math.tan(verticalAngle) * aspect);
    expect(globeAngle).toBeLessThan(verticalAngle);
    expect(globeAngle).toBeLessThan(horizontalAngle);
  });

  it('allows a narrow canvas to fit beyond the old zoom limit', () => {
    expect(planetFitDistance({ aspect: 0.45 })).toBeGreaterThan(4.8);
  });

  it('uses safe defaults before a canvas has measurable dimensions', () => {
    expect(planetFitDistance({ aspect: 0, fov: NaN })).toBe(planetFitDistance());
    expect(planetFitDistance({ aspect: Infinity, radius: -1, padding: 0 }))
      .toBe(planetFitDistance());
  });
});

describe('planet tap versus navigation gestures', () => {
  it('accepts a single primary tap with small natural movement', () => {
    const down = beginPlanetPointer(createPlanetPointerState(), pointer());
    const result = endPlanetPointer(down, pointer({ clientX: 103, clientY: 104 }));
    expect(result.tap).toBe(true);
    expect(result.state).toEqual(createPlanetPointerState());
  });

  it('does not mistake the same contact delivered twice for a second finger', () => {
    const state = beginPlanetPointer(createPlanetPointerState(), pointer());
    const duplicate = beginPlanetPointer(state, pointer());
    expect(duplicate).toBe(state);
    expect(endPlanetPointer(duplicate, pointer()).tap).toBe(true);
  });

  it('rejects a drag that returns to its starting position', () => {
    let state = beginPlanetPointer(createPlanetPointerState(), pointer());
    state = movePlanetPointer(state, pointer({ clientX: 180 }));
    state = movePlanetPointer(state, pointer());
    expect(endPlanetPointer(state, pointer()).tap).toBe(false);
  });

  it('rejects a drag even when no intermediate move was delivered', () => {
    const state = beginPlanetPointer(createPlanetPointerState(), pointer());
    expect(endPlanetPointer(state, pointer({ clientY: 120 })).tap).toBe(false);
  });

  it.each([1, 2])('rejects a two-finger gesture when pointer %s ends first', (first) => {
    let state = beginPlanetPointer(createPlanetPointerState(), pointer());
    state = beginPlanetPointer(state, pointer({ pointerId: 2, clientX: 150, isPrimary: false }));
    const firstEnd = endPlanetPointer(state, pointer({ pointerId: first }));
    const lastEnd = endPlanetPointer(firstEnd.state, pointer({ pointerId: first === 1 ? 2 : 1 }));
    expect(firstEnd.tap).toBe(false);
    expect(lastEnd.tap).toBe(false);
    expect(lastEnd.state).toEqual(createPlanetPointerState());
  });

  it('rejects pointer cancellation and accepts the next independent tap', () => {
    const state = beginPlanetPointer(createPlanetPointerState(), pointer());
    const cancelled = endPlanetPointer(state, pointer(), true);
    expect(cancelled.tap).toBe(false);
    const next = beginPlanetPointer(cancelled.state, pointer({ pointerId: 3 }));
    expect(endPlanetPointer(next, pointer({ pointerId: 3 })).tap).toBe(true);
  });

  it.each([{ pointerId: 8 }, { pointerId: undefined }, { pointerId: '1' }])(
    'does not select or consume another pointer when its identity is %j', (override) => {
      const state = beginPlanetPointer(createPlanetPointerState(), pointer());
      const result = endPlanetPointer(state, pointer(override));
      expect(result.tap).toBe(false);
      expect(result.state).toBe(state);
    },
  );

  it.each([{ button: 2 }, { isPrimary: false }, { clientX: NaN }])(
    'rejects unsupported starting contacts %j', (override) => {
      const state = beginPlanetPointer(createPlanetPointerState(), pointer(override));
      expect(endPlanetPointer(state, pointer()).tap).toBe(false);
    },
  );
});
