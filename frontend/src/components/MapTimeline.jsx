// Ползунок времени для карты регионов: прокрутка показателя по годам.
// Год — controlled с родителя (URL ?year= + раскраска карты); play/pause
// живут внутри. Движение ползунка и запуск — в аналитику (region_map_timeline).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause } from 'lucide-react';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import Button from './Button';
import '../styles/regions-w4.css';
import '../styles/k4-charts.css';

const STEP_MS = 900;

export default function MapTimeline({ years, year, onYearChange, metric }) {
  const t = useT();
  const [playing, setPlaying] = useState(false);
  const trackTimer = useRef(null);
  // Ползунок ведёт своё значение сам и не ждёт родителя: год лежит в адресе (?period=), роутер обновляет его с задержкой, и
  // управляемый input откатывал бегунок назад на каждом шаге, так что отмотать годы было нельзя. Пока человек двигает бегунок,
  // старые значения родителя бегунок не трогают; когда он замолчал на 0,45 с, он сверяется с годом из адреса.
  const [local, setLocal] = useState(year);
  const lastInput = useRef(0);
  const syncTimer = useRef(null);
  useEffect(() => {
    const idle = Date.now() - lastInput.current;
    if (idle > 450) { setLocal(year); return undefined; }
    syncTimer.current = setTimeout(() => setLocal(year), 450 - idle + 20);
    return () => clearTimeout(syncTimer.current);
  }, [year]);

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
    lastInput.current = Date.now();
    setLocal(y);
    setYearBoth(y);
    if (trackTimer.current) clearTimeout(trackTimer.current);
    trackTimer.current = setTimeout(() => emit('scrub', y), 600);
  }, [ready, setYearBoth, emit]);

  useEffect(() => () => {
    if (trackTimer.current) clearTimeout(trackTimer.current);
  }, []);

  if (!ready) return null;

  const shown = local != null ? local : year;
  const pct = max === min ? 100 : ((shown - min) / (max - min)) * 100;

  return (
    <div className="mt-3 flex items-center gap-3">
      {/* В конце ряда кнопка остаётся «играть» (треугольник) и подписана словами: круговая стрелка «повторить» читалась как загадка. */}
      <Button
        onClick={togglePlay}
        aria-label={playing ? t('map.timeline.pause') : (atEnd ? t('c8y.map.replay') : t('map.timeline.play'))}
        title={playing ? t('map.timeline.pause') : (atEnd ? t('c8y.map.replay') : t('map.timeline.play'))}
        className={atEnd && !playing
          ? 'h-10 shrink-0 gap-1.5 rounded-full! px-3.5! pointer-coarse:h-11'
          : 'h-10 w-10 shrink-0 rounded-full! px-0! pointer-coarse:h-11 pointer-coarse:w-11'}
        data-testid="map-timeline-play"
      >
        {playing ? <Pause size={15} aria-hidden="true" /> : <Play size={15} className={atEnd ? undefined : 'translate-x-[1px]'} aria-hidden="true" />}
        {atEnd && !playing ? <span className="whitespace-nowrap text-[13px] font-semibold">{t('c8y.map.replay')}</span> : null}
      </Button>

      <div className="min-w-0 flex-1">
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={shown}
          onChange={handleSlider}
          aria-label={t('map.timeline.yearOnMap')}
          className="map-timeline w-full"
          style={{ '--k4-pct': `${pct}%` }}
        />
        <div className="fe-num mt-1 flex justify-between text-xs text-text-secondary">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      </div>

      <div className="w-16 shrink-0 text-right">
        <span key={shown} className="fe-map-year fe-num whitespace-nowrap text-xl font-bold text-champagne-ink" data-testid="map-timeline-year">{shown}</span>
        <span className="-mt-0.5 block text-xs text-text-secondary">{t('common.year').toLowerCase()}</span>
      </div>
    </div>
  );
}
