import { useEffect, useMemo, useRef } from 'react';
import { geoEquirectangular, geoPath } from 'd3-geo';
import { WORLD_FEATURES } from '../lib/worldTopology';
import { viewRectangles } from '../lib/planetView';

let cachedWorldPath = null;

/** Контуры мира в плоской проекции 360 x 180: считаются один раз на всю страницу. */
function worldPath() {
  if (cachedWorldPath == null) {
    const projection = geoEquirectangular().scale(360 / (2 * Math.PI)).translate([180, 90]);
    const path = geoPath(projection);
    cachedWorldPath = WORLD_FEATURES.map((feature) => path(feature) || '').join('');
  }
  return cachedWorldPath;
}

/**
 * Мини-карта: viewBusRef.current(view) двигает рамку напрямую в DOM, без перерисовки React на каждый кадр камеры.
 */
export default function PlanetMiniMap({ viewBusRef, lastViewRef, label }) {
  const first = useRef(null);
  const second = useRef(null);
  const d = useMemo(() => worldPath(), []);
  useEffect(() => {
    const apply = (view) => {
      if (!view) return;
      const rects = viewRectangles(view);
      [first.current, second.current].forEach((node, index) => {
        if (!node) return;
        const rect = rects[index];
        node.style.display = rect ? '' : 'none';
        if (!rect) return;
        node.setAttribute('x', rect.x.toFixed(1));
        node.setAttribute('y', rect.y.toFixed(1));
        node.setAttribute('width', rect.width.toFixed(1));
        node.setAttribute('height', rect.height.toFixed(1));
      });
    };
    viewBusRef.current = apply;
    apply(lastViewRef.current);
    return () => { viewBusRef.current = null; };
  }, [viewBusRef, lastViewRef]);
  return (
    <svg className="planet-minimap" viewBox="0 0 360 180" role="img" aria-label={label}>
      <rect className="planet-minimap-sea" x="0" y="0" width="360" height="180" rx="10" />
      <path className="planet-minimap-land" d={d} />
      <rect ref={first} className="planet-minimap-frame" x="0" y="0" width="0" height="0" rx="3" />
      <rect ref={second} className="planet-minimap-frame" x="0" y="0" width="0" height="0" rx="3" style={{ display: 'none' }} />
    </svg>
  );
}
