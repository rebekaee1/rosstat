import { useRef, useEffect, useState, useId } from 'react';

const COLOR_POSITIVE = '#16A34A';
const COLOR_NEGATIVE = '#DC2626';
const COLOR_CHAMPAGNE = '#B8942F';
const COLOR_FLAT = '#9CA3AF';

function resolveColor(trend, sentiment) {
  if (trend === 'flat') return COLOR_FLAT;

  if (sentiment === 'neutral') return COLOR_CHAMPAGNE;

  const isUp = trend === 'up';
  if (sentiment === 'inverse') return isUp ? COLOR_NEGATIVE : COLOR_POSITIVE;
  return isUp ? COLOR_POSITIVE : COLOR_NEGATIVE;
}

/**
 * Fritsch-Carlson monotone cubic interpolation.
 * Returns SVG path `d` string for a smooth curve that never overshoots data.
 */
function monotonePath(points) {
  const n = points.length;
  if (n < 2) return '';
  if (n === 2) return `M${points[0].x},${points[0].y}L${points[1].x},${points[1].y}`;

  const dx = [];
  const dy = [];
  const m = [];

  for (let i = 0; i < n - 1; i++) {
    dx.push(points[i + 1].x - points[i].x);
    dy.push(points[i + 1].y - points[i].y);
    m.push(dy[i] / dx[i]);
  }

  const tangents = [m[0]];
  for (let i = 1; i < n - 1; i++) {
    if (m[i - 1] * m[i] <= 0) {
      tangents.push(0);
    } else {
      tangents.push(3 * (dx[i - 1] + dx[i]) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i]));
    }
  }
  tangents.push(m[n - 2]);

  let d = `M${points[0].x},${points[0].y}`;
  for (let i = 0; i < n - 1; i++) {
    const p0 = points[i];
    const p1 = points[i + 1];
    const step = dx[i] / 3;
    const cp1x = p0.x + step;
    const cp1y = p0.y + tangents[i] * step;
    const cp2x = p1.x - step;
    const cp2y = p1.y - tangents[i + 1] * step;
    d += `C${cp1x},${cp1y},${cp2x},${cp2y},${p1.x},${p1.y}`;
  }

  return d;
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced;
}

export default function Sparkline({
  points,
  trend = 'flat',
  sentiment = 'positive',
  height = 48,
  className = '',
  staggerMs = 0,
}) {
  const uid = useId();
  const svgRef = useRef(null);
  const lineRef = useRef(null);
  const [inView, setInView] = useState(false);
  const [pathLength, setPathLength] = useState(0);
  const reducedMotion = useReducedMotion();

  const revealed = reducedMotion || inView;
  const color = resolveColor(trend, sentiment);
  const pad = 4;
  const dotR = 2.5;
  const glowR = 5;

  const safeId = uid.replace(/:/g, '_');
  const areaGradId = `spark-area-${safeId}`;
  const lineGradId = `spark-line-${safeId}`;

  useEffect(() => {
    if (!svgRef.current || reducedMotion) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => setInView(true), staggerMs);
          observer.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    observer.observe(svgRef.current);
    return () => observer.disconnect();
  }, [staggerMs, reducedMotion]);

  useEffect(() => {
    if (lineRef.current) {
      setPathLength(lineRef.current.getTotalLength());
    }
  }, [points]);

  if (!points || points.length < 2) return null;

  const values = points;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const computePoints = (w) => {
    const drawW = w - pad * 2;
    const drawH = height - pad * 2;
    return values.map((v, i) => ({
      x: pad + (i / (values.length - 1)) * drawW,
      y: pad + drawH - ((v - min) / range) * drawH,
    }));
  };

  const renderContent = (width) => {
    const pts = computePoints(width);
    const linePath = monotonePath(pts);
    const lastPt = pts[pts.length - 1];
    const firstPt = pts[0];

    const areaPath =
      linePath + `L${lastPt.x},${height - pad}L${firstPt.x},${height - pad}Z`;

    const showAnimation = revealed && !reducedMotion && pathLength > 0;
    const instantReveal = reducedMotion || !pathLength;

    return (
      <svg
        ref={svgRef}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={`sparkline-svg ${className}`}
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={areaGradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.12} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
          <linearGradient id={lineGradId} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={1} />
          </linearGradient>
        </defs>

        {/* Area fill */}
        <path
          d={areaPath}
          fill={`url(#${areaGradId})`}
          className={showAnimation ? 'sparkline-area-animate' : ''}
          style={{
            opacity: instantReveal ? 1 : revealed ? undefined : 0,
            animationDelay: showAnimation ? '300ms' : undefined,
          }}
        />

        {/* Line with gradient stroke */}
        <path
          ref={lineRef}
          d={linePath}
          fill="none"
          stroke={`url(#${lineGradId})`}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={
            showAnimation
              ? {
                  strokeDasharray: pathLength,
                  strokeDashoffset: 0,
                  animation: `sparkline-reveal 800ms ease-out forwards`,
                }
              : instantReveal
                ? { opacity: 1 }
                : {
                    strokeDasharray: pathLength,
                    strokeDashoffset: pathLength,
                  }
          }
        />

        {/* Glow ring */}
        <circle
          cx={lastPt.x}
          cy={lastPt.y}
          r={glowR}
          fill={color}
          className={revealed ? 'sparkline-glow' : ''}
          style={{
            opacity: revealed ? undefined : 0,
            animationDelay: reducedMotion ? '0ms' : `${800 + staggerMs}ms`,
          }}
        />

        {/* Solid dot */}
        <circle
          cx={lastPt.x}
          cy={lastPt.y}
          r={dotR}
          fill={color}
          style={{
            opacity: revealed ? 1 : 0,
            transition: reducedMotion ? 'none' : `opacity 200ms ${800 + staggerMs}ms`,
          }}
        />
      </svg>
    );
  };

  return (
    <div className="sparkline-container w-full" style={{ height }}>
      <SparklineResizer height={height} render={renderContent} />
    </div>
  );
}

function SparklineResizer({ height, render }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.round(entry.contentRect.width);
      if (w > 0) setWidth(w);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={containerRef} style={{ width: '100%', height }}>
      {width > 0 && render(width)}
    </div>
  );
}

export function SparklineSkeleton({ height = 48 }) {
  return (
    <div className="skeleton w-full rounded-lg" style={{ height }} />
  );
}
