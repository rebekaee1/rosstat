// Ползунок времени для карты регионов: прокрутка показателя по годам с
// плавной анимацией раскраски (сама анимация — CSS-переход fill в RegionsMap,
// здесь только смена активного года). Кнопка Play проигрывает историю
// покадрово по годам. Год живёт внутри компонента (self-driven), наверх
// уходит через onYearChange только для раскраски карты и подписи. Движение
// ползунка и запуск отправляются в аналитику (событие region_map_timeline) —
// попадает в Пульс/BI для гипотез «как менялось во времени».
import { useCallback, useEffect, useRef, useState } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import { track, events } from '../lib/track';

const STEP_MS = 900; // темп покадровой смены года при проигрывании

export default function MapTimeline({ years, initialYear, onYearChange, metric }) {
  const [year, setYear] = useState(initialYear ?? years[years.length - 1]);
  const [playing, setPlaying] = useState(false);
  const trackTimer = useRef(null);

  const min = years[0];
  const max = years[years.length - 1];
  const atEnd = year >= max;

  const setYearBoth = useCallback((y) => {
    setYear(y);
    onYearChange(y);
  }, [onYearChange]);

  const emit = useCallback((action, y) => {
    track(events.REGIONS_MAP_TIMELINE, { metric, year: y, action });
  }, [metric]);

  // Проигрывание: раз в STEP_MS переходим к следующему году; эффект каждый раз
  // видит свежий year (перезапускается при его смене). На последнем году —
  // останавливаемся. setState — внутри setTimeout (асинхронно), не в теле эффекта.
  useEffect(() => {
    if (!playing) return undefined;
    const i = years.indexOf(year);
    if (i >= years.length - 1) return undefined; // достигли конца
    const t = setTimeout(() => {
      const next = years[i + 1];
      setYearBoth(next);
      if (i + 1 >= years.length - 1) { setPlaying(false); emit('complete', next); }
    }, STEP_MS);
    return () => clearTimeout(t);
  }, [playing, year, years, emit, setYearBoth]);

  const togglePlay = useCallback(() => {
    if (playing) { setPlaying(false); return; }
    if (atEnd) setYearBoth(years[0]); // с конца — перематываем в начало
    setPlaying(true);
    emit('play', atEnd ? years[0] : year);
  }, [playing, atEnd, years, year, setYearBoth, emit]);

  const handleSlider = useCallback((e) => {
    setPlaying(false);
    const y = Number(e.target.value);
    setYearBoth(y);
    // Дебаунс аналитики скраба — не спамим на каждый шаг ползунка.
    if (trackTimer.current) clearTimeout(trackTimer.current);
    trackTimer.current = setTimeout(() => emit('scrub', y), 600);
  }, [setYearBoth, emit]);

  useEffect(() => () => {
    if (trackTimer.current) clearTimeout(trackTimer.current);
  }, []);

  const pct = max === min ? 100 : ((year - min) / (max - min)) * 100;

  return (
    <div className="mt-3 flex items-center gap-3">
      <button
        type="button"
        onClick={togglePlay}
        aria-label={playing ? 'Пауза' : 'Проиграть по годам'}
        title={playing ? 'Пауза' : 'Проиграть по годам'}
        className="shrink-0 w-9 h-9 flex items-center justify-center rounded-full bg-champagne text-white hover:bg-champagne-muted transition-colors shadow-sm"
      >
        {playing ? <Pause size={15} /> : atEnd ? <RotateCcw size={14} /> : <Play size={15} className="translate-x-[1px]" />}
      </button>

      <div className="flex-1 min-w-0">
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
        <div className="mt-1 flex justify-between text-[10px] text-text-tertiary font-mono tabular-nums">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      </div>

      <div className="shrink-0 w-16 text-right">
        <span className="font-mono text-lg font-bold text-champagne tabular-nums">{year}</span>
        <span className="block text-[10px] text-text-tertiary -mt-0.5">год</span>
      </div>
    </div>
  );
}
