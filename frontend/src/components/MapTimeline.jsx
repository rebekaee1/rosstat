// Ползунок времени для карты регионов: прокрутка показателя по годам.
// Год — controlled с родителя (URL ?year= + раскраска карты); play/pause
// живут внутри. Движение ползунка и запуск — в аналитику (region_map_timeline).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import { track, events } from '../lib/track';

const STEP_MS = 900;

export default function MapTimeline({ years, year, onYearChange, metric }) {
  const [playing, setPlaying] = useState(false);
  const trackTimer = useRef(null);

  const list = useMemo(
    () => (Array.isArray(years) ? years.filter((y) => y != null) : []),
    [years],
  );
  const ready = list.length >= 2 && year != null && typeof onYearChange === 'function';
  const min = ready ? list[0] : 0;
  const max = ready ? list[list.length - 1] : 0;
  const atEnd = ready ? year >= max : false;

  const setYearBoth = useCallback((y) => {
    if (typeof onYearChange === 'function') onYearChange(y);
  }, [onYearChange]);

  const emit = useCallback((action, y) => {
    track(events.REGIONS_MAP_TIMELINE, { metric, year: y, action });
  }, [metric]);

  useEffect(() => {
    if (!ready || !playing) return undefined;
    const i = list.indexOf(year);
    if (i < 0 || i >= list.length - 1) return undefined;
    const t = setTimeout(() => {
      const next = list[i + 1];
      setYearBoth(next);
      if (i + 1 >= list.length - 1) { setPlaying(false); emit('complete', next); }
    }, STEP_MS);
    return () => clearTimeout(t);
  }, [ready, playing, year, list, emit, setYearBoth]);

  const togglePlay = useCallback(() => {
    if (!ready) return;
    if (playing) { setPlaying(false); return; }
    if (atEnd) setYearBoth(list[0]);
    setPlaying(true);
    emit('play', atEnd ? list[0] : year);
  }, [ready, playing, atEnd, list, year, setYearBoth, emit]);

  const handleSlider = useCallback((e) => {
    if (!ready) return;
    setPlaying(false);
    const y = Number(e.target.value);
    setYearBoth(y);
    if (trackTimer.current) clearTimeout(trackTimer.current);
    trackTimer.current = setTimeout(() => emit('scrub', y), 600);
  }, [ready, setYearBoth, emit]);

  useEffect(() => () => {
    if (trackTimer.current) clearTimeout(trackTimer.current);
  }, []);

  if (!ready) return null;

  const pct = max === min ? 100 : ((year - min) / (max - min)) * 100;

  return (
    <div className="mt-1 flex items-center gap-3">
      <button
        type="button"
        onClick={togglePlay}
        aria-label={playing ? 'Пауза' : 'Проиграть по годам'}
        title={playing ? 'Пауза' : 'Проиграть по годам'}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-champagne text-white shadow-sm transition-colors hover:bg-champagne-muted"
      >
        {playing ? <Pause size={15} /> : atEnd ? <RotateCcw size={14} /> : <Play size={15} className="translate-x-[1px]" />}
      </button>

      <div className="min-w-0 flex-1">
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={year}
          onChange={handleSlider}
          aria-label="Год на карте"
          className="map-timeline w-full"
          style={{
            background: `linear-gradient(to right, #B8942F 0%, #B8942F ${pct}%, rgba(26,26,46,0.10) ${pct}%, rgba(26,26,46,0.10) 100%)`,
          }}
        />
        <div className="mt-1 flex justify-between font-mono text-[10px] tabular-nums text-text-tertiary">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      </div>

      <div className="w-16 shrink-0 text-right">
        <span className="font-mono text-lg font-bold tabular-nums text-champagne">{year}</span>
        <span className="-mt-0.5 block text-[10px] text-text-tertiary">год</span>
      </div>
    </div>
  );
}
