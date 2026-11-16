import { useMemo, useRef, useState } from 'react';
import {
  FIELD, areaPath, fieldBounds, formatMonth, formatPercent, linePath, nearestIndex, place, yearTicks,
} from '../../lib/welcomeChart';

/**
 * Линия приветственного экрана: настоящий ряд сайта, один на весь показ.
 *
 * Почему так (`.artifacts/FE-REFERENSY/FILOSOFIYA.md`): график — не украшение рядом с лозунгом, а доказательство фразы.
 * Слова стоят неподвижно, под рукой меняется только то, что берётся одним взглядом: число и месяц.
 * Сегодняшняя точка — самая резкая кромка; на шаге про свежесть прошлое уходит в тень, но не гаснет.
 *
 * `mode` — шаг экрана: find (линия и тон), fresh (кромка «сейчас»), telegram (линия тише), compare (второй ряд), account (точка «ваше»).
 * Рисунок растянут на всю ширину (`preserveAspectRatio="none"`), толщина линии при этом постоянная (`non-scaling-stroke`);
 * подписи — обычный текст поверх, по долям ширины и высоты, поэтому буквы не растягиваются.
 */
export default function WelcomeChart({ series, peer = null, mode, locale, t, names = null }) {
  const boxRef = useRef(null);
  const [hover, setHover] = useState(-1);
  const withPeer = mode === 'compare' && peer && peer.length > 0;
  const bounds = useMemo(() => fieldBounds(series, withPeer ? peer : null), [series, peer, withPeer]);
  const geometry = useMemo(() => {
    if (!bounds) return null;
    return {
      line: linePath(series, bounds),
      area: areaPath(series, bounds),
      peerLine: withPeer ? linePath(peer, bounds) : '',
      ticks: yearTicks(bounds),
    };
  }, [bounds, series, peer, withPeer]);
  if (!bounds || !geometry) return <div className="fe-wl3-chart" data-empty="true" aria-hidden="true" />;

  const last = series[series.length - 1];
  const at = (point) => {
    const { x, y } = place(point, bounds);
    return { left: `${(x / FIELD.w) * 100}%`, top: `${(y / FIELD.h) * 100}%` };
  };
  const nowAt = at(last);
  // Подпись у точки не должна лежать на линии: если точка в верхней половине поля, подпись уходит под неё.
  const nowLow = place(last, bounds).y / FIELD.h < 0.42;
  // В сравнении подпись верхней линии стоит над ней, нижней — под ней.
  const homeAbove = withPeer ? place(last, bounds).y <= place(peer[peer.length - 1], bounds).y : true;
  const scrub = (event) => {
    const box = boxRef.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    setHover(nearestIndex(series, bounds, (event.clientX - box.left) / box.width));
  };
  const picked = hover >= 0 ? series[hover] : null;
  const pickedAt = picked ? at(picked) : null;
  // Число у края поля не должно уезжать за экран: у правого края подпись стоит слева от точки.
  const flip = picked ? place(picked, bounds).x / FIELD.w > 0.78 : false;

  return (
    <div
      ref={boxRef}
      className="fe-wl3-chart"
      data-mode={mode}
      data-scrub={picked ? 'true' : undefined}
      role="img"
      aria-label={t('welcome.chartAria')}
      onPointerMove={scrub}
      onPointerDown={scrub}
      onPointerLeave={() => setHover(-1)}
      onPointerCancel={() => setHover(-1)}
    >
      <svg viewBox={`0 0 ${FIELD.w} ${FIELD.h}`} preserveAspectRatio="none" className="fe-wl3-chart__svg" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="fe-wl3-tone" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#1F3B78" stopOpacity="0.2" />
            <stop offset="1" stopColor="#1F3B78" stopOpacity="0" />
          </linearGradient>
          {/* Прошлое мягче: к левому краю линия уходит в холодную тень, резкой остаётся кромка «сейчас» (шаг «Свежие данные»). */}
          <linearGradient id="fe-wl3-past" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={FIELD.w} y2="0">
            <stop offset="0" stopColor="#1F3B78" stopOpacity="0.22" />
            <stop offset="0.8" stopColor="#1F3B78" stopOpacity="0.34" />
            <stop offset="0.97" stopColor="#1F3B78" stopOpacity="1" />
          </linearGradient>
        </defs>
        <g className="fe-wl3-chart__draw">
          <path d={geometry.area} fill="url(#fe-wl3-tone)" className="fe-wl3-chart__area" />
          <path d={geometry.line} className="fe-wl3-chart__line" />
        </g>
        <g className="fe-wl3-chart__past">
          <path d={geometry.area} fill="url(#fe-wl3-tone)" opacity="0.4" />
          <path d={geometry.line} className="fe-wl3-chart__line" stroke="url(#fe-wl3-past)" />
        </g>
        {withPeer ? <path d={geometry.peerLine} className="fe-wl3-chart__line fe-wl3-chart__line--peer" /> : null}
      </svg>

      <div className="fe-wl3-chart__years" aria-hidden="true">
        {geometry.ticks.map((tick) => <span key={tick.year} style={{ left: `${tick.fraction * 100}%` }}>{tick.year}</span>)}
      </div>

      {/* Кромка «сейчас»: тонкая вертикаль у последней точки и подпись месяца. Видна на шаге про свежесть. */}
      <span className="fe-wl3-chart__edge" style={{ left: nowAt.left }} aria-hidden="true" />
      <span className="fe-wl3-chart__now" style={nowAt} aria-hidden="true" />
      <span className="fe-wl3-chart__nowlabel" data-below={nowLow ? 'true' : undefined} style={nowAt} aria-hidden="true">
        {mode === 'account' ? t('welcome.account.yours') : formatMonth(last.t, locale)}
      </span>

      {withPeer ? (
        <>
          <span className="fe-wl3-chart__now fe-wl3-chart__now--peer" style={at(peer[peer.length - 1])} aria-hidden="true" />
          <span className="fe-wl3-chart__end" data-below={homeAbove ? undefined : 'true'} style={at(last)} aria-hidden="true">{names?.home}</span>
          <span className="fe-wl3-chart__end fe-wl3-chart__end--peer" data-below={homeAbove ? 'true' : undefined} style={at(peer[peer.length - 1])} aria-hidden="true">{names?.peer}</span>
        </>
      ) : null}

      {picked ? (
        <>
          <span className="fe-wl3-chart__hair" style={{ left: pickedAt.left }} aria-hidden="true" />
          <span className="fe-wl3-chart__dot" style={pickedAt} aria-hidden="true" />
          <span className="fe-wl3-chart__read" data-flip={flip ? 'true' : undefined} style={pickedAt} data-testid="welcome-read">
            <b>{formatPercent(picked.value, locale)}</b>
            {formatMonth(picked.t, locale)}
          </span>
        </>
      ) : null}
    </div>
  );
}
