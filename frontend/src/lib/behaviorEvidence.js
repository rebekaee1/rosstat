// Small, deterministic evidence primitives shared by SPA and standalone SSR.
// They observe browser state; they never infer comprehension or satisfaction.
export const EVIDENCE_VERSION = 3;
export const SCROLL_SETTLE_MS = 250;
const MAX_TIMING_MS = 7 * 24 * 3600 * 1000;
const TARGET_ATTRIBUTE = /^(data-analytics-overlay|data-block|data-fe-interaction-action)$/;
const TOKEN = /^[a-z][a-z0-9_-]{0,63}$/i;

export function evidenceToken(value) {
  return typeof value === 'string' && TOKEN.test(value) ? value : null;
}

/** Structural locator only: no text, aria-label, name, value or arbitrary id. */
export function interactionTarget(node) {
  const parts = [];
  while (node?.nodeType === 1 && parts.length < 6 && node.tagName !== 'HTML') {
    const tag = String(node.tagName).toLowerCase();
    if (!/^[a-z][a-z0-9-]{0,31}$/.test(tag)) break;
    let part = tag;
    if (node.id === 'root') { parts.unshift(`${tag}#root`); break; }
    const attribute = ['data-fe-interaction-action', 'data-analytics-overlay', 'data-block']
      .find((key) => evidenceToken(node.getAttribute?.(key)));
    if (attribute) part += `[${attribute}=${node.getAttribute(attribute)}]`;
    else {
      let index = 1;
      let sibling = node.previousElementSibling;
      let inspected = 0;
      while (sibling && inspected++ < 64) {
        if (sibling.tagName === node.tagName) index += 1;
        sibling = sibling.previousElementSibling;
      }
      if (index > 1 && !sibling) part += `:nth-of-type(${index})`;
    }
    parts.unshift(part);
    node = node.parentElement;
  }
  return parts.join(' > ').slice(0, 380) || null;
}

function safeTargetString(value) {
  if (typeof value !== 'string' || value.length > 380) return null;
  const parts = value.split(' > ');
  if (parts.length > 6) return null;
  return parts.every((part) => {
    const match = part.match(/^([a-z][a-z0-9-]{0,31})(#root)?(?::nth-of-type\(\d{1,3}\))?(?:\[([^=\]]+)=([^\]]+)\])?$/);
    return match && (!match[3] || (TARGET_ATTRIBUTE.test(match[3]) && TOKEN.test(match[4])));
  }) ? value : null;
}

function timing(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= MAX_TIMING_MS
    ? Math.round(value) : null;
}

export function inpEvidence(metric, timeOrigin) {
  const a = metric.attribution || {};
  const start = timing(a.interactionTime);
  const origin = typeof timeOrigin === 'number' && Number.isFinite(timeOrigin) && timeOrigin > 0 && timeOrigin < 1e14
    ? Math.round(timeOrigin) : null;
  return {
    inp_target: safeTargetString(a.interactionTarget),
    inp_type: ['pointer', 'keyboard'].includes(a.interactionType) ? a.interactionType : null,
    inp_start_ms: start,
    input_delay_ms: timing(a.inputDelay),
    processing_ms: timing(a.processingDuration),
    presentation_ms: timing(a.presentationDelay),
    load_state: ['loading', 'dom-interactive', 'dom-content-loaded', 'complete'].includes(a.loadState) ? a.loadState : null,
    time_origin_ms: origin,
    interaction_epoch_ms: origin !== null && start !== null ? origin + start : null,
    evidence_version: EVIDENCE_VERSION,
  };
}

function clip(a, b) {
  const left = Math.max(a.left, b.left), top = Math.max(a.top, b.top);
  const right = Math.min(a.right, b.right), bottom = Math.min(a.bottom, b.bottom);
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}

/** Area of a rectangle union: nested/overlapping overlays subtract only once. */
function unionArea(rects) {
  const xs = [...new Set(rects.flatMap((r) => [r.left, r.right]))].sort((a, b) => a - b);
  let area = 0;
  for (let i = 1; i < xs.length; i += 1) {
    const ys = rects.filter((r) => r.left < xs[i] && r.right > xs[i - 1])
      .map((r) => [r.top, r.bottom]).sort((a, b) => a[0] - b[0]);
    let start = 0, end = 0, height = 0;
    for (const [top, bottom] of ys) {
      if (top > end) { height += end - start; start = top; end = bottom; }
      else end = Math.max(end, bottom);
    }
    area += (xs[i] - xs[i - 1]) * (height + end - start);
  }
  return area;
}

export function unobscuredRatio(rect, viewport, overlays = []) {
  const area = (rect.right - rect.left) * (rect.bottom - rect.top);
  const visible = clip(rect, viewport);
  if (!Number.isFinite(area) || area <= 0 || !visible) return 0;
  const covered = overlays.slice(0, 8).map((overlay) => clip(visible, overlay)).filter(Boolean);
  const shown = (visible.right - visible.left) * (visible.bottom - visible.top) - unionArea(covered);
  return Math.max(0, Math.min(1, shown / area));
}

/** Union time for one semantic block, not a sum of its duplicate DOM nodes. */
export function createBlockClock(now = 0) {
  let tick = now, visible = false, activeUntil = null, seen = 0, active = 0;
  const advance = (time) => {
    time = Math.max(tick, time);
    if (visible) {
      seen += time - tick;
      if (activeUntil !== null) active += Math.max(0, Math.min(time, activeUntil) - tick);
    }
    tick = time;
  };
  return {
    update(time, isVisible, until) { advance(time); visible = isVisible; activeUntil = isVisible ? until : null; },
    snapshot(time) { advance(time); const result = { visible_ms: seen, active_ms: active }; seen = 0; active = 0; return result; },
  };
}

/** Scroll distance is retained only from settled, scrollable, visible layouts.
 * When content grows, recompute progress from observed distance, not an old 100%.
 */
export function createScrollProgress() {
  let height = 0, viewport = 0, changedAt = 0, now = 0, maxY = 0, pendingY = null;
  let valid = false;
  const snapshot = () => ({
    pct: valid ? Math.min(100, Math.round(maxY / (height - viewport) * 100)) : 0,
    valid, height, viewport, max_y: Math.round(maxY),
  });
  return {
    observe({ height: h, viewport: v, y, time, input = false, visible = true }) {
      if (![h, v, y, time].every(Number.isFinite) || h < 0 || v <= 0) return snapshot();
      now = Math.max(now, time);
      const extent = h - v;
      if (h !== height || v !== viewport) {
        height = h; viewport = v; changedAt = now; pendingY = null; valid = false;
        maxY = Math.min(maxY, Math.max(0, extent));
      }
      if (input && visible && extent > 0 && y > 0 && y <= extent + 1) pendingY = Math.max(pendingY || 0, Math.min(y, extent));
      if (!visible || extent <= 0 || now - changedAt < SCROLL_SETTLE_MS) {
        valid = false;
        if (!visible || extent <= 0) pendingY = null;
        return snapshot();
      }
      if (pendingY !== null) { maxY = Math.max(maxY, pendingY); pendingY = null; }
      valid = maxY > 0;
      return snapshot();
    },
    snapshot,
  };
}
