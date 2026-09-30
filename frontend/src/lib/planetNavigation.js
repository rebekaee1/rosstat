/** Fit the complete globe, including padding, to the smaller viewport angle. */
export function planetFitDistance({ fov = 40, aspect = 1, radius = 1, padding = 1.08 } = {}) {
  const safeFov = Number.isFinite(fov) && fov > 0 && fov < 179 ? fov : 40;
  const safeAspect = Number.isFinite(aspect) && aspect > 0 ? aspect : 1;
  const safeRadius = Number.isFinite(radius) && radius > 0 ? radius : 1;
  const safePadding = Number.isFinite(padding) && padding >= 1 ? padding : 1.08;
  const verticalAngle = safeFov * Math.PI / 360;
  const horizontalAngle = Math.atan(Math.tan(verticalAngle) * safeAspect);
  return safeRadius * safePadding / Math.sin(Math.min(verticalAngle, horizontalAngle));
}

export function createPlanetPointerState() {
  return { pointerId: null, x: 0, y: 0, moved: false, cancelled: false, activeIds: [] };
}

function validPointer(event) {
  return Number.isInteger(event?.pointerId)
    && Number.isFinite(event.clientX) && Number.isFinite(event.clientY);
}

/** A second contact cancels the whole gesture, even if it starts off the globe. */
export function beginPlanetPointer(state, event) {
  if (!validPointer(event)) return { ...state, cancelled: true };
  if (state.activeIds.includes(event.pointerId)) return state;
  const activeIds = [...state.activeIds, event.pointerId];
  if (state.activeIds.length) return { ...state, activeIds, cancelled: true };
  return {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    moved: false,
    cancelled: event.isPrimary === false || (event.button != null && event.button !== 0),
    activeIds,
  };
}

/** Remember movement permanently: a round trip is still a drag, never a tap. */
export function movePlanetPointer(state, event, threshold = 6) {
  if (!validPointer(event) || event.pointerId !== state.pointerId || state.moved) return state;
  return Math.hypot(event.clientX - state.x, event.clientY - state.y) > threshold
    ? { ...state, moved: true } : state;
}

export function endPlanetPointer(state, event, cancelled = false) {
  if (!Number.isInteger(event?.pointerId) || !state.activeIds.includes(event.pointerId)) {
    return { state, tap: false };
  }
  const movedState = movePlanetPointer(state, event);
  const activeIds = movedState.activeIds.filter((id) => id !== event.pointerId);
  const tap = validPointer(event) && event.pointerId === movedState.pointerId
    && !activeIds.length && !movedState.moved && !movedState.cancelled && !cancelled;
  return {
    state: activeIds.length
      ? { ...movedState, activeIds, cancelled: true }
      : createPlanetPointerState(),
    tap,
  };
}
