import { useMemo, useRef, useState } from 'react';
import { CHART_THEME } from '../lib/chartTheme';
import '../styles/chart-controls.css';

/**
 * Рамка выбора периода прямо под графиком: уменьшенная копия ряда и окно с двумя ручками.
 * Левая ручка двигает начало, правая конец, середина сдвигает окно целиком. Заменяет ползунок «Раньше / Позже».
 *
 * Работает в индексах точек: `start` включительно, `end` не включительно (как slice). Кнопки-стрелки на ручках
 * двигают границу на одну точку, с Shift на 12.
 */

const SPARK_W = 600;
const SPARK_H = 40;
const MAX_SPARK_POINTS = 160;

function sparkPaths(rows) {
  const values = [];
  const step = Math.max(1, Math.ceil(rows.length / MAX_SPARK_POINTS));
  for (let i = 0; i < rows.length; i += step) {
    const raw = rows[i].actual ?? rows[i].forecast;
    const v = Number(raw);
    values.push(Number.isFinite(v) ? v : null);
  }
  const last = rows[rows.length - 1];
  const lastValue = Number(last?.actual ?? last?.forecast);
  if ((rows.length - 1) % step !== 0) values.push(Number.isFinite(lastValue) ? lastValue : null);
  const finite = values.filter((v) => v != null);
  if (finite.length < 2) return null;
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const span = max - min || 1;
  let line = '';
  let area = '';
  let first = null;
  let lastX = 0;
  values.forEach((v, i) => {
    if (v == null) return;
    const x = (i / (values.length - 1)) * SPARK_W;
    const y = SPARK_H - 4 - ((v - min) / span) * (SPARK_H - 8);
    line += `${line ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`;
    if (first == null) first = x;
    lastX = x;
  });
  area = `${line}L${lastX.toFixed(1)} ${SPARK_H}L${(first ?? 0).toFixed(1)} ${SPARK_H}Z`;
  return { line, area };
}

export default function ChartBrush({
  rows, start, end, minWindow = 4, onChange, labels,
}) {
  const trackRef = useRef(null);
  const dragRef = useRef(null);
  const [active, setActive] = useState(null);
  const total = rows.length;
  const spark = useMemo(() => sparkPaths(rows), [rows]);
  if (total < 2) return null;

  const pct = (index) => `${(Math.max(0, Math.min(total, index)) / total) * 100}%`;
  const left = (start / total) * 100;
  const width = ((end - start) / total) * 100;

  const indexAt = (clientX) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return null;
    return ((clientX - rect.left) / rect.width) * total;
  };

  const apply = (nextStart, nextEnd) => {
    const s = Math.max(0, Math.min(total - minWindow, Math.round(nextStart)));
    const e = Math.min(total, Math.max(s + minWindow, Math.round(nextEnd)));
    if (s !== start || e !== end) onChange(s, e);
  };

  const begin = (kind) => (event) => {
    event.stopPropagation();
    const at = indexAt(event.clientX);
    if (at == null) return;
    dragRef.current = {
      kind, grabAt: at, start, end, pointerId: event.pointerId,
    };
    setActive(kind);
    try { trackRef.current?.setPointerCapture(event.pointerId); } catch { /* ok */ }
  };

  const move = (event) => {
    const d = dragRef.current;
    if (!d) return;
    const at = indexAt(event.clientX);
    if (at == null) return;
    const delta = at - d.grabAt;
    // Ручка упирается в другую ручку на расстоянии минимального окна, а не толкает её перед собой.
    if (d.kind === 'start') apply(Math.min(d.start + delta, d.end - minWindow), d.end);
    else if (d.kind === 'end') apply(d.start, Math.max(d.end + delta, d.start + minWindow));
    else {
      const size = d.end - d.start;
      const nextStart = Math.max(0, Math.min(total - size, d.start + delta));
      apply(nextStart, nextStart + size);
    }
  };

  const finish = (event) => {
    if (!dragRef.current) return;
    try { trackRef.current?.releasePointerCapture(event.pointerId); } catch { /* ok */ }
    dragRef.current = null;
    setActive(null);
  };

  // Нажатие мимо окна переносит его центр в эту точку.
  const jump = (event) => {
    if (dragRef.current) return;
    const at = indexAt(event.clientX);
    if (at == null) return;
    const size = end - start;
    const nextStart = Math.max(0, Math.min(total - size, at - size / 2));
    apply(nextStart, nextStart + size);
  };

  const keyHandler = (kind) => (event) => {
    const stepSize = event.shiftKey ? 12 : 1;
    let dir = 0;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') dir = -1;
    else if (event.key === 'ArrowRight' || event.key === 'ArrowUp') dir = 1;
    else return;
    event.preventDefault();
    if (kind === 'start') apply(Math.min(start + dir * stepSize, end - minWindow), end);
    else apply(start, Math.max(end + dir * stepSize, start + minWindow));
  };

  return (
    <div
      className="fe-brush"
      role="group"
      aria-label={labels.group}
      data-active={active || undefined}
    >
      <div
        ref={trackRef}
        className="fe-brush__track"
        onPointerDown={jump}
        onPointerMove={move}
        onPointerUp={finish}
        onPointerCancel={finish}
      >
        {spark && (
          <svg
            className="fe-brush__spark"
            viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d={spark.area} fill={CHART_THEME.ink} fillOpacity={0.08} />
            <path d={spark.line} fill="none" stroke={CHART_THEME.axis} strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
          </svg>
        )}
        <div className="fe-brush__shade" style={{ left: 0, width: `${left}%` }} aria-hidden="true" />
        <div className="fe-brush__shade" style={{ left: `${left + width}%`, right: 0 }} aria-hidden="true" />
        <div
          className="fe-brush__window"
          style={{ left: `${left}%`, width: `${width}%` }}
          onPointerDown={begin('move')}
          aria-hidden="true"
        />
        <button
          type="button"
          role="slider"
          className="fe-brush__handle fe-brush__handle--start"
          style={{ left: pct(start) }}
          aria-label={labels.from}
          aria-valuemin={0}
          aria-valuemax={Math.max(0, end - minWindow)}
          aria-valuenow={start}
          aria-valuetext={String(rows[start]?.date ?? '').slice(0, 10)}
          onPointerDown={begin('start')}
          onKeyDown={keyHandler('start')}
        >
          <span aria-hidden="true" />
        </button>
        <button
          type="button"
          role="slider"
          className="fe-brush__handle fe-brush__handle--end"
          style={{ left: pct(end) }}
          aria-label={labels.to}
          aria-valuemin={Math.min(total, start + minWindow)}
          aria-valuemax={total}
          aria-valuenow={end}
          aria-valuetext={String(rows[end - 1]?.date ?? '').slice(0, 10)}
          onPointerDown={begin('end')}
          onKeyDown={keyHandler('end')}
        >
          <span aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
